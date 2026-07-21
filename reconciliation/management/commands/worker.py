import time
from django.core.management.base import BaseCommand
from reconciliation.jobs import work_once


class Command(BaseCommand):
    help = "Process durable fixture explanation jobs; no external provider calls."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            worked = work_once()
            if options["once"]:
                self.stdout.write("Processed one job" if worked else "No eligible job")
                return
            if not worked:
                time.sleep(2)
