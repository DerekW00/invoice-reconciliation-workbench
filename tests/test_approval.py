from concurrent.futures import ThreadPoolExecutor
import pytest
from django.db import close_old_connections
from reconciliation.engine import reconcile
from reconciliation.reviews import resolve, approve
from reconciliation.imports import import_csv
from reconciliation.exports import export_approved
from reconciliation.models import Invoice

pytestmark = pytest.mark.django_db


def test_unresolved_and_stale_rejected(org, imported):
    v = reconcile(org.id, imported)
    with pytest.raises(ValueError):
        approve(org.id, imported, expected_revision=v.revision)
    r = resolve(org.id, imported, expected_revision=v.revision, note="Accepted")
    with pytest.raises(ValueError):
        approve(org.id, imported, expected_revision=v.revision)
    approve(org.id, imported, expected_revision=r.revision)
    assert Invoice.objects.get(pk=imported).approved_snapshot["total"] == "20.00"


def test_approval_frozen_after_new_receipt(org, imported):
    v = reconcile(org.id, imported)
    v = resolve(org.id, imported, expected_revision=v.revision, note="Accepted")
    approve(org.id, imported, expected_revision=v.revision)
    old = export_approved(org.id, imported)
    import_csv(org.id, "receipt", b"vendor,po,line,receipt,quantity\nAcme,P1,1,R2,3\n")
    assert export_approved(org.id, imported) == old


def test_new_import_invalidates_old_review(org, imported):
    v = reconcile(org.id, imported)
    v = resolve(org.id, imported, expected_revision=v.revision, note="Accepted")
    import_csv(org.id, "receipt", b"vendor,po,line,receipt,quantity\nAcme,P1,1,R2,3\n")
    with pytest.raises(ValueError):
        approve(org.id, imported, expected_revision=v.revision)


@pytest.mark.django_db(transaction=True)
def test_concurrent_approvers_one_wins(org, imported):
    v = reconcile(org.id, imported)
    v = resolve(org.id, imported, expected_revision=v.revision, note="Accepted")

    def attempt(_):
        close_old_connections()
        try:
            approve(org.id, imported, expected_revision=v.revision)
            return "approved"
        except ValueError:
            return "stale"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["approved", "stale"]


@pytest.mark.django_db(transaction=True)
def test_concurrent_resolve_and_approve_fenced(org, imported):
    v = reconcile(org.id, imported)
    v = resolve(org.id, imported, expected_revision=v.revision, note="Accepted")

    def attempt(operation):
        close_old_connections()
        try:
            operation(
                org.id,
                imported,
                expected_revision=v.revision,
                **({"note": "New decision"} if operation == resolve else {}),
            )
            return "ok"
        except ValueError:
            return "stale"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, [approve, resolve])) == ["ok", "stale"]


def test_reviewer_identity_is_recorded(org, imported, user):
    from reconciliation.models import Audit, Resolution

    v = reconcile(org.id, imported)
    v = resolve(
        org.id, imported, expected_revision=v.revision, note="Authorized review", actor_id=user.id
    )
    approve(org.id, imported, expected_revision=v.revision, actor_id=user.id)
    assert Resolution.objects.get().actor_id == user.id
    assert Audit.objects.get(action="approved").actor_id == user.id


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_import_is_idempotent(org):
    from reconciliation.models import ImportBatch

    payload = b"vendor,po,line,currency,quantity,unit_price\nAcme,RACE,1,USD,1,2\n"

    def attempt(_):
        close_old_connections()
        try:
            return import_csv(org.id, "po", payload).reused
        finally:
            close_old_connections()

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]
    assert ImportBatch.objects.count() == 1
