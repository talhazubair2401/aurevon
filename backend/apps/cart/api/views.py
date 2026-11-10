"""/api/v1/cart: the bag, for guests (an HttpOnly cookie) and signed-in customers (their account).

Guests' writes carry the cart's own CSRF token in X-CSRF-Token; customers' writes are covered by the customer
session's CSRF check. All bodies are JSON only, so cross-site forms can't post here at all."""

from decimal import Decimal
from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SAFE_METHODS, CustomerSessionAuthentication
from apps.accounts.models import Account, CustomerSession
from apps.accounts.services import sessions
from common.api import money, request_locale
from common.exceptions import ApiProblem
from common.security import constant_time_equal

from .. import services
from ..models import Cart

CART_COOKIE = "__Host-av_cart"
CART_DAYS = 30
TAG = ["cart"]


class MoneyOut(serializers.Serializer[Any]):
    amount = serializers.CharField()
    currency = serializers.CharField()


class CartLineOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    product_slug = serializers.CharField()
    name = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.DictField()
    image = serializers.DictField(allow_null=True)
    unit_price = MoneyOut()
    quantity = serializers.IntegerField()
    line_total = MoneyOut()
    available = serializers.IntegerField()
    problem = serializers.CharField(allow_null=True)


class CartOut(serializers.Serializer[Any]):
    id = serializers.UUIDField(allow_null=True)
    csrf_token = serializers.CharField(allow_null=True, help_text="Guests send this as X-CSRF-Token on writes.")
    items = CartLineOut(many=True)
    count = serializers.IntegerField()
    subtotal = MoneyOut()
    coupon_code = serializers.CharField(allow_blank=True)


class AddIn(serializers.Serializer[Any]):
    sku = serializers.CharField(max_length=40)
    quantity = serializers.IntegerField(min_value=1, max_value=services.MAX_PER_LINE, default=1)


class QuantityIn(serializers.Serializer[Any]):
    quantity = serializers.IntegerField(min_value=1, max_value=services.MAX_PER_LINE)


class CouponIn(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=40)


def set_cart_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CART_COOKIE, token, max_age=CART_DAYS * 86400, path="/", secure=True, httponly=True, samesite="Lax"
    )


def cart_payload(cart: Cart | None, locale: str, guest: bool) -> dict[str, Any]:
    if cart is None:
        return {"id": None, "csrf_token": None, "items": [], "count": 0, "subtotal": money(0, "PKR"), "coupon_code": ""}
    lines = services.lines(cart, locale)
    items = []
    for ln in lines:
        v = ln.variant
        image = next((i for i in v.product.images.all() if i.colour_slug in ("", v.colour.slug)), None)
        items.append(
            {
                "id": ln.item.pk,
                "sku": v.sku,
                "product_slug": v.product.slug,
                "name": ln.name,
                "size": v.size,
                "colour": {
                    "slug": v.colour.slug,
                    "name": v.colour.name_ur if locale == "ur" and v.colour.name_ur else v.colour.name_en,
                    "hex": v.colour.hex,
                },
                "image": None
                if image is None
                else {
                    "url": image.thumb_url or image.url or None,
                    "demo_art": image.demo_art or None,
                    "tone": v.colour.hex,
                },
                "unit_price": money(v.price, v.currency),
                "quantity": ln.item.quantity,
                "line_total": money(ln.line_total, v.currency),
                "available": ln.available,
                "problem": ln.problem,
            }
        )
    return {
        "id": cart.pk,
        "csrf_token": cart.csrf_token if guest else None,
        "items": items,
        "count": sum(i["quantity"] for i in items),
        "subtotal": money(sum((ln.line_total for ln in lines), 0), "PKR"),
        "coupon_code": cart.coupon_code,
    }


