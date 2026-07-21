import copy
from django.db import transaction
from .engine import locked_invoice, build_version
from .models import (
    Organization,
    Invoice,
    Membership,
    ReconciliationVersion,
    Exception,
    Resolution,
    Audit,
)


def current(
    org_id: int, invoice_id: int, expected_revision: int
) -> tuple[Organization, Invoice, ReconciliationVersion]:
    org, invoice = locked_invoice(org_id, invoice_id)
    version = build_version(org, invoice)
    if invoice.status == "approved" or version.revision != expected_revision:
        raise ValueError("Stale revision. Reload and review the latest facts.")
    return org, invoice, version


@transaction.atomic
def resolve(
    org_id: int, invoice_id: int, *, expected_revision: int, note: str, actor_id: int | None = None
) -> ReconciliationVersion:
    if not note.strip() or len(note) > 2000:
        raise ValueError("A resolution note of 1–2000 characters is required")
    org, invoice, old = current(org_id, invoice_id, expected_revision)
    validate_actor(org_id, actor_id)
    invoice.revision += 1
    invoice.save(update_fields=["revision"])
    new = ReconciliationVersion.objects.create(
        invoice=invoice,
        revision=invoice.revision,
        source_revision=org.revision,
        snapshot=copy.deepcopy(old.snapshot),
        resolved=True,
    )
    Exception.objects.bulk_create(
        [
            Exception(version=new, code=e.code, line=e.line, facts=e.facts)
            for e in old.exceptions.all()
        ]
    )
    Resolution.objects.create(version=new, note=note.strip(), actor_id=actor_id)
    Audit.objects.create(
        invoice=invoice,
        revision=new.revision,
        action="resolved",
        note=note.strip(),
        actor_id=actor_id,
    )
    return new


@transaction.atomic
def approve(
    org_id: int, invoice_id: int, *, expected_revision: int, actor_id: int | None = None
) -> Invoice:
    _, invoice, version = current(org_id, invoice_id, expected_revision)
    validate_actor(org_id, actor_id)
    if version.exceptions.exists() and not version.resolved:
        raise ValueError("Resolve all exceptions with a note before approval")
    invoice.approved_snapshot = copy.deepcopy(version.snapshot)
    invoice.status = "approved"
    invoice.revision += 1
    invoice.save(update_fields=["approved_snapshot", "status", "revision"])
    Audit.objects.create(
        invoice=invoice, revision=invoice.revision, action="approved", actor_id=actor_id
    )
    return invoice


def validate_actor(org_id: int, actor_id: int | None) -> None:
    if (
        actor_id is not None
        and not Membership.objects.filter(org_id=org_id, user_id=actor_id).exists()
    ):
        raise ValueError("Reviewer is not a member of this organization")
