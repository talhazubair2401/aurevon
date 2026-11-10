"""Orders, purchase-time snapshots and status history (MTS §6, §11). Order status and payment status are
separate columns; delivery detail lives on the shipment (A-24)."""

import uuid

from django.db import models
from django.db.models import Q


class OrderStatus(models.TextChoices):
    AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
    CONFIRMED = "confirmed", "Confirmed"
    PACKING = "packing", "Packing"
    DISPATCHED = "dispatched", "Dispatched"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    UNDELIVERED = "undelivered", "Returned undelivered"
    RETURNED = "returned", "Returned"


class PaymentStatus(models.TextChoices):
    UNPAID = "unpaid", "Unpaid"
    PAID = "paid", "Paid"
    PARTLY_REFUNDED = "partly_refunded", "Partly refunded"
    REFUNDED = "refunded", "Refunded"
    # Cash on delivery (MTS §10, A-24): finance states, never inferred from delivery alone.
    COD_COLLECT = "cod_collect", "Collect on delivery"
    COD_REMITTANCE_PENDING = "cod_remittance_pending", "Remittance pending"
    COD_REMITTANCE_RECEIVED = "cod_remittance_received", "Remittance received"
    COD_RECONCILED = "cod_reconciled", "Reconciled"
    COD_DISCREPANCY = "cod_discrepancy", "Discrepancy"
    COD_CANCELLED = "cod_cancelled", "Cancelled (nothing to collect)"


class PaymentMethod(models.TextChoices):
    CARD = "card", "Card or wallet (online)"
    COD = "cod", "Cash on delivery"
    EXCHANGE = "exchange", "Exchange (no charge)"  # replacement sent for a returned item (M12)


CHECKOUT_METHODS = [PaymentMethod.CARD.value, PaymentMethod.COD.value]  # what a customer can choose


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=20, unique=True)  # AV100001, from a database sequence
    account = models.ForeignKey(
        "accounts.Account", null=True, blank=True, on_delete=models.PROTECT, related_name="orders"
    )
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    locale = models.CharField(max_length=5, default="en")
    status = models.CharField(max_length=20, choices=OrderStatus.choices)
    payment_status = models.CharField(max_length=30, choices=PaymentStatus.choices)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    currency = models.CharField(max_length=3, default="PKR")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cod_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_included = models.BooleanField(default=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    coupon_code = models.CharField(max_length=40, blank=True)
    shipping_address = models.JSONField()  # snapshot: name, phone, lines, city, province, postal code
    shipping_zone = models.CharField(max_length=40)
    shipping_method = models.CharField(max_length=12)
    delivery_days = models.CharField(max_length=10, blank=True)  # "2-4"
    access_token_hash = models.CharField(max_length=64)  # lets a guest open their own order
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)
    customer_note = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-placed_at"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=OrderStatus.values), name="order_status_valid"),
            models.CheckConstraint(
                condition=Q(payment_status__in=PaymentStatus.values), name="order_payment_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(payment_method__in=PaymentMethod.values), name="order_payment_method_valid"
            ),
            models.CheckConstraint(condition=Q(total__gte=0) & Q(subtotal__gte=0), name="order_amounts_not_negative"),
        ]
        indexes = [
            models.Index(fields=["status", "placed_at"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return self.number


class OrderItem(models.Model):
    """Snapshot at purchase: later catalogue edits never change what the customer bought or paid (MTS §6)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="+")
    product_slug = models.SlugField(max_length=120)
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=40)
    size = models.CharField(max_length=10)
    colour = models.CharField(max_length=60)
    image_url = models.CharField(max_length=300, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    returned_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_positive"),
            models.CheckConstraint(
                condition=Q(returned_quantity__lte=models.F("quantity")), name="order_item_returns_within_quantity"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sku} x{self.quantity}"


class OrderStatusHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    kind = models.CharField(max_length=10, default="order")  # order | payment
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    actor_label = models.CharField(max_length=254)
    reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status}->{self.to_status}"


class IdempotencyKey(models.Model):
    """A double click or network retry of order placement returns the first result (MTS §11)."""

    key = models.CharField(max_length=80, primary_key=True)
    request_hash = models.CharField(max_length=64)
    order = models.ForeignKey(Order, null=True, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.key
