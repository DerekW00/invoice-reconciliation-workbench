"""Validate outside the transaction, then publish under an organization lock."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from .money import finite, comparable
from .models import Organization, ImportBatch, PurchaseOrderLine, Receipt, Invoice, InvoiceLine

SCHEMAS = {
    "po": ["vendor", "po", "line", "currency", "quantity", "unit_price"],
    "receipt": ["vendor", "po", "line", "receipt", "quantity"],
    "invoice": ["vendor", "invoice", "po", "line", "currency", "quantity", "unit_price"],
}


@dataclass(frozen=True)
class ImportResult:
    batch_id: int
    invoice_ids: tuple[int, ...]
    reused: bool = False


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def parse(kind: str, content: bytes) -> list[dict[str, str]]:
    if kind not in SCHEMAS or len(content) > 256 * 1024:
        raise ValueError("Unknown import type or file exceeds 256 KiB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8"), newline=""), strict=True)
        if reader.fieldnames != SCHEMAS[kind]:
            raise ValueError("Header must match the documented schema exactly")
        rows: list[dict[str, str]] = []
        keys = set()
        for raw in reader:
            if len(rows) >= 500 or None in raw or any(v is None for v in raw.values()):
                raise ValueError("Invalid row shape or more than 500 rows")
            row = {}
            for key, value in raw.items():
                if not value or len(value) > 100 or "\x00" in value:
                    raise ValueError("Empty, oversized or NUL-containing field")
                if key in {"quantity", "unit_price"}:
                    number = finite(Decimal(value))
                    row[key] = format(number.normalize(), "f")
                else:
                    row[key] = value
            if "currency" in row:
                comparable(row["currency"], row["currency"])
            identity = tuple(
                row[k]
                for k in (
                    ["vendor", "invoice", "po", "line"]
                    if kind == "invoice"
                    else ["vendor", "po", "line"] + (["receipt"] if kind == "receipt" else [])
                )
            )
            if identity in keys:
                raise ValueError("Duplicate business key within file")
            keys.add(identity)
            rows.append(row)
        if not rows:
            raise ValueError("File has no data rows")
        return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))
    except (UnicodeError, csv.Error, InvalidOperation) as exc:
        raise ValueError("Malformed UTF-8 CSV or decimal") from exc


@transaction.atomic
def _publish(org_id: int, kind: str, rows: list[dict[str, str]]) -> ImportResult:
    org = Organization.objects.select_for_update().get(pk=org_id)
    digest = _digest(rows)
    previous = ImportBatch.objects.filter(org=org, kind=kind, digest=digest).first()
    invoice_ids = []
    if previous:
        if kind == "invoice":
            for vendor, number in sorted({(r["vendor"], r["invoice"]) for r in rows}):
                invoice_ids.append(Invoice.objects.get(org=org, vendor=vendor, number=number).id)
        return ImportResult(previous.id, tuple(invoice_ids), True)
    if kind == "invoice":
        groups: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in rows:
            groups.setdefault((row["vendor"], row["invoice"]), []).append(row)
        for (vendor, number), lines in groups.items():
            if Invoice.objects.filter(org=org, vendor=vendor, number=number).exists():
                raise ValueError("Invoice number already exists; changed imports cannot replace it")
            fingerprint = _digest([{k: v for k, v in r.items() if k != "invoice"} for r in lines])
            invoice = Invoice.objects.create(
                org=org, vendor=vendor, number=number, fingerprint=fingerprint
            )
            invoice_ids.append(invoice.id)
            for row in lines:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    **{k: v for k, v in row.items() if k not in {"vendor", "invoice"}},
                )
    else:
        model = PurchaseOrderLine if kind == "po" else Receipt
        for row in rows:
            identity_fields = ["vendor", "po", "line"] + (["receipt"] if kind == "receipt" else [])
            identity = {k: row[k] for k in identity_fields}
            if model.objects.filter(org=org, **identity).exists():
                raise ValueError("Existing business key conflicts; publish a new identifier")
            model.objects.create(org=org, **row)
    batch = ImportBatch.objects.create(org=org, kind=kind, digest=digest, row_count=len(rows))
    org.revision += 1
    org.save(update_fields=["revision"])
    return ImportResult(batch.id, tuple(invoice_ids))


def import_csv(org_id: int, kind: str, content: bytes) -> ImportResult:
    return _publish(org_id, kind, parse(kind, content))
