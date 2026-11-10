"""Marketing consent (MTS §6 Communication: ConsentRecord). Newsletter sign-up is double opt-in: a record is
`pending` until the address owner confirms through the emailed link, and only `confirmed` records may be mailed."""

import uuid

from django.db import models
from django.db.models import Q


class ConsentPurpose(models.TextChoices):
    NEWSLETTER = "newsletter", "Newsletter"
    CART_REMINDERS = "cart_reminders", "Reminders about items left in the bag"
    SMS_UPDATES = "sms_updates", "Order updates by SMS"


class ConsentStatus(models.TextChoices):
    PENDING = "pending", "Pending confirmation"
    CONFIRMED = "confirmed", "Confirmed"
    WITHDRAWN = "withdrawn", "Withdrawn"


class ConsentRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    purpose = models.CharField(max_length=20, choices=ConsentPurpose.choices)
    status = models.CharField(max_length=10, choices=ConsentStatus.choices, default=ConsentStatus.PENDING)
    locale = models.CharField(max_length=5, default="en")
    wording_version = models.CharField(max_length=20, help_text="Which consent text the person agreed to")
    source = models.CharField(max_length=40, help_text="Where the sign-up happened, e.g. shop_all")
    confirm_token_hash = models.CharField(max_length=64, blank=True)
    confirm_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["email", "purpose"], name="consent_one_per_email_purpose"),
            models.CheckConstraint(condition=Q(status__in=ConsentStatus.values), name="consent_status_valid"),
            models.CheckConstraint(condition=Q(purpose__in=ConsentPurpose.values), name="consent_purpose_valid"),
        ]
        indexes = [models.Index(fields=["confirm_token_hash"])]

    def __str__(self) -> str:
        return f"{self.purpose}:{self.status}"


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class StaffAlert(models.Model):
    """Operational alerts (MTS §14): payment conflicts, manual refunds, COD discrepancies, low stock …
    Shown on the staff dashboard until resolved; critical ones are also emailed to Owners and Store Admins."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=40)
    severity = models.CharField(max_length=10, choices=AlertSeverity.choices, default=AlertSeverity.WARNING)
    message = models.CharField(max_length=300)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    dedupe_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=254, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["dedupe_key"], condition=Q(resolved_at__isnull=True) & ~Q(dedupe_key=""), name="alert_open_once"
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.message[:40]}"
