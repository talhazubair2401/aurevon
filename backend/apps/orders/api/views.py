"""/api/v1/shipping/options, /checkout/quote, /checkout/orders, /orders/{number}, /me/orders (MTS §8).

A guest can open only orders whose access token their browser holds (an HttpOnly cookie set at placement);
a customer only their own orders. Payment endpoints live in apps.payments.api."""

import contextlib
from decimal import Decimal
from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import CustomerAPIView
from apps.accounts.models import Account, CustomerSession
from apps.cart import services as cart_services
from apps.cart.api.views import LOCALE, CartAPIView, MoneyOut
from apps.customers import services as customers
from apps.customers.models import PROVINCE_CODES
from apps.customers.validators import AddressSerializer, normalize_phone
from common.api import money, request_locale
from common.exceptions import ApiProblem
from common.security import constant_time_equal, token_hash

from .. import checkout
from ..models import Order, PaymentMethod

ORDER_COOKIE = "__Host-av_orders"
TAG = ["checkout"]


class ShippingOptionOut(serializers.Serializer[Any]):
    method = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    fee = MoneyOut()
    standard_fee = MoneyOut()
    free_over = MoneyOut(allow_null=True)
    days_min = serializers.IntegerField()
    days_max = serializers.IntegerField()
    cod_allowed = serializers.BooleanField()
    cod_fee = MoneyOut()


class QuoteAddressIn(serializers.Serializer[Any]):
    """A quote only needs where the parcel goes; the full address is checked when the order is placed."""

    city = serializers.CharField(max_length=80)
    province = serializers.ChoiceField(choices=PROVINCE_CODES)

    def validate_city(self, value: str) -> str:
        return value.strip().title()


class QuoteIn(serializers.Serializer[Any]):
    address = QuoteAddressIn(required=False, allow_null=True)
    shipping_method = serializers.CharField(max_length=12, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.values, required=False, allow_null=True)


class QuoteOut(serializers.Serializer[Any]):
    subtotal = MoneyOut()
    discount = MoneyOut()
    discount_label = serializers.CharField(allow_blank=True)
    coupon_error = serializers.CharField(allow_blank=True)
    shipping_fee = MoneyOut()
    cod_fee = MoneyOut()
    tax = MoneyOut()
    tax_included = serializers.BooleanField()
    total = MoneyOut()
    shipping_options = ShippingOptionOut(many=True)
    shipping_method = serializers.CharField(allow_null=True)
    payment_methods = serializers.ListField(child=serializers.CharField())
    problems = serializers.ListField(child=serializers.CharField())
    guest_checkout_allowed = serializers.BooleanField()


class PlaceIn(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254, required=False)
    phone = serializers.CharField(max_length=30)
    address = AddressSerializer()
    shipping_method = serializers.CharField(max_length=12)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.values)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    save_address = serializers.BooleanField(required=False, default=False)

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)


class OrderLineOut(serializers.Serializer[Any]):
    product_slug = serializers.CharField()
    name = serializers.CharField()
    sku = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    image_url = serializers.CharField(allow_blank=True)
    unit_price = MoneyOut()
    quantity = serializers.IntegerField()
    line_total = MoneyOut()


class OrderEventOut(serializers.Serializer[Any]):
    kind = serializers.CharField()
    status = serializers.CharField()
    at = serializers.DateTimeField()


class ShipmentOut(serializers.Serializer[Any]):
    courier = serializers.CharField()
    tracking_number = serializers.CharField(allow_blank=True)
    tracking_url = serializers.CharField(allow_blank=True)
    status = serializers.CharField()


class OrderOut(serializers.Serializer[Any]):
    number = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    payment_method = serializers.CharField()
    placed_at = serializers.DateTimeField()
    email = serializers.EmailField()
    phone = serializers.CharField()
    items = OrderLineOut(many=True)
    subtotal = MoneyOut()
    discount = MoneyOut()
    discount_label = serializers.CharField(allow_blank=True)
    shipping_fee = MoneyOut()
    cod_fee = MoneyOut()
    tax = MoneyOut()
    tax_included = serializers.BooleanField()
    total = MoneyOut()
    shipping_address = serializers.DictField()
    shipping_method = serializers.CharField()
    delivery_days = serializers.CharField()
    pay_by = serializers.DateTimeField(allow_null=True)
    can_pay = serializers.BooleanField()
    can_return = serializers.BooleanField()
    history = OrderEventOut(many=True)
    shipments = ShipmentOut(many=True)


