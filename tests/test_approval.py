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


def run_with_proven_postgres_wait(org_id, winner, contender):
    """Run real services on distinct connections, observing the blocked backend in PostgreSQL."""
    from queue import Queue
    from time import monotonic, sleep
    from django.db import connection, connections, transaction
    from reconciliation.models import Organization

    backend_pid = Queue(maxsize=1)

    def waiting_operation():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                # Bound a failed test's database wait as well as the Python future join.
                cursor.execute("SET statement_timeout = '5s'")
                cursor.execute("SET lock_timeout = '4s'")
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.put(cursor.fetchone()[0], timeout=2)
            try:
                return contender()
            except ValueError as exc:
                return exc
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Organization.objects.select_for_update().get(pk=org_id)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                blocking_pid = cursor.fetchone()[0]
            future = pool.submit(waiting_operation)
            waiting_pid = backend_pid.get(timeout=2)
            assert waiting_pid != blocking_pid, "The operations must use separate PG connections"
            deadline = monotonic() + 2
            observed = None
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")
                    cursor.execute(
                        "SELECT wait_event_type, pg_blocking_pids(pid) "
                        "FROM pg_stat_activity WHERE pid = %s",
                        [waiting_pid],
                    )
                    observed = cursor.fetchone()
                if observed and observed[0] == "Lock" and blocking_pid in observed[1]:
                    break
                assert not future.done(), "Contender completed without the required row-lock wait"
                sleep(0.01)
            else:
                pytest.fail(f"Did not observe PostgreSQL lock contention: {observed!r}")
            assert not future.done(), "The contender must still be blocked before the winner runs"
            winner_result = winner()
        # Exiting the outer transaction commits the winner before releasing the contender.
        return winner_result, future.result(timeout=5)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("winner_name", ["resolve", "approve"])
def test_contended_resolution_and_approval_reject_obsolete_revision(org, imported, winner_name):
    from reconciliation.models import Audit

    version = reconcile(org.id, imported)
    reviewed = resolve(
        org.id, imported, expected_revision=version.revision, note="Initial acceptance"
    )

    def resolution():
        return resolve(
            org.id, imported, expected_revision=reviewed.revision, note="Coordinated new decision"
        )

    def approval():
        approve(org.id, imported, expected_revision=reviewed.revision)
        return export_approved(org.id, imported)

    winner, contender = (
        (resolution, approval) if winner_name == "resolve" else (approval, resolution)
    )
    winner_result, rejected = run_with_proven_postgres_wait(org.id, winner, contender)
    assert isinstance(rejected, ValueError)
    assert "Stale revision" in str(rejected)
    invoice = Invoice.objects.get(pk=imported)
    if winner_name == "resolve":
        assert invoice.status == "review"
        assert invoice.approved_snapshot is None
        assert Audit.objects.filter(invoice=invoice, action="approved").count() == 0
        approve(org.id, imported, expected_revision=winner_result.revision)
        assert b"20.00" in export_approved(org.id, imported)
    else:
        assert invoice.status == "approved"
        assert export_approved(org.id, imported) == winner_result
        assert not Audit.objects.filter(invoice=invoice, note="Coordinated new decision").exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("winner_name", ["import", "approve"])
def test_contended_import_and_approval_preserve_review_and_frozen_export(
    org, imported, winner_name
):
    from decimal import Decimal
    from django.db.models import Sum
    from reconciliation.models import Receipt

    version = reconcile(org.id, imported)
    reviewed = resolve(
        org.id, imported, expected_revision=version.revision, note="Accept five received"
    )

    def new_receipt():
        return import_csv(org.id, "receipt", b"vendor,po,line,receipt,quantity\nAcme,P1,1,R2,3\n")

    def approval():
        approve(org.id, imported, expected_revision=reviewed.revision)
        return export_approved(org.id, imported)

    winner, contender = (
        (new_receipt, approval) if winner_name == "import" else (approval, new_receipt)
    )
    winner_result, contender_result = run_with_proven_postgres_wait(org.id, winner, contender)
    invoice = Invoice.objects.get(pk=imported)
    assert Receipt.objects.filter(org=org).aggregate(total=Sum("quantity"))["total"] == Decimal("8")
    if winner_name == "import":
        assert isinstance(contender_result, ValueError)
        assert "Stale revision" in str(contender_result)
        assert invoice.status == "review"
        assert invoice.approved_snapshot is None
        fresh = reconcile(org.id, imported)
        assert fresh.revision > reviewed.revision
        assert fresh.snapshot["lines"][0]["received"] == "8.0000"
        assert not fresh.resolved, (
            "The prior acceptance must not silently carry to new source facts"
        )
        accepted = resolve(
            org.id, imported, expected_revision=fresh.revision, note="Review eight now received"
        )
        approve(org.id, imported, expected_revision=accepted.revision)
        invoice.refresh_from_db()
        assert invoice.approved_snapshot["lines"][0]["received"] == "8.0000"
    else:
        assert not isinstance(contender_result, ValueError)
        assert not contender_result.reused
        assert invoice.status == "approved"
        assert invoice.approved_snapshot["lines"][0]["received"] == "5.0000"
        assert export_approved(org.id, imported) == winner_result
        # Reconciliation after the committed receipt also retains the frozen financial facts.
        assert reconcile(org.id, imported).snapshot["lines"][0]["received"] == "5.0000"
        assert export_approved(org.id, imported) == winner_result
