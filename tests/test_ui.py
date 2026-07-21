from datetime import datetime, timezone
import pytest
from reconciliation.engine import reconcile
from reconciliation.models import Audit


@pytest.mark.django_db
def test_history_timestamps_are_rendered_in_labeled_utc(client, user, org, imported):
    reconcile(org.id, imported)
    Audit.objects.update(created_at=datetime(2026, 10, 26, 21, 0, tzinfo=timezone.utc))
    client.force_login(user)
    response = client.get(f"/invoices/{imported}/")
    assert b"21:00:00 UTC" in response.content
