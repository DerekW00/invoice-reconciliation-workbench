import pytest
from django.contrib.auth.models import User
from reconciliation.models import Organization, Membership


@pytest.fixture
def org(db):
    return Organization.objects.create(name="Synthetic North")


@pytest.fixture
def other(db):
    return Organization.objects.create(name="Synthetic South")


@pytest.fixture
def user(org):
    user = User.objects.create_user(username="reviewer", password="demo-pass")
    Membership.objects.create(org=org, user=user)
    return user


@pytest.fixture
def imported(org):
    from reconciliation.imports import import_csv

    import_csv(
        org.id, "po", b"vendor,po,line,currency,quantity,unit_price\nAcme,P1,1,USD,10,2.00\n"
    )
    import_csv(org.id, "receipt", b"vendor,po,line,receipt,quantity\nAcme,P1,1,R1,5\n")
    result = import_csv(
        org.id,
        "invoice",
        b"vendor,invoice,po,line,currency,quantity,unit_price\nAcme,I1,P1,1,USD,8,2.50\n",
    )
    return result.invoice_ids[0]
