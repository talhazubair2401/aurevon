"""Return and exchange requests and inspection outcomes (MTS §6 Fulfilment, §11, M13 module)."""

import uuid

from django.db import models
from django.db.models import Q


class ReturnStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    APPROVED = "approved", "Approved: send it back"
    REJECTED = "rejected", "Rejected"
    RECEIVED = "received", "Received"
    INSPECTED = "inspected", "Inspected"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class ReturnKind(models.TextChoices):
    REFUND = "refund", "Refund"
    EXCHANGE = "exchange", "Exchange"


class ReturnRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=24, unique=True)  # R-AV100001-1
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="returns")
    kind = models.CharField(max_length=10, choices=ReturnKind.choices)
    status = models.CharField(max_length=12, choices=ReturnStatus.choices, default=ReturnStatus.REQUESTED)
    reason = models.CharField(max_length=40)  # size | quality | not_as_described | changed_mind | other
    details = models.TextField(blank=True, max_length=1000)
    decision_note = models.CharField(max_length=300, blank=True)
    decided_by = models.CharField(max_length=254, blank=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    exchange_order = models.ForeignKey(
        "orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=ReturnStatus.values), name="return_status_valid"),
            models.CheckConstraint(condition=Q(kind__in=ReturnKind.values), name="return_kind_valid"),
        ]

    def __str__(self) -> str:
        return self.number


class InspectionOutcome(models.TextChoices):
    SELLABLE = "sellable", "Back to sellable stock"
    QUARANTINE = "quarantine", "Needs work or a second check"
    DAMAGED = "damaged", "Damaged"


class ReturnItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey("orders.OrderItem", on_delete=models.PROTECT, related_name="return_items")
    quantity = models.PositiveIntegerField()
    exchange_sku = models.CharField(max_length=40, blank=True)  # the size/colour wanted instead
    outcome = models.CharField(max_length=12, choices=InspectionOutcome.choices, blank=True)
    inspection_note = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=1), name="return_item_quantity_positive")]

    def __str__(self) -> str:
        return f"{self.order_item_id} x{self.quantity}"
