import os
from django.core.management.base import BaseCommand, CommandError
from reconciliation.demo_data import seed


class Command(BaseCommand):
    help = "Seed repeatable newly synthetic local accounts and reconciliation fixtures."

    def handle(self, *args, **options):
        if os.environ.get("DEMO_MODE") != "1":
            raise CommandError("seed_demo requires explicit DEMO_MODE=1")
        seed()
        self.stdout.write(
            "Synthetic demo ready: reviewer / local-demo-2026; other-reviewer / local-demo-2026"
        )
