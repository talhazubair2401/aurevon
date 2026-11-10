"""M7/M8 commerce core: cart, checkout, orders, payments, reservations, refunds, coupons and tax, through the API."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.services import Actor
from apps.catalog.models import ProductVariant
from apps.cms.models import StoreSetting
from apps.inventory.models import InventoryItem, ReservationStatus, StockReservation
from apps.localization.models import TaxRule
from apps.notifications.models import StaffAlert
from apps.orders import services as order_services
from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.payments import services as payments
from apps.payments.models import Payment, PaymentEvent, PaymentState, Refund, RefundState
from apps.promotions.models import Coupon, Promotion
from apps.sandbox.models import SandboxPayment
from common.exceptions import ApiProblem
from integrations.payments import SandboxAdapter

pytestmark = pytest.mark.django_db

KARACHI = {
    "full_name": "Ayesha Khan",
    "phone": "0300 1234567",
    "line1": "House 12, Street 4",
    "area": "DHA Phase 6",
    "city": "karachi",
    "province": "sindh",
    "postal_code": "75500",
}
PASSWORD = "silk and linen 2026"


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def sku_with_stock(n: int = 5, skip: int = 0) -> str:
    v = ProductVariant.objects.filter(is_active=True, product__status="published").order_by("sku")[skip]
    InventoryItem.objects.filter(variant=v, location_id="main").update(on_hand=n, reserved=0)
    return v.sku


def stock_of(sku: str) -> tuple[int, int]:
    i = InventoryItem.objects.get(variant__sku=sku, location_id="main")
    return i.on_hand, i.reserved


class Shopper:
    def __init__(self, client: APIClient | None = None) -> None:
        self.c = client or APIClient()
        self.signed_in = False

    def cart(self) -> dict[str, Any]:
        body: dict[str, Any] = self.c.get("/api/v1/cart").json()
        return body

    def write(self, method: str, path: str, data: Any = None, **headers: str) -> Any:
        token = self.c.cookies.get("__Host-av_cart")
        h: dict[str, Any] = dict(headers)
        if token and not self.signed_in:
            h["HTTP_X_CSRF_TOKEN"] = self.cart()["csrf_token"] or ""
        return getattr(self.c, method)(path, data, format="json", **h)

    def add(self, sku: str, qty: int = 1) -> Any:
        return self.write("post", "/api/v1/cart/items", {"sku": sku, "quantity": qty})

    def place(self, payment: str = "cod", key: str | None = None, **extra: Any) -> Any:
        body = {
            "email": "ayesha@example.pk",
            "phone": "03001234567",
            "address": KARACHI,
            "shipping_method": "standard",
            "payment_method": payment,
            **extra,
        }
        return self.write("post", "/api/v1/checkout/orders", body, HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex)


def customer(email: str = "ayesha@example.pk") -> Shopper:
    s = Shopper()
    s.c.post("/api/v1/auth/register", {"email": email, "password": PASSWORD, "full_name": "Ayesha"}, format="json")
    r = s.c.post("/api/v1/auth/login", {"email": email, "password": PASSWORD}, format="json")
    s.c.credentials(HTTP_X_CSRF_TOKEN=r.json()["csrf_token"])
    s.signed_in = True
    return s


# --- Cart ----------------------------------------------------------------------------------------------------


def test_guest_cart_add_update_remove_and_csrf() -> None:
    sku = sku_with_stock(5)
    s = Shopper()
    r = s.add(sku, 2)
    assert r.status_code == 201 and r.json()["count"] == 2 and r.json()["items"][0]["sku"] == sku
    item = r.json()["items"][0]["id"]
    # A second write without the cart's token is refused (the cookie alone isn't enough).
    assert s.c.patch(f"/api/v1/cart/items/{item}", {"quantity": 3}, format="json").status_code == 403
    assert s.write("patch", f"/api/v1/cart/items/{item}", {"quantity": 3}).json()["count"] == 3
    assert s.write("delete", f"/api/v1/cart/items/{item}").json()["count"] == 0
    assert StockReservation.objects.count() == 0  # carts never hold stock


def test_cart_checks_stock_and_limits() -> None:
    sku = sku_with_stock(2)
    s = Shopper()
    assert s.add(sku, 3).json()["type"].endswith("insufficient-stock")
    assert s.add(sku, 11).status_code == 400
    InventoryItem.objects.filter(variant__sku=sku).update(on_hand=0)
    assert s.add(sku).json()["type"].endswith("out-of-stock")
    assert Shopper().add("AV-NOPE").status_code == 404


def test_signing_in_merges_the_guest_cart() -> None:
    sku, other = sku_with_stock(5), sku_with_stock(5, skip=1)
    c = customer()
    c.add(sku, 1)
    guest = Shopper()
    guest.add(other, 2)
    r = guest.c.post("/api/v1/auth/login", {"email": "ayesha@example.pk", "password": PASSWORD}, format="json")
    guest.c.credentials(HTTP_X_CSRF_TOKEN=r.json()["csrf_token"])
    cart = guest.c.get("/api/v1/cart").json()
    assert sorted(i["sku"] for i in cart["items"]) == sorted([sku, other]) and cart["csrf_token"] is None


# --- Quote, COD placement, idempotency, access -----------------------------------------------------------------


def test_quote_uses_zone_rates_and_free_delivery_threshold() -> None:
    sku = sku_with_stock(5)
    s = Shopper()
    s.add(sku)
    q = s.write("post", "/api/v1/checkout/quote", {"address": KARACHI}).json()
    assert q["shipping_method"] == "standard" and {o["method"] for o in q["shipping_options"]} == {
        "standard",
        "express",
    }
    price = Decimal(q["subtotal"]["amount"])
    fee = Decimal(q["shipping_fee"]["amount"])
    assert fee == (0 if price >= 15000 else 250)
    assert Decimal(q["total"]["amount"]) == price + fee
    assert set(q["payment_methods"]) == {"card", "cod"} and q["problems"] == []
    far = {**KARACHI, "city": "Gilgit", "province": "gb"}
    q2 = s.write("post", "/api/v1/checkout/quote", {"address": far, "shipping_method": "express"}).json()
    assert Decimal(q2["shipping_fee"]["amount"]) == 650


def test_cod_order_commits_stock_confirms_and_is_idempotent() -> None:
    sku = sku_with_stock(3)
    s = Shopper()
    s.add(sku, 2)
    key = uuid.uuid4().hex
    r = s.place("cod", key=key)
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["next"] == "confirmed" and body["order"]["status"] == "confirmed"
    assert (
        body["order"]["payment_status"] == "cod_collect"
        and body["order"]["shipping_address"]["phone"] == "+923001234567"
    )
    assert stock_of(sku) == (1, 0)
    assert s.cart()["count"] == 0
    assert "is confirmed" in mail.outbox[-1].subject
    # A double submit returns the same order and changes nothing.
    s.add(sku, 1)
    again = s.place("cod", key=key)
    assert again.status_code in (201, 409)
    assert Order.objects.count() == 1 and stock_of(sku) == (1, 0)
    number = body["order"]["number"]
    assert number.startswith("AV1")
    assert s.c.get(f"/api/v1/orders/{number}").status_code == 200
    assert APIClient().get(f"/api/v1/orders/{number}").status_code == 404  # another browser can't see it


def test_out_of_stock_at_placement_refuses_the_whole_order() -> None:
    sku = sku_with_stock(1)
    a, b = Shopper(), Shopper()
    a.add(sku)
    b.add(sku)
    assert a.place().status_code == 201
    r = b.place()
    body = r.json()
    assert r.status_code == 409 and (body.get("skus") == [sku] or f"{sku}:insufficient" in body.get("problems", []))
    assert Order.objects.count() == 1 and stock_of(sku) == (0, 0)


def test_guest_checkout_can_be_switched_off() -> None:
    StoreSetting.objects.create(key="checkout.guest_allowed", value=False)
    sku = sku_with_stock(2)
    s = Shopper()
    s.add(sku)
    assert s.place().status_code == 401
    c = customer()
    c.add(sku)
    assert c.place().status_code == 201


# --- Online payment ------------------------------------------------------------------------------------------


def _pay_flow(sku: str) -> tuple[Shopper, Order, Payment]:
    s = Shopper()
    s.add(sku, 1)
    r = s.place("card")
    assert r.status_code == 201 and r.json()["next"] == "pay"
    order = Order.objects.get(number=r.json()["order"]["number"])
    assert order.status == OrderStatus.AWAITING_PAYMENT and stock_of(sku)[1] == 1
    start = s.write("post", f"/api/v1/orders/{order.number}/payment-attempts")
    assert start.status_code == 201 and "/api/v1/sandbox/pay/" in start.json()["redirect_url"]
    return s, order, Payment.objects.get(order=order)


def test_card_payment_confirmed_by_signed_callback() -> None:
    sku = sku_with_stock(2)
    s, order, payment = _pay_flow(sku)
    page = s.c.get(f"/api/v1/sandbox/pay/{payment.provider_ref}")
    assert page.status_code == 200 and b"SANDBOX" in page.content
    back = s.c.post(f"/api/v1/sandbox/pay/{payment.provider_ref}", {"outcome": "succeeded"})
    assert back.status_code == 302 and f"order={order.number}" in back["Location"]
    order.refresh_from_db()
    assert (order.status, order.payment_status) == (OrderStatus.CONFIRMED, PaymentStatus.PAID)
    assert stock_of(sku) == (1, 0)
    status = s.c.get(f"/api/v1/orders/{order.number}/payment-status").json()
    assert status == {"order_status": "confirmed", "payment_status": "paid", "attempt": "succeeded"}


def test_webhooks_are_verified_stored_once_and_never_move_backwards() -> None:
    sku = sku_with_stock(2)
    _, order, payment = _pay_flow(sku)
    SandboxPayment.objects.filter(ref=payment.provider_ref).update(state="succeeded")
    body, headers = SandboxAdapter.signed_event(payment.provider_ref, "payment.succeeded")
    hdr: dict[str, Any] = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()}
    url = "/api/v1/webhooks/payments/sandbox"
    assert APIClient().post(url, body, content_type="application/json", **hdr).status_code == 200
    assert APIClient().post(url, body, content_type="application/json", **hdr).status_code == 200  # duplicate
    assert PaymentEvent.objects.filter(provider="sandbox").exclude(kind="check").count() == 1
    bad = APIClient().post(url, body, content_type="application/json", HTTP_X_SANDBOX_SIGNATURE="nope")
    assert bad.status_code == 400
    # "failed" after success is a conflict: flagged and alerted, never applied.
    fail_body, fail_headers = SandboxAdapter.signed_event(payment.provider_ref, "payment.failed")
    fh: dict[str, Any] = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in fail_headers.items()}
    APIClient().post(url, fail_body, content_type="application/json", **fh)
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.state == PaymentState.SUCCEEDED and payment.needs_review and order.payment_status == "paid"
    assert StaffAlert.objects.filter(kind="payment-conflict", severity="critical").exists()


def test_a_lost_callback_is_caught_by_the_status_check() -> None:
    sku = sku_with_stock(2)
    s, order, payment = _pay_flow(sku)
    s.c.post(f"/api/v1/sandbox/pay/{payment.provider_ref}", {"outcome": "silent"})
    order.refresh_from_db()
    assert order.status == OrderStatus.AWAITING_PAYMENT  # no callback arrived
    Payment.objects.filter(pk=payment.pk).update(next_check_at=timezone.now())
    assert payments.check_pending() == 1
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED and order.payment_status == PaymentStatus.PAID


def test_declined_payment_can_be_retried_within_the_reservation() -> None:
    sku = sku_with_stock(2)
    s, order, payment = _pay_flow(sku)
    s.c.post(f"/api/v1/sandbox/pay/{payment.provider_ref}", {"outcome": "failed"})
    payment.refresh_from_db()
    assert payment.state == PaymentState.NOT_PAID
    assert s.write("post", f"/api/v1/orders/{order.number}/payment-attempts").status_code == 201
    assert Payment.objects.filter(order=order).count() == 2


# --- Expiry and late payments ----------------------------------------------------------------------------------


def test_unpaid_orders_expire_and_release_stock() -> None:
    sku = sku_with_stock(2)
    s = Shopper()
    s.add(sku)
    order = Order.objects.get(number=s.place("card").json()["order"]["number"])
    Order.objects.filter(pk=order.pk).update(reservation_expires_at=timezone.now() - timedelta(seconds=1))
    assert order_services.expire_due() == 1
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED and stock_of(sku) == (2, 0)
    assert StockReservation.objects.get(order_id=order.pk).status == ReservationStatus.RELEASED


def test_expiry_waits_while_the_provider_window_is_open() -> None:
    sku = sku_with_stock(2)
    _, order, _payment = _pay_flow(sku)
    Order.objects.filter(pk=order.pk).update(reservation_expires_at=timezone.now() - timedelta(seconds=1))
    order_services.expire_due()
    order.refresh_from_db()
    assert order.status == OrderStatus.AWAITING_PAYMENT
    assert order.reservation_expires_at is not None and order.reservation_expires_at > timezone.now()


def test_late_payment_restores_the_order_when_stock_remains() -> None:
    sku = sku_with_stock(2)
    _, order, payment = _pay_flow(sku)
    order_services.cancel(order.pk, Actor(None, "system"), "Payment wasn't completed in time", expired=True)
    SandboxPayment.objects.filter(ref=payment.provider_ref).update(state="succeeded")
    body, headers = SandboxAdapter.signed_event(payment.provider_ref, "payment.succeeded")
    payments.receive_webhook("sandbox", body, headers)
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED and order.payment_status == PaymentStatus.PAID
    assert stock_of(sku) == (1, 0)
    assert StaffAlert.objects.filter(kind="late-payment-restored").exists()


# --- Refunds -------------------------------------------------------------------------------------------------


def _paid_order(sku: str) -> Order:
    s, order, payment = _pay_flow(sku)
    s.c.post(f"/api/v1/sandbox/pay/{payment.provider_ref}", {"outcome": "succeeded"})
    order.refresh_from_db()
    return order


def test_cancelling_a_paid_order_restores_stock_and_refunds_after_two_approvals() -> None:
    sku = sku_with_stock(2)
    order = _paid_order(sku)
    a, b = Actor(uuid.uuid4(), "admin@aurevon.test"), Actor(uuid.uuid4(), "accounts@aurevon.test")
    order_services.cancel(order.pk, a, "Customer asked to cancel")
    assert stock_of(sku) == (2, 0)
    refund = Refund.objects.get(order=order)
    assert refund.state == RefundState.REQUESTED and refund.source == "cancellation"
    with pytest.raises(ApiProblem):
        payments.approve_refund(refund.pk, a)  # the requester can't approve
    payments.approve_refund(refund.pk, b)  # first approval (no threshold set: two needed)
    refund.refresh_from_db()
    assert refund.state == RefundState.REQUESTED and refund.approved_by == b.label
    payments.approve_refund(refund.pk, Actor(uuid.uuid4(), "owner@aurevon.test"))
    payments.process_refund(refund.pk)  # on_commit doesn't fire inside the test transaction
    refund.refresh_from_db()
    order.refresh_from_db()
    assert refund.state == RefundState.SUCCEEDED and order.payment_status == PaymentStatus.REFUNDED
    assert Payment.objects.get(order=order).state == PaymentState.REFUNDED


def test_failed_refunds_retry_then_need_manual_payment() -> None:
    sku = sku_with_stock(2)
    order = _paid_order(sku)
    StoreSetting.objects.create(
        key="refunds.dual_approval_threshold", value={"amount": "1000000.00", "currency": "PKR"}
    )
    refund = payments.request_refund(order, Decimal("10.13"), "Goodwill", Actor(uuid.uuid4(), "support@aurevon.test"))
    payments.approve_refund(refund.pk, Actor(uuid.uuid4(), "owner@aurevon.test"))
    for _ in range(6):
        Refund.objects.filter(pk=refund.pk).update(next_retry_at=timezone.now())
        payments.process_refund(refund.pk)
    refund.refresh_from_db()
    assert refund.state == RefundState.MANUAL_REQUIRED and StaffAlert.objects.filter(kind="refund-manual").exists()
    payments.complete_manual(refund.pk, "IBFT 98765", Actor(uuid.uuid4(), "accounts@aurevon.test"))
    refund.refresh_from_db()
    assert refund.state == RefundState.MANUAL_COMPLETED


# --- Customers -----------------------------------------------------------------------------------------------


def test_customer_account_addresses_wishlist_and_orders() -> None:
    sku = sku_with_stock(3)
    c = customer()
    assert (
        c.c.patch("/api/v1/me", {"phone": "+92 321 7654321", "full_name": "Ayesha K"}, format="json").json()["phone"]
        == "+923217654321"
    )
    a1 = c.c.post("/api/v1/me/addresses", {**KARACHI, "label": "Home"}, format="json").json()
    a2 = c.c.post(
        "/api/v1/me/addresses", {**KARACHI, "city": "Lahore", "province": "punjab", "make_default": True}, format="json"
    ).json()
    rows = c.c.get("/api/v1/me/addresses").json()
    assert (
        [r["is_default"] for r in rows] == [True, False] and rows[0]["id"] == a2["id"] and rows[1]["city"] == "Karachi"
    )
    assert c.c.post("/api/v1/me/addresses", {**KARACHI, "province": "texas"}, format="json").status_code == 400
    assert c.c.delete(f"/api/v1/me/addresses/{a1['id']}").status_code == 204
    slug = ProductVariant.objects.get(sku=sku).product.slug
    assert c.c.post("/api/v1/me/wishlist", {"slug": slug}, format="json").status_code == 204
    assert [p["slug"] for p in c.c.get("/api/v1/me/wishlist").json()] == [slug]
    c.add(sku)
    number = c.place().json()["order"]["number"]
    assert [o["number"] for o in c.c.get("/api/v1/me/orders").json()] == [number]
    other = customer("someone@example.pk")
    assert other.c.get(f"/api/v1/orders/{number}").status_code == 404
    assert other.c.get("/api/v1/me/orders").json() == []
    assert APIClient().get("/api/v1/me").status_code in (401, 403)


def test_password_change_signs_out_other_sessions() -> None:
    c = customer()
    second = APIClient()
    second.post("/api/v1/auth/login", {"email": "ayesha@example.pk", "password": PASSWORD}, format="json")
    r = c.c.post(
        "/api/v1/me/password", {"current_password": "wrong", "new_password": "a whole new phrase 9"}, format="json"
    )
    assert r.status_code == 400
    r = c.c.post(
        "/api/v1/me/password", {"current_password": PASSWORD, "new_password": "a whole new phrase 9"}, format="json"
    )
    assert r.status_code == 204
    assert second.get("/api/v1/me").status_code in (401, 403)
    assert c.c.get("/api/v1/me").status_code == 200


# --- Coupons, promotions, tax ----------------------------------------------------------------------------------


def test_coupons_apply_once_per_customer_and_promotions_dont_stack() -> None:
    sku = sku_with_stock(5)
    Coupon.objects.create(code="WELCOME10", kind="percent", value=Decimal("10"))
    c = customer()
    c.add(sku)
    assert c.c.post("/api/v1/cart/coupon", {"code": "nope"}, format="json").status_code == 400
    assert c.c.post("/api/v1/cart/coupon", {"code": "welcome10"}, format="json").json()["coupon_code"] == "WELCOME10"
    q = c.c.post("/api/v1/checkout/quote", {"address": KARACHI}, format="json").json()
    subtotal = Decimal(q["subtotal"]["amount"])
    assert (
        Decimal(q["discount"]["amount"]) == (subtotal / 10).quantize(Decimal("0.01"))
        and q["discount_label"] == "WELCOME10"
    )
    order = Order.objects.get(number=c.place().json()["order"]["number"])
    assert order.discount > 0 and Coupon.objects.get(code="WELCOME10").times_used == 1
    c.add(sku)
    assert (
        c.c.post("/api/v1/cart/coupon", {"code": "WELCOME10"}, format="json").json()["type"].endswith("coupon-invalid")
    )
    Promotion.objects.create(name="Winter", label_en="Winter sale", kind="percent", value=Decimal("20"))
    q = c.c.post("/api/v1/checkout/quote", {"address": KARACHI}, format="json").json()
    assert q["discount_label"] == "Winter sale"


def test_tax_rules_inclusive_and_exclusive() -> None:
    sku = sku_with_stock(5)
    s = Shopper()
    s.add(sku)
    base = s.write("post", "/api/v1/checkout/quote", {"address": KARACHI}).json()
    assert base["tax"]["amount"] == "0.00"
    TaxRule.objects.create(
        name="Sales tax", rate=Decimal("0.18"), prices_include_tax=True, effective_from=date(2020, 1, 1)
    )
    inc = s.write("post", "/api/v1/checkout/quote", {"address": KARACHI}).json()
    assert inc["total"] == base["total"] and Decimal(inc["tax"]["amount"]) > 0 and inc["tax_included"]
    TaxRule.objects.create(
        name="Sales tax new", rate=Decimal("0.10"), prices_include_tax=False, effective_from=date(2021, 1, 1)
    )
    exc = s.write("post", "/api/v1/checkout/quote", {"address": KARACHI}).json()
    goods = Decimal(exc["subtotal"]["amount"])
    assert Decimal(exc["tax"]["amount"]) == (goods * Decimal("0.10")).quantize(Decimal("0.01"))
    assert Decimal(exc["total"]["amount"]) == Decimal(base["total"]["amount"]) + Decimal(exc["tax"]["amount"])
