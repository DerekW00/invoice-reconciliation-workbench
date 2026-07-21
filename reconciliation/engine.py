"""Explicit identifier reconciliation. Organization lock precedes invoice lock everywhere."""

from typing import Any
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from .money import amount
from .models import (
    InvoiceLine,
    Organization,
    Invoice,
    PurchaseOrderLine,
    Receipt,
    ReconciliationVersion,
    Exception,
    Audit,
)


def locked_invoice(org_id: int, invoice_id: int) -> tuple[Organization, Invoice]:
    org = Organization.objects.select_for_update().get(pk=org_id)
    try:
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id, org=org)
    except Invoice.DoesNotExist as exc:
        raise ValueError("Invoice not found") from exc
    return org, invoice


def build_version(org: Organization, invoice: Invoice) -> ReconciliationVersion:
    existing = invoice.versions.order_by("-revision").first()
    if existing and (invoice.status == "approved" or existing.source_revision == org.revision):
        return existing
    lines = []
    conditions: list[tuple[str, str, dict[str, Any]]] = []
    totals: dict[str, Decimal] = {}
    duplicate = (
        Invoice.objects.filter(org=org, vendor=invoice.vendor, fingerprint=invoice.fingerprint)
        .exclude(pk=invoice.pk)
        .exists()
    )
    for line in invoice.lines.order_by("po", "line"):
        po = PurchaseOrderLine.objects.filter(
            org=org, vendor=invoice.vendor, po=line.po, line=line.line
        ).first()
        received = Receipt.objects.filter(
            org=org, vendor=invoice.vendor, po=line.po, line=line.line
        ).aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        cumulative = InvoiceLine.objects.filter(
            invoice__org=org, invoice__vendor=invoice.vendor, po=line.po, line=line.line
        ).aggregate(total=Sum("quantity"))["total"]
        extended = amount(line.quantity, line.unit_price)
        facts = {
            "po": line.po,
            "line": line.line,
            "currency": line.currency,
            "quantity": str(line.quantity),
            "unit_price": str(line.unit_price),
            "received": str(received),
            "amount": str(extended),
            "ordered": str(po.quantity) if po else None,
            "ordered_unit_price": str(po.unit_price) if po else None,
            "ordered_currency": po.currency if po else None,
            "cumulative_invoiced": str(cumulative),
        }
        lines.append(facts)
        totals[line.currency] = totals.get(line.currency, Decimal("0")) + extended
        codes = []
        if not po:
            codes.append("missing_po")
        else:
            if po.currency != line.currency:
                codes.append("currency")
            if cumulative > po.quantity:
                codes.append("over_ordered")
            if line.unit_price != po.unit_price and po.currency == line.currency:
                codes.append("price")
        if cumulative > received:
            codes.append("over_received")
        if duplicate:
            codes.append("duplicate")
        conditions.extend((code, line.line, facts) for code in codes)
    if len(totals) > 1:
        conditions.append(
            ("currency", "all", {"reason": "Multiple currencies; no combined monetary total"})
        )
    invoice.revision += 1
    invoice.save(update_fields=["revision"])
    snapshot = {
        "vendor": invoice.vendor,
        "invoice": invoice.number,
        "lines": lines,
        "totals": {k: str(v) for k, v in totals.items()},
        "total": str(next(iter(totals.values()))) if len(totals) == 1 else "mixed",
    }
    version = ReconciliationVersion.objects.create(
        invoice=invoice, revision=invoice.revision, source_revision=org.revision, snapshot=snapshot
    )
    Exception.objects.bulk_create(
        [
            Exception(version=version, code=code, line=line, facts=facts)
            for code, line, facts in conditions
        ]
    )
    Audit.objects.create(invoice=invoice, revision=invoice.revision, action="reconciled")
    return version


@transaction.atomic
def reconcile(org_id: int, invoice_id: int) -> ReconciliationVersion:
    return build_version(*locked_invoice(org_id, invoice_id))
