import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from reconciliation.demo_data import ROOT, seed
from reconciliation.models import Invoice, Organization
from reconciliation.engine import reconcile
from reconciliation.provider import explain


class Command(BaseCommand):
    help = "Evaluate frozen synthetic functional outcomes, without retaining evaluation data."

    def handle(self, *args, **options):
        with transaction.atomic():
            seed()
            org = Organization.objects.get(name="Northstar Workshop")
            expected = json.loads((ROOT / "fixtures" / "expected.json").read_text())
            for number, codes in expected.items():
                invoice = Invoice.objects.get(org=org, number=number)
                actual = sorted({e.code for e in reconcile(org.id, invoice.id).exceptions.all()})
                if actual != codes:
                    raise CommandError(f"{number}: expected {codes}, got {actual}")
            for mode in ["invalid_ids", "malformed", "failure"]:
                try:
                    explain([{"id": 1, "code": "price"}], mode)
                except ValueError:
                    continue
                raise CommandError(f"Unsafe fixture accepted: {mode}")
            transaction.set_rollback(True)
        self.stdout.write(
            "8/8 scripted functional cases passed (5 reconciliation + 3 provider rejections). Live quality, speed and spend unmeasured."
        )
