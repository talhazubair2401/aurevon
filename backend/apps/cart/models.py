"""Carts for guests (cookie) and customers (MTS §6 Commerce). Carts never hold stock: availability is checked
when items are added and again, with the rows locked, when the order is placed (MTS §11)."""

import uuid

from django.db import models
from django.db.models import Q


class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.OneToOneField(
        "accounts.Account", null=True, blank=True, on_delete=models.CASCADE, related_name="cart"
    )
    token_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)  # guests only
    csrf_token = models.CharField(max_length=64)
    coupon_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Abandoned-cart reminders (M11): set when a consented reminder is sent, cleared on any change.
    reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(account__isnull=False) | Q(token_hash__isnull=False), name="cart_has_owner"
            )
        ]

    def __str__(self) -> str:
        return str(self.pk)


class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="cart_item_unique"),
            models.CheckConstraint(condition=Q(quantity__gte=1, quantity__lte=10), name="cart_item_quantity_range"),
        ]

    def __str__(self) -> str:
        return f"{self.variant_id} x{self.quantity}"
