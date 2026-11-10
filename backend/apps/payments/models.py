"""Payments, provider events and refunds (MTS §10). Each attempt to pay is its own Payment; an order has at
most one success. Every provider callback is stored before it is applied, and stored once."""

import uuid

from django.db import models
from django.db.models import Q


class PaymentState(models.TextChoices):
    CREATED = "created", "Created"
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    NOT_PAID = "not_paid", "Not paid"
    PARTLY_REFUNDED = "partly_refunded", "Partly refunded"
    REFUNDED = "refunded", "Refunded"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=30)
    state = models.CharField(max_length=20, choices=PaymentState.choices, default=PaymentState.CREATED)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="PKR")
    provider_ref = models.CharField(max_length=120, blank=True)
    redirect_url = models.URLField(max_length=500, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    needs_review = models.BooleanField(default=False)  # a conflicting provider event (A-23)
    review_note = models.CharField(max_length=300, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    check_count = models.PositiveIntegerField(default=0)
    next_check_at = models.DateTimeField(null=True, blank=True)
    provider_window_ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(state__in=PaymentState.values), name="payment_state_valid"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=Q(refunded_amount__gte=0) & Q(refunded_amount__lte=models.F("amount")),
                name="payment_refunds_within_amount",
            ),
            # At most one successful payment per order, whatever the code does.
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(state__in=["succeeded", "partly_refunded", "refunded"]),
                name="one_successful_payment_per_order",
            ),
        ]
        indexes = [models.Index(fields=["state", "next_check_at"]), models.Index(fields=["provider", "provider_ref"])]

    def __str__(self) -> str:
        return f"{self.provider}:{self.state}"


class PaymentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=30)
    event_id = models.CharField(max_length=120)
    payment = models.ForeignKey(Payment, null=True, on_delete=models.SET_NULL, related_name="events")
    kind = models.CharField(max_length=40)  # payment.succeeded, payment.failed, refund.succeeded, check
    payload = models.JSONField()
    signature_valid = models.BooleanField()
    outcome = models.CharField(max_length=30, blank=True)  # applied | ignored_backwards | conflict | duplicate …
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [models.UniqueConstraint(fields=["provider", "event_id"], name="payment_event_once")]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"


class RefundState(models.TextChoices):
    REQUESTED = "requested", "Requested"
    APPROVED = "approved", "Approved"
    PROCESSING = "processing", "Processing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed (retrying)"
    MANUAL_REQUIRED = "manual_required", "Manual refund required"
    MANUAL_COMPLETED = "manual_completed", "Paid manually"
    REJECTED = "rejected", "Rejected"


class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="refunds")
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=300)
    state = models.CharField(max_length=20, choices=RefundState.choices, default=RefundState.REQUESTED)
    source = models.CharField(max_length=20, default="staff")  # staff | cancellation | return
    requested_by = models.CharField(max_length=254)
    approved_by = models.CharField(max_length=254, blank=True)
    second_approved_by = models.CharField(max_length=254, blank=True)
    decision_note = models.CharField(max_length=300, blank=True)
    provider_ref = models.CharField(max_length=120, blank=True)
    manual_reference = models.CharField(max_length=120, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(state__in=RefundState.values), name="refund_state_valid"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="refund_amount_positive"),
        ]
        indexes = [models.Index(fields=["state", "next_retry_at"])]

    def __str__(self) -> str:
        return f"{self.order_id}:{self.amount}:{self.state}"
