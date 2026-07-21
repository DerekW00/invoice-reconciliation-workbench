import pytest
from django.core.management import call_command
from reconciliation.models import Invoice, Organization

pytestmark = pytest.mark.django_db


def test_demo_seed_is_repeatable_and_tenant_separated(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    call_command("seed_demo")
    call_command("seed_demo")
    assert Invoice.objects.filter(org__name="Northstar Workshop").count() == 5
    assert Organization.objects.count() == 2
    assert Invoice.objects.filter(status="approved").count() == 1
    call_command("evaluate")


def test_seed_requires_explicit_demo_mode(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("seed_demo")
    assert not Invoice.objects.exists()
