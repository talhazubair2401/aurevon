"""Discount evaluation (server-side only, A-15) and redemption."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from common.exceptions import ApiProblem

from .models import Coupon, CouponRedemption, DiscountKind, Promotion

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


@dataclass
class Result:
    discount: Decimal
    error: str = ""
    label: str = ""
    coupon: Coupon | None = None


def _live(qs: Any) -> Any:
    now = timezone.now()
    return (
        qs.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    )


def _amount(d: Coupon | Promotion, lines: list[Any]) -> Decimal:
    eligible = sum(
        (ln.line_total for ln in lines if not d.categories or ln.variant.product.category.slug in d.categories), ZERO
    )
    if eligible <= 0:
        return ZERO
    if d.kind == DiscountKind.PERCENT:
        amount = (eligible * d.value / 100).quantize(CENT, ROUND_HALF_UP)
    else:
        amount = min(d.value, eligible)
    if d.max_discount is not None:
        amount = min(amount, d.max_discount)
    return amount


def best_promotion(lines: list[Any], subtotal: Decimal) -> tuple[Decimal, str]:
    best, label = ZERO, ""
    for p in _live(Promotion.objects.all()):
        if subtotal < p.min_subtotal:
            continue
        amount = _amount(p, lines)
        if amount > best:
            best, label = amount, p.label_en
    return best, label


def find_coupon(code: str) -> Coupon | None:
    found: Coupon | None = _live(Coupon.objects.filter(code=code.strip().upper())).first()
    return found


def evaluate(code: str, lines: list[Any], subtotal: Decimal, account: Any, email: str | None) -> Result:
    promo, promo_label = best_promotion(lines, subtotal)
    if not code:
        return Result(promo, label=promo_label)
    coupon = find_coupon(code)
    if coupon is None:
        return Result(promo, "This code isn't valid or has expired.", promo_label)
    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        return Result(promo, "This code has been fully used.", promo_label)
    if subtotal < coupon.min_subtotal:
        return Result(promo, f"This code needs a bag of at least Rs {coupon.min_subtotal:,.0f}.", promo_label)
    if account is not None:
        used = CouponRedemption.objects.filter(coupon=coupon, account=account).count()
        if used >= coupon.per_customer_limit:
            return Result(promo, "You've already used this code.", promo_label)
    amount = _amount(coupon, lines)
    if amount <= 0:
        return Result(promo, "This code doesn't apply to the items in your bag.", promo_label)
    if promo > amount:
        return Result(promo, "", promo_label)  # no stacking: the larger discount applies
    return Result(amount, "", coupon.code, coupon)


@transaction.atomic
def redeem(code: str, order: Any, account: Any) -> None:
    coupon = Coupon.objects.select_for_update().filter(code=code).first()
    if coupon is None:
        return  # the discount came from an automatic promotion
    if account is None:
        used = CouponRedemption.objects.filter(coupon=coupon, email=order.email).count()
        if used >= coupon.per_customer_limit:
            raise ApiProblem(409, "coupon-invalid", "This code has already been used with this email address.")
    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        raise ApiProblem(409, "coupon-invalid", "This code has been fully used.")
    Coupon.objects.filter(pk=coupon.pk).update(times_used=F("times_used") + 1)
    CouponRedemption.objects.create(
        coupon=coupon, order=order, account=account, email=order.email, amount=order.discount
    )
