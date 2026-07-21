from pathlib import Path
from django.contrib.auth.models import User
from django.db import transaction
from .models import Organization, Membership, Invoice
from .imports import import_csv
from .engine import reconcile
from .reviews import approve
from .jobs import enqueue

ROOT = Path(__file__).resolve().parent.parent


@transaction.atomic
def seed() -> None:
    org, _ = Organization.objects.get_or_create(name="Northstar Workshop")
    other, _ = Organization.objects.get_or_create(name="Southbank Studio")
    for username, tenant in [("reviewer", org), ("other-reviewer", other)]:
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password("local-demo-2026")
            user.save()
        Membership.objects.get_or_create(user=user, defaults={"org": tenant})
    for kind in ["po", "receipt", "invoice"]:
        import_csv(org.id, kind, (ROOT / "fixtures" / "demo" / f"{kind}.csv").read_bytes())
    # A real foreign-tenant invoice makes access-control demonstrations reproducible.
    import_csv(
        other.id,
        "invoice",
        b"vendor,invoice,po,line,currency,quantity,unit_price\nSouthbank,PRIVATE-001,PO-X,1,GBP,1,70\n",
    )
    for invoice in Invoice.objects.filter(org=org).order_by("id"):
        version = reconcile(org.id, invoice.id)
        if invoice.number == "INV-203" and invoice.status != "approved":
            approve(org.id, invoice.id, expected_revision=version.revision)
        if invoice.number == "INV-204" and not invoice.versions.filter(job__isnull=False).exists():
            enqueue(org.id, version.id)
