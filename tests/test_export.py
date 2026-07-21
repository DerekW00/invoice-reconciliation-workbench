import pytest
from reconciliation.exports import export_approved, safe_cell
from reconciliation.engine import reconcile
from reconciliation.reviews import resolve, approve

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "value", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)", " \t=1", "\r+1", "\x01@cmd"]
)
def test_formula_text_is_escaped(value):
    assert safe_cell(value).startswith("'")


def test_export_is_frozen_and_tenant_scoped(org, other, imported):
    with pytest.raises(ValueError):
        export_approved(org.id, imported)
    v = reconcile(org.id, imported)
    v = resolve(org.id, imported, expected_revision=v.revision, note="Accepted")
    approve(org.id, imported, expected_revision=v.revision)
    assert b"20.00" in export_approved(org.id, imported)
    with pytest.raises(ValueError):
        export_approved(other.id, imported)


def test_http_export_requires_membership(client, user, org, other, imported):
    assert client.get(f"/invoices/{imported}/export/").status_code == 302
    client.force_login(user)
    from reconciliation.models import Invoice

    foreign = Invoice.objects.create(org=other, vendor="Other", number="Foreign", fingerprint="f")
    assert client.get(f"/invoices/{foreign.id}/export/").status_code == 404
    assert client.post(f"/invoices/{foreign.id}/approve/", {"revision": 1}).status_code == 404


@pytest.mark.parametrize("value", ["\u2003=1", "\u00a0+1", "\u2028@cmd"])
def test_unicode_whitespace_formula_is_escaped(value):
    assert safe_cell(value).startswith("'")


def test_http_actions_are_csrf_protected(user, imported):
    from django.test import Client

    secure_client = Client(enforce_csrf_checks=True)
    secure_client.force_login(user)
    assert secure_client.post(f"/invoices/{imported}/approve/", {"revision": 1}).status_code == 403


def test_foreign_detail_job_activity_and_cancel_denied(client, user, org, other, imported):
    from reconciliation.jobs import enqueue
    from django.contrib.auth.models import User
    from reconciliation.models import Membership

    j = enqueue(org.id, reconcile(org.id, imported).id)
    outsider = User.objects.create_user("outsider")
    Membership.objects.create(user=outsider, org=other)
    client.force_login(outsider)
    assert client.get(f"/invoices/{imported}/").status_code == 404
    assert client.get(f"/invoices/{imported}/activity/").status_code == 404
    assert client.post(f"/invoices/{imported}/explain/").status_code == 404
    assert client.post(f"/jobs/{j.id}/cancel/").status_code == 404