class OrderSummaryOut(serializers.Serializer[Any]):
    number = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    placed_at = serializers.DateTimeField()
    total = MoneyOut()
    item_count = serializers.IntegerField()
    first_image = serializers.CharField(allow_blank=True)


class PlacedOut(serializers.Serializer[Any]):
    order = OrderOut()
    next = serializers.ChoiceField(choices=["pay", "confirmed"])


def _m(amount: Decimal, currency: str = "PKR") -> dict[str, str] | None:
    return money(amount, currency)


def _option(o: Any) -> dict[str, Any]:
    return {
        "method": o.method,
        "label": o.label,
        "fee": _m(o.fee),
        "standard_fee": _m(o.standard_fee),
        "free_over": _m(o.free_over) if o.free_over is not None else None,
        "days_min": o.days_min,
        "days_max": o.days_max,
        "cod_allowed": o.cod_allowed,
        "cod_fee": _m(o.cod_fee),
    }


def order_payload(order: Order) -> dict[str, Any]:
    from apps.orders.models import OrderStatus
    from apps.returns.services import returnable

    c = order.currency
    return {
        "number": order.number,
        "status": order.status,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "placed_at": order.placed_at,
        "email": order.email,
        "phone": order.phone,
        "items": [
            {
                "product_slug": i.product_slug,
                "name": i.name,
                "sku": i.sku,
                "size": i.size,
                "colour": i.colour,
                "image_url": i.image_url,
                "unit_price": _m(i.unit_price, c),
                "quantity": i.quantity,
                "line_total": _m(i.line_total, c),
            }
            for i in order.items.all()
        ],
        "subtotal": _m(order.subtotal, c),
        "discount": _m(order.discount, c),
        "discount_label": order.coupon_code,
        "shipping_fee": _m(order.shipping_fee, c),
        "cod_fee": _m(order.cod_fee, c),
        "tax": _m(order.tax, c),
        "tax_included": order.tax_included,
        "total": _m(order.total, c),
        "shipping_address": order.shipping_address,
        "shipping_method": order.shipping_method,
        "delivery_days": order.delivery_days,
        "pay_by": order.reservation_expires_at if order.payment_method == PaymentMethod.CARD else None,
        "can_pay": order.status == OrderStatus.AWAITING_PAYMENT and order.payment_method == PaymentMethod.CARD,
        "can_return": returnable(order),
        "history": [{"kind": h.kind, "status": h.to_status, "at": h.created_at} for h in order.history.all()],
        "shipments": [
            {
                "courier": s.courier,
                "tracking_number": s.tracking_number,
                "tracking_url": s.tracking_url,
                "status": s.status,
            }
            for s in order.shipments.all()
        ],
    }


def _guest_tokens(request: Request) -> dict[str, str]:
    raw = request.COOKIES.get(ORDER_COOKIE, "")
    pairs = (p.split(":", 1) for p in raw.split("|") if ":" in p)
    return dict(pairs)


def set_order_cookie(request: Request, response: Response, number: str, token: str) -> None:
    tokens = _guest_tokens(request)
    tokens[number] = token
    value = "|".join(f"{n}:{t}" for n, t in list(tokens.items())[-5:])
    response.set_cookie(ORDER_COOKIE, value, max_age=90 * 86400, path="/", secure=True, httponly=True, samesite="Lax")


def find_order(request: Request, number: str) -> Order:
    """The caller's own order: by customer account, or by the guest token cookie. Anything else is 404."""
    order = Order.objects.filter(number=number).prefetch_related("items", "history", "shipments").first()
    if order is not None:
        account = request.user if isinstance(request.auth, CustomerSession) else None
        if isinstance(account, Account) and order.account_id == account.pk:
            return order
        token = _guest_tokens(request).get(number)
        if token and constant_time_equal(token_hash(token), order.access_token_hash):
            return order
    raise ApiProblem(404, "not-found", "We couldn't find this order.")


def _valid(cls: type[serializers.Serializer[Any]], request: Request) -> dict[str, Any]:
    s = cls(data=request.data)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


