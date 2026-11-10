"""Stock per variant and location (MTS v2.1 §6 Inventory, §11; M14; decision 0006, #11).

M5 creates one record per variant in the sellable "Main warehouse" and reads availability from it; adjustments,
reservations, returns inspection and purchase orders arrive in M7 and M9. The database refuses negative stock and
over-reservation even if code is wrong (MTS §6). Every change is an immutable StockMovement.
"""

import uuid

from django.db import models
from django.db.models import F, Q


class LocationKind(models.TextChoices):
    SELLABLE = "sellable", "Sellable"
    QUARANTINE = "quarantine", "Quarantine"
    DAMAGED = "damaged", "Damaged"


MAIN_WAREHOUSE = "main"


class StockLocation(models.Model):
    code = models.SlugField(primary_key=True, max_length=40)
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=12, choices=LocationKind.choices)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(kind__in=LocationKind.values), name="location_kind_valid")]

    def __str__(self) -> str:
        return self.code


class InventoryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="stock")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="items")
    on_hand = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["variant", "location"], name="inventory_item_unique"),
            models.CheckConstraint(condition=Q(on_hand__gte=0), name="inventory_on_hand_not_negative"),
            models.CheckConstraint(
                condition=Q(reserved__gte=0) & Q(reserved__lte=F("on_hand")), name="inventory_reserved_within_on_hand"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant_id}@{self.location_id}"


class MovementReason(models.TextChoices):
    RECEIPT = "receipt", "Receipt"
    ADJUSTMENT = "adjustment", "Adjustment"
    DEMO = "demo", "Demo stock (local review only)"
    SALE = "sale", "Sale"
    CANCELLATION = "cancellation", "Cancellation (restored before dispatch)"
    RETURN = "return", "Return to stock"
    QUARANTINE = "quarantine", "Into quarantine"
    RELEASE = "release", "Released from quarantine"
    DAMAGED = "damaged", "Damaged"
    WRITE_OFF = "write_off", "Written off"
    TRANSFER = "transfer", "Transfer between locations"


class StockMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    quantity = models.IntegerField()  # positive in, negative out
    reason = models.CharField(max_length=20, choices=MovementReason.choices)
    note = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=40, blank=True)  # order number, purchase order, return
    actor_label = models.CharField(max_length=254, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(quantity=0), name="movement_not_zero"),
            models.CheckConstraint(condition=Q(reason__in=MovementReason.values), name="movement_reason_valid"),
        ]

    def __str__(self) -> str:
        return f"{self.quantity:+d} {self.reason}"


class ReservationStatus(models.TextChoices):
    ACTIVE = "active", "Holding stock"
    COMMITTED = "committed", "Sold (stock taken)"
    RELEASED = "released", "Released"


class StockReservation(models.Model):
    """Stock held for one order line while it waits for payment (MTS §11). Only sellable stock can be reserved."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="reservations")
    order_id = models.UUIDField(db_index=True)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=ReservationStatus.choices, default=ReservationStatus.ACTIVE)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="reservation_quantity_positive"),
            models.CheckConstraint(condition=Q(status__in=ReservationStatus.values), name="reservation_status_valid"),
        ]
        indexes = [models.Index(fields=["status", "expires_at"])]

    def __str__(self) -> str:
        return f"{self.order_id}:{self.quantity}"