class CartAPIView(APIView):
    """Resolves the current cart: the customer's (merging any guest cart once) or the guest's cookie cart."""

    authentication_classes = [CustomerSessionAuthentication]
    permission_classes = [AllowAny]

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        self._new_token: str | None = None
        self._drop_cookie = False
        account = request.user if isinstance(request.auth, CustomerSession) else None
        self.customer: Account | None = account if isinstance(account, Account) else None
        token = request.COOKIES.get(CART_COOKIE)
        guest = services.for_guest(token)
        if self.customer is not None:
            if guest is not None:
                services.merge_guest_into(self.customer, guest)
            self._drop_cookie = bool(token)
            self.cart: Cart | None = services.for_account(self.customer, create=False)
        else:
            self.cart = guest
            if guest is not None and request.method not in SAFE_METHODS:
                supplied = str(request.META.get("HTTP_X_CSRF_TOKEN", ""))
                if not supplied or not constant_time_equal(supplied, guest.csrf_token):
                    raise ApiProblem(403, "csrf-failed", "The request is missing a valid X-CSRF-Token header.")

    def ensure_cart(self) -> Cart:
        if self.cart is None:
            if self.customer is not None:
                self.cart = services.for_account(self.customer, create=True)
            else:
                self.cart, self._new_token = services.new_guest_cart()
        if self.cart is None:  # pragma: no cover - for_account(create=True) always returns one
            raise ApiProblem(403, "customers-only", "Only customer accounts have a bag.")
        return self.cart

    def respond(self, request: Request, status: int = 200) -> Response:
        return Response(cart_payload(self.cart, request_locale(request), self.customer is None), status=status)

    def finalize_response(self, request: Request, response: Response, *args: Any, **kwargs: Any) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        if getattr(self, "_new_token", None):
            set_cart_cookie(response, self._new_token)  # type: ignore[arg-type]
        elif getattr(self, "_drop_cookie", False):
            response.delete_cookie(CART_COOKIE, path="/", samesite="Lax")
        token = getattr(request, "_customer_token", None)
        if token and isinstance(request.auth, CustomerSession):
            sessions.refresh_customer_cookie(response, request.auth, token)
        return response


LOCALE = [OpenApiParameter("locale", str, enum=["en", "ur"])]


def _valid(cls: type[serializers.Serializer[Any]], request: Request) -> dict[str, Any]:
    s = cls(data=request.data)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


class CartView(CartAPIView):
    @extend_schema(tags=TAG, parameters=LOCALE, responses={200: CartOut}, operation_id="cart_get")
    def get(self, request: Request) -> Response:
        return self.respond(request)


class CartItemsView(CartAPIView):
    @extend_schema(tags=TAG, parameters=LOCALE, request=AddIn, responses={201: CartOut}, operation_id="cart_add")
    def post(self, request: Request) -> Response:
        data = _valid(AddIn, request)
        services.add(self.ensure_cart(), data["sku"], data["quantity"])
        return self.respond(request, 201)


class CartItemView(CartAPIView):
    @extend_schema(
        tags=TAG, parameters=LOCALE, request=QuantityIn, responses={200: CartOut}, operation_id="cart_update"
    )
    def patch(self, request: Request, item_id: str) -> Response:
        if self.cart is None:
            raise ApiProblem(404, "not-found", "Your bag is empty.")
        services.set_quantity(self.cart, item_id, _valid(QuantityIn, request)["quantity"])
        return self.respond(request)

    @extend_schema(tags=TAG, parameters=LOCALE, responses={200: CartOut}, operation_id="cart_remove")
    def delete(self, request: Request, item_id: str) -> Response:
        if self.cart is not None:
            services.remove(self.cart, item_id)
        return self.respond(request)


class CartCouponView(CartAPIView):
    @extend_schema(
        tags=TAG, parameters=LOCALE, request=CouponIn, responses={200: CartOut}, operation_id="cart_coupon_apply"
    )
    def post(self, request: Request) -> Response:
        from apps.promotions import services as promotions

        cart = self.ensure_cart()
        code = _valid(CouponIn, request)["code"].strip().upper()
        lines = services.lines(cart)
        subtotal = sum((ln.line_total for ln in lines), Decimal("0"))
        result = promotions.evaluate(code, lines, subtotal, self.customer, None)
        if result.error:
            raise ApiProblem(400, "coupon-invalid", result.error)
        cart.coupon_code = code
        cart.save(update_fields=["coupon_code", "updated_at"])
        return self.respond(request)

    @extend_schema(tags=TAG, parameters=LOCALE, responses={200: CartOut}, operation_id="cart_coupon_remove")
    def delete(self, request: Request) -> Response:
        if self.cart is not None:
            self.cart.coupon_code = ""
            self.cart.save(update_fields=["coupon_code", "updated_at"])
        return self.respond(request)
