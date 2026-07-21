import csv
import io
from .models import Invoice


def safe_cell(value: str) -> str:
    probe = value
    while probe and (probe[0].isspace() or ord(probe[0]) < 33 or ord(probe[0]) == 127):
        probe = probe[1:]
    return "'" + value if probe.startswith(("=", "+", "-", "@")) else value


def export_approved(org_id: int, invoice_id: int) -> bytes:
    invoice = Invoice.objects.filter(org_id=org_id, pk=invoice_id, status="approved").first()
    if not invoice or not invoice.approved_snapshot:
        raise ValueError("Approved invoice not found")
    snapshot = invoice.approved_snapshot
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        ["vendor", "invoice", "po", "line", "currency", "quantity", "unit_price", "amount"]
    )
    for line in snapshot["lines"]:
        writer.writerow(
            [
                safe_cell(str(v))
                for v in [
                    snapshot["vendor"],
                    snapshot["invoice"],
                    line["po"],
                    line["line"],
                    line["currency"],
                    line["quantity"],
                    line["unit_price"],
                    line["amount"],
                ]
            ]
        )
    return stream.getvalue().encode("utf-8")
