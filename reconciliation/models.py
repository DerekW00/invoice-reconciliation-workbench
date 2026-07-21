from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=120)
    revision = models.PositiveIntegerField(default=0)


class Membership(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class ImportBatch(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    kind = models.CharField(max_length=12)
    digest = models.CharField(max_length=64)
    row_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "kind", "digest"], name="batch_digest")
        ]


class PurchaseOrderLine(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    vendor = models.CharField(max_length=100)
    po = models.CharField(max_length=100)
    line = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "vendor", "po", "line"], name="po_key")
        ]


class Receipt(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    vendor = models.CharField(max_length=100)
    po = models.CharField(max_length=100)
    line = models.CharField(max_length=100)
    receipt = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "vendor", "po", "line", "receipt"], name="receipt_key"
            )
        ]


class Invoice(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    vendor = models.CharField(max_length=100)
    number = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64)
    revision = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, default="review")
    approved_snapshot = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "vendor", "number"], name="invoice_key")
        ]


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    po = models.CharField(max_length=100)
    line = models.CharField(max_length=100)
    currency = models.CharField(max_length=3)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invoice", "po", "line"], name="invoice_line_key")
        ]


class ReconciliationVersion(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="versions", on_delete=models.CASCADE)
    revision = models.PositiveIntegerField()
    source_revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["invoice", "revision"], name="version_revision")
        ]


class Exception(models.Model):
    version = models.ForeignKey(
        ReconciliationVersion, related_name="exceptions", on_delete=models.CASCADE
    )
    code = models.CharField(max_length=30)
    line = models.CharField(max_length=100)
    facts = models.JSONField()


class Resolution(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    version = models.ForeignKey(ReconciliationVersion, on_delete=models.CASCADE)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Audit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    invoice = models.ForeignKey(Invoice, related_name="audit", on_delete=models.CASCADE)
    revision = models.PositiveIntegerField()
    action = models.CharField(max_length=30)
    note = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)


class Job(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE)
    version = models.ForeignKey(ReconciliationVersion, on_delete=models.CASCADE)
    status = models.CharField(max_length=12, default="queued")
    token = models.CharField(max_length=64, default="")
    lease_until = models.DateTimeField(null=True)
    deadline = models.DateTimeField()
    result = models.JSONField(null=True)
    usage = models.JSONField(default=dict)
    guard_units = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class JobEvent(models.Model):
    job = models.ForeignKey(Job, related_name="events", on_delete=models.CASCADE)
    kind = models.CharField(max_length=30)
    detail = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
