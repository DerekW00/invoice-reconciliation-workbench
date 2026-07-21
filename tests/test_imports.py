import pytest
from reconciliation.imports import import_csv
from reconciliation.models import Invoice, ImportBatch, PurchaseOrderLine

pytestmark = pytest.mark.django_db
PO = b"vendor,po,line,currency,quantity,unit_price\nAcme,P1,1,USD,10,2\n"


def test_digest_retry_and_canonical_numbers(org):
    a = import_csv(org.id, "po", PO)
    b = import_csv(org.id, "po", PO.replace(b",10,2", b",10.00,2.0000"))
    assert a.batch_id == b.batch_id
    assert PurchaseOrderLine.objects.count() == 1


def test_changed_key_is_atomic(org):
    import_csv(org.id, "po", PO)
    with pytest.raises(ValueError):
        import_csv(org.id, "po", PO.replace(b",10,2", b",11,2"))
    assert str(PurchaseOrderLine.objects.get().quantity) == "10.0000"
    assert ImportBatch.objects.count() == 1


@pytest.mark.parametrize(
    "content",
    [
        PO + b"Acme,P2,1,USD,nope,2\n",
        PO.replace(b"vendor,po", b"vendor,vendor"),
        PO.replace(b"vendor,po", b"strange,po"),
        b"x" * 262145,
        PO + b"Acme,P1,1,USD,10,2\n",
        PO.replace(b",10,2", b",NaN,2"),
        PO.replace(b"USD", b"JPY"),
    ],
)
def test_invalid_import_rolls_back(org, content):
    with pytest.raises(ValueError):
        import_csv(org.id, "po", content)
    assert not PurchaseOrderLine.objects.exists()
    assert not ImportBatch.objects.exists()


def test_invoice_line_duplicate_and_changed_number(org, imported):
    content = b"vendor,invoice,po,line,currency,quantity,unit_price\nAcme,I1,P1,1,USD,9,2.50\n"
    with pytest.raises(ValueError):
        import_csv(org.id, "invoice", content)
    with pytest.raises(ValueError):
        import_csv(org.id, "invoice", content + content.split(b"\n")[1] + b"\n")
    assert Invoice.objects.count() == 1


def test_row_cap(org):
    rows = "".join(f"Acme,P{i},1,USD,1,1\n" for i in range(501))
    with pytest.raises(ValueError):
        import_csv(org.id, "po", PO.split(b"\n")[0] + b"\n" + rows.encode())
