import pytest
from reconciliation.engine import reconcile
from reconciliation.imports import import_csv
from reconciliation.reviews import resolve
from reconciliation.models import Resolution, Audit

pytestmark = pytest.mark.django_db


def test_partial_delivery_and_price_are_explicit(org, imported):
    version = reconcile(org.id, imported)
    assert {e.code for e in version.exceptions.all()} == {"over_received", "price"}
    assert version.snapshot["lines"][0]["received"] == "5.0000"
    assert version.snapshot["total"] == "20.00"


def test_currency_and_missing_po_never_match(org):
    r = import_csv(
        org.id,
        "invoice",
        b"vendor,invoice,po,line,currency,quantity,unit_price\nAcme,X,UNKNOWN,1,EUR,1,2\n",
    )
    v = reconcile(org.id, r.invoice_ids[0])
    assert {e.code for e in v.exceptions.all()} == {"missing_po", "over_received"}
    import_csv(
        org.id, "po", b"vendor,po,line,currency,quantity,unit_price\nAcme,UNKNOWN,1,USD,1,2\n"
    )
    v = reconcile(org.id, r.invoice_ids[0])
    assert "currency" in {e.code for e in v.exceptions.all()}


def test_duplicate_fingerprint_is_reviewable(org, imported):
    r = import_csv(
        org.id,
        "invoice",
        b"vendor,invoice,po,line,currency,quantity,unit_price\nAcme,I2,P1,1,USD,8,2.50\n",
    )
    assert "duplicate" in {e.code for e in reconcile(org.id, r.invoice_ids[0]).exceptions.all()}


def test_resolution_requires_note_and_records_audit(org, imported):
    v = reconcile(org.id, imported)
    with pytest.raises(ValueError):
        resolve(org.id, imported, expected_revision=v.revision, note=" ")
    new = resolve(
        org.id, imported, expected_revision=v.revision, note="Accept synthetic price and timing"
    )
    assert new.revision > v.revision
    assert Resolution.objects.get().note == "Accept synthetic price and timing"
    assert Audit.objects.filter(action="resolved").exists()


def test_multiple_invoices_cannot_hide_cumulative_quantity(org, imported):
    r = import_csv(
        org.id,
        "invoice",
        b"vendor,invoice,po,line,currency,quantity,unit_price\nAcme,I3,P1,1,USD,4,2.00\n",
    )
    v = reconcile(org.id, r.invoice_ids[0])
    assert "over_ordered" in {e.code for e in v.exceptions.all()}


def test_exception_facts_expose_both_sides_of_price_and_currency(org, imported):
    v = reconcile(org.id, imported)
    price = v.exceptions.get(code="price")
    assert price.facts["ordered_unit_price"] == "2.0000"
    assert price.facts["ordered_currency"] == "USD"
    assert price.facts["unit_price"] == "2.5000"
