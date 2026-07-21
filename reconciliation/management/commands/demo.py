from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migrate, seed and run the synthetic local demo on 127.0.0.1:8102."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true")

    def handle(self, *args, **options):
        call_command("migrate", verbosity=0)
        call_command("seed_demo")
        call_command("worker", once=True)
        self.stdout.write("Local demo: http://127.0.0.1:8102")
        if not options["check"]:
            call_command("runserver", "127.0.0.1:8102", use_reloader=False)
