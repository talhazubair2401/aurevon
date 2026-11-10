"""Price quotes and the order-placement transaction (MTS §11). Every amount is recalculated on the server (A-15);
nothing the browser sends about prices is trusted."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.cart import services as carts
from apps.cart.models import Cart
from apps.cms.services import get_value
from apps.inventory import services as stock
from apps.localization import services as tax
from apps.shipping import services as shipping
from common.exceptions import ApiProblem
from common.security import new_token, token_hash

from . import services
from .models import IdempotencyKey, Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus

ZERO = Decimal("0.00")


@dataclass
class Quote:
    lines: list[carts.Line]
    subtotal: Decimal
    discount: Decimal
    shipping_fee: Decimal
    cod_fee: Decimal
    tax: Decimal
    tax_included: bool
    total: Decimal
    option: shipping.Option | None
    options: list[shipping.Option]
    payment_methods: list[str]
    coupon_code: str = ""
    coupon_error: str = ""
    discount_label: str = ""
    problems: list[str] = field(default_factory=list)


def payment_methods(goods_total: Decimal, option: shipping.Option | None) -> list[str]:
    from integrations import payments as adapters

    methods = []
    if adapters.online_adapter() is not None:
        methods.append(PaymentMethod.CARD.value)
    if get_value("payments.cod_enabled") and (option is None or option.cod_allowed):
        limit = get_value("payments.cod_max_order")
        if limit is None or goods_total <= Decimal(limit["amount"]):
            methods.append(PaymentMethod.COD.value)
    return methods


def quote(
    cart: Cart,
    address: dict[str, Any] | None,
    method: str | None,
    payment_method: str | None,
    account: Account | None,
    locale: str = "en",
) -> Quote:
    from apps.promotions import services as promotions

    lines = carts.lines(cart, locale)
    problems = [f"{ln.variant.sku}:{ln.problem}" for ln in lines if ln.problem]
    if not lines:
        problems.append("empty")
    subtotal = sum((ln.line_total for ln in lines), ZERO)
    result = promotions.evaluate(cart.coupon_code, lines, subtotal, account, email=None)
    discount, coupon_error, discount_label = result.discount, result.error, result.label
    goods = subtotal - discount
    options: list[shipping.Option] = []
    option = None
    if address:
        options = shipping.options(address["city"], address["province"], goods)
        if not options:
            problems.append("no-delivery")
        elif method:
            option = next((o for o in options if o.method == method), None)
            if option is None:
                problems.append("shipping-method")
        else:
            option = options[0]
    shipping_fee = option.fee if option else ZERO
    methods = payment_methods(goods, option)
    cod_fee = option.cod_fee if (option and payment_method == PaymentMethod.COD) else ZERO
    if payment_method and payment_method not in methods:
        problems.append("payment-method")
    t = tax.compute(goods, shipping_fee + cod_fee)
    total = goods + shipping_fee + cod_fee + (ZERO if t.included else t.amount)
    return Quote(
        lines,
        subtotal,
        discount,
        shipping_fee,
        cod_fee,
        t.amount,
        t.included,
        total,
        option,
        options,
        methods,
        cart.coupon_code,
        coupon_error,
        discount_label,
        problems,
    )


def _request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class Placed:
    order: Order
    access_token: str | None  # only on first placement; a replay returns None


def place(
    cart: Cart,
    *,
    account: Account | None,
    email: str,
    phone: str,
    address: dict[str, Any],
    method: str,
    payment_method: str,
    idempotency_key: str,
    locale: str,
    note: str = "",
) -> Placed:
    """MTS §11 steps 1 to 5 in one transaction: validate, re-price, lock and reserve, create the order with
    snapshots and history, then commit. The payment provider is only called afterwards."""
    if account is None and not get_value("checkout.guest_allowed"):
        raise ApiProblem(401, "sign-in-required", "Sign in or create an account to check out.")
    request_hash = _request_hash(
        {"cart": str(cart.pk), "email": email, "address": address, "method": method, "pay": payment_method}
    )
    existing = IdempotencyKey.objects.filter(key=idempotency_key).select_related("order").first()
    if existing:
        if existing.request_hash != request_hash or existing.order is None:
            raise ApiProblem(409, "idempotency-conflict", "This checkout was already submitted with different details.")
        return Placed(existing.order, None)
    try:
        with transaction.atomic():
            IdempotencyKey.objects.create(key=idempotency_key, request_hash=request_hash)
            q = quote(cart, address, method, payment_method, account, locale)
            if q.coupon_error:
                raise ApiProblem(409, "coupon-invalid", q.coupon_error)
            if q.problems:
                raise ApiProblem(409, "checkout-blocked", "Please review your bag and details.", problems=q.problems)
            if q.option is None:  # pragma: no cover - quote() reports a problem first
                raise ApiProblem(409, "checkout-blocked", "Choose a delivery option.")
            cod = payment_method == PaymentMethod.COD
            token = new_token()
            minutes = int(get_value("checkout.reservation_minutes"))
            expires = None if cod else timezone.now() + timedelta(minutes=minutes)
            order = Order.objects.create(
                number=services.next_number(),
                account=account,
                email=email.strip().lower(),
                phone=phone,
                locale=locale,
                status=OrderStatus.AWAITING_PAYMENT,
                payment_status=PaymentStatus.COD_COLLECT if cod else PaymentStatus.UNPAID,
                payment_method=payment_method,
                subtotal=q.subtotal,
                discount=q.discount,
                shipping_fee=q.shipping_fee,
                cod_fee=q.cod_fee,
                tax=q.tax,
                tax_included=q.tax_included,
                total=q.total,
                coupon_code=q.discount_label if q.discount else "",
                shipping_address=address,
                shipping_zone=q.option.zone,
                shipping_method=q.option.method,
                delivery_days=f"{q.option.days_min}-{q.option.days_max}",
                access_token_hash=token_hash(token),
                reservation_expires_at=expires,
                customer_note=note[:300],
            )
            for ln in q.lines:
                v = ln.variant
                image = next(
                    (
                        i
                        for i in v.product.images.all()
                        if i.colour_slug in ("", v.colour.slug) and (i.thumb_url or i.url)
                    ),
                    None,
                )
                OrderItem.objects.create(
                    order=order,
                    variant=v,
                    product_slug=v.product.slug,
                    name=ln.name,
                    sku=v.sku,
                    size=v.size,
                    colour=v.colour.name_en,
                    image_url=(image.thumb_url or image.url) if image else "",
                    unit_price=v.price,
                    quantity=ln.item.quantity,
                    line_total=ln.line_total,
                )
            services.history(
                order,
                OrderStatus.AWAITING_PAYMENT,
                account.email if account else f"guest {order.email}",
                "Order placed",
            )
            lines_by_variant: dict[Any, int] = {}
            for ln in q.lines:
                lines_by_variant[ln.variant.pk] = lines_by_variant.get(ln.variant.pk, 0) + ln.item.quantity
            try:
                stock.reserve(
                    order.pk, order.number, lines_by_variant, expires or timezone.now() + timedelta(days=3650)
                )
            except stock.OutOfStock as exc:
                short = [ln.variant.sku for ln in q.lines if ln.variant.pk in exc.shortages]
                raise ApiProblem(
                    409, "out-of-stock", "Some items sold out while you were checking out.", skus=short
                ) from exc
            if q.discount and q.discount_label == q.coupon_code.strip().upper():
                from apps.promotions import services as promotions

                promotions.redeem(q.discount_label, order, account)
            IdempotencyKey.objects.filter(key=idempotency_key).update(order=order)
            if cod:
                # COD is accepted at once: stock committed, order confirmed (MTS §11, §10 A-24).
                stock.commit(order.pk, order.number)
                services._move(order, OrderStatus.CONFIRMED, "system", "Cash on delivery order accepted")
                services._email(order, "order_confirmed", paid=False)
            else:
                services._email(order, "order_awaiting_payment", minutes=minutes)
            carts.clear(cart)
    except IntegrityError as exc:
        raise ApiProblem(409, "idempotency-conflict", "This checkout is already being processed.") from exc
    return Placed(order, token)
