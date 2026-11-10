"""Coupons and scheduled promotions (MTS §6 Promotions, M16 at launch: basic coupons). Always evaluated on the
server and recorded against the order."""

import uuid

from django.db import models
from django.db.models import Q


class DiscountKind(models.TextChoices):
    PERCENT = "percent", "Percentage off"
    FIXED = "fixed", "Fixed amount off"


class _Discount(models.Model):
    kind = models.CharField(max_length=10, choices=DiscountKind.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)  # 15.00 = 15 % or Rs 15
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    min_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    categories = models.JSONField(default=list, blank=True)  # category slugs; empty = everything
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=254, blank=True)

    class Meta:
        abstract = True


class Coupon(_Discount):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)  # stored upper-case
    description = models.CharField(max_length=200, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_customer_limit = models.PositiveIntegerField(default=1)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="coupon_value_positive"),
            models.CheckConstraint(condition=Q(kind__in=DiscountKind.values), name="coupon_kind_valid"),
            models.CheckConstraint(condition=~Q(kind="percent") | Q(value__lte=90), name="coupon_percent_at_most_90"),
            models.CheckConstraint(
                condition=Q(usage_limit__isnull=True) | Q(times_used__lte=models.F("usage_limit")),
                name="coupon_usage_within_limit",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class Promotion(_Discount):
    """An automatic, scheduled discount (no code). Coupons and promotions don't stack: the larger one applies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    label_en = models.CharField(max_length=80)
    label_ur = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="promotion_value_positive"),
            models.CheckConstraint(
                condition=~Q(kind="percent") | Q(value__lte=90), name="promotion_percent_at_most_90"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class CouponRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="coupon_redemption")
    account = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    email = models.EmailField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.coupon_id}:{self.order_id}"