class ShippingOptionsView(CartAPIView):
    @extend_schema(
        tags=TAG,
        parameters=[OpenApiParameter("city", str, required=True), OpenApiParameter("province", str, required=True)],
        responses={200: ShippingOptionOut(many=True)},
        operation_id="shipping_options",
    )
    def get(self, request: Request) -> Response:
        from apps.shipping import services as shipping

        city = request.query_params.get("city", "")[:80]
        province = request.query_params.get("province", "")[:12]
        subtotal = (
            sum((ln.line_total for ln in cart_services.lines(self.cart)), Decimal("0")) if self.cart else Decimal("0")
        )
        return Response([_option(o) for o in shipping.options(city, province, subtotal)])


class QuoteView(CartAPIView):
    @extend_schema(
        tags=TAG, parameters=LOCALE, request=QuoteIn, responses={200: QuoteOut}, operation_id="checkout_quote"
    )
    def post(self, request: Request) -> Response:
        from apps.cms.services import get_value

        data = _valid(QuoteIn, request)
        if self.cart is None:
            raise ApiProblem(409, "cart-empty", "Your bag is empty.")
        q = checkout.quote(
            self.cart,
            data.get("address"),
            data.get("shipping_method") or None,
            data.get("payment_method"),
            self.customer,
            request_locale(request),
        )
        return Response(
            {
                "subtotal": _m(q.subtotal),
                "discount": _m(q.discount),
                "discount_label": q.discount_label,
                "coupon_error": q.coupon_error,
                "shipping_fee": _m(q.shipping_fee),
                "cod_fee": _m(q.cod_fee),
                "tax": _m(q.tax),
                "tax_included": q.tax_included,
                "total": _m(q.total),
                "shipping_options": [_option(o) for o in q.options],
                "shipping_method": q.option.method if q.option else None,
                "payment_methods": q.payment_methods,
                "problems": q.problems,
                "guest_checkout_allowed": bool(get_value("checkout.guest_allowed")),
            }
        )


class PlaceOrderView(CartAPIView):
    @extend_schema(
        tags=TAG,
        parameters=[*LOCALE, OpenApiParameter("Idempotency-Key", str, location="header", required=True)],
        request=PlaceIn,
        responses={201: PlacedOut},
        operation_id="checkout_place_order",
    )
    def post(self, request: Request) -> Response:
        key = request.headers.get("Idempotency-Key", "")
        if not 16 <= len(key) <= 80:
            raise ApiProblem(400, "idempotency-key-required", "Send an Idempotency-Key header (16 to 80 characters).")
        data = _valid(PlaceIn, request)
        if self.cart is None:
            raise ApiProblem(409, "cart-empty", "Your bag is empty.")
        email = self.customer.email if self.customer else data.get("email")
        if not email:
            raise ApiProblem(400, "email-required", "Enter your email address.")
        address = dict(data["address"])
        placed = checkout.place(
            self.cart,
            account=self.customer,
            email=email,
            phone=data["phone"],
            address=address,
            method=data["shipping_method"],
            payment_method=data["payment_method"],
            idempotency_key=key,
            locale=request_locale(request),
            note=data["note"],
        )
        if self.customer and data["save_address"]:
            with contextlib.suppress(ApiProblem):  # the order is placed; saving the address is a convenience
                customers.add_address(self.customer, address)
        order = Order.objects.prefetch_related("items", "history", "shipments").get(pk=placed.order.pk)
        response = Response(
            {
                "order": order_payload(order),
                "next": "pay" if order.payment_method == PaymentMethod.CARD else "confirmed",
            },
            status=201,
        )
        if placed.access_token:
            set_order_cookie(request, response, order.number, placed.access_token)
        return response


class OrderView(CartAPIView):
    @extend_schema(tags=["orders"], responses={200: OrderOut}, operation_id="order_get")
    def get(self, request: Request, number: str) -> Response:
        return Response(order_payload(find_order(request, number)))


class MyOrdersView(CustomerAPIView):
    @extend_schema(tags=["customer account"], responses={200: OrderSummaryOut(many=True)}, operation_id="me_orders")
    def get(self, request: Request) -> Response:
        rows = Order.objects.filter(account=self.account).prefetch_related("items")[:100]
        return Response(
            [
                {
                    "number": o.number,
                    "status": o.status,
                    "payment_status": o.payment_status,
                    "placed_at": o.placed_at,
                    "total": _m(o.total, o.currency),
                    "item_count": sum(i.quantity for i in o.items.all()),
                    "first_image": next((i.image_url for i in o.items.all() if i.image_url), ""),
                }
                for o in rows
            ]
        )
