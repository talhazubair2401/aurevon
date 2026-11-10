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
    # Low-stock alert when available sellable stock falls to this (0: no alert). Main warehouse only (M9).
    reorder_level = models.PositiveIntegerField(default=0)
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


class Supplier(models.Model):
    """Who AureVon buys stock from (M9)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    contact_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=300, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent to supplier"
    PARTLY_RECEIVED = "partly_received", "Partly received"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=20, unique=True)  # PO-000001
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=16, choices=PurchaseOrderStatus.choices, default=PurchaseOrderStatus.DRAFT)
    expected_on = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_by = models.CharField(max_length=254)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=PurchaseOrderStatus.values), name="po_status_valid")
        ]

    def __str__(self) -> str:
        return self.number


class PurchaseOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="+")
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity_ordered__gte=1), name="po_line_quantity_positive"),
            models.CheckConstraint(
                condition=Q(quantity_received__lte=F("quantity_ordered")), name="po_line_not_over_received"
            ),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="po_line_cost_not_negative"),
            models.UniqueConstraint(fields=["purchase_order", "variant"], name="po_line_variant_once"),
        ]

    def __str__(self) -> str:
        return f"{self.variant_id} x{self.quantity_ordered}"
