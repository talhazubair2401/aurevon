"""M12 returns and exchanges, end to end through the customer and staff APIs: request, decide, receive, inspect
into stock locations, then refund (through the normal approval rules) or exchange (a no-charge order)."""

from datetime import timedelta
from typing import Any

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffSession
from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in, step_up
from apps.audit.models import AuditLog
from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryItem
from apps.orders.models import Order, OrderStatus, PaymentMethod
from apps.orders.tests.test_commerce import Shopper, sku_with_stock
from apps.payments.models import Refund, RefundState

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def sibling_sku(sku: str) -> str:
    v = ProductVariant.objects.get(sku=sku)
    other = ProductVariant.objects.filter(product=v.product, is_active=True).exclude(sku=sku).order_by("sku").first()
    assert other is not None
    InventoryItem.objects.filter(variant=other, location_id="main").update(on_hand=5, reserved=0)
    return other.sku


def delivered_order(qty: int = 2) -> tuple[Shopper, Order, str]:
    sku = sku_with_stock(5)
    s = Shopper()
    s.add(sku, qty)
    r = s.place("cod")
    assert r.status_code == 201, r.content
    order = Order.objects.get(number=r.json()["order"]["number"])
    Order.objects.filter(pk=order.pk).update(status=OrderStatus.DELIVERED, delivered_at=timezone.now())
    order.refresh_from_db()
    return s, order, sku


def on_hand(sku: str, location: str = "main") -> int:
    item = InventoryItem.objects.filter(variant__sku=sku, location_id=location).first()
    return item.on_hand if item else 0


def test_customer_can_request_within_the_window_only() -> None:
    s, order, sku = delivered_order()
    url = f"/api/v1/orders/{order.number}/returns"
    info = s.c.get(url).json()
    assert info["can_return"] and info["window_days"] == 7 and info["items"][0]["available"] == 2
    assert APIClient().get(url).status_code == 404  # someone else's order
    bad = {"kind": "refund", "reason": "size", "lines": [{"sku": sku, "quantity": 3}]}
    assert s.write("post", url, bad).status_code == 400
    r = s.write(
        "post", url, {"kind": "refund", "reason": "size", "details": "Too long", "lines": [{"sku": sku, "quantity": 1}]}
    )
    assert r.status_code == 201, r.content
    req = r.json()["requests"][0]
    assert req["number"] == f"R-{order.number}-1" and req["status"] == "requested"
    assert r.json()["items"][0]["available"] == 1  # one unit already in the open request
    assert "received your return request" in mail.outbox[-1].subject
    cancel = s.write("post", f"{url}/{req['number']}/cancel")
    assert cancel.json()["requests"][0]["status"] == "cancelled" and cancel.json()["items"][0]["available"] == 2

    Order.objects.filter(pk=order.pk).update(delivered_at=timezone.now() - timedelta(days=8))
    assert s.c.get(url).json()["can_return"] is False
    late = {"kind": "refund", "reason": "size", "lines": [{"sku": sku, "quantity": 1}]}
    assert s.write("post", url, late).status_code == 409


def test_refund_return_inspects_into_stock_and_raises_a_refund() -> None:
    s, order, sku = delivered_order(2)
    url = f"/api/v1/orders/{order.number}/returns"
    s.write("post", url, {"kind": "refund", "reason": "quality", "lines": [{"sku": sku, "quantity": 2}]})
    support = make_staff(RoleCode.SUPPORT, "help@aurevon.test")
    staff = sign_in(support)
    rid = staff.get(f"{STAFF}/returns", {"status": "requested"}).json()["results"][0]["id"]
    act = f"{STAFF}/returns/{rid}"
    assert staff.post(f"{act}/reject", {"note": ""}, format="json").status_code == 400  # a reason is needed
    assert staff.post(f"{act}/receive").status_code == 409  # not approved yet
    r = staff.post(f"{act}/approve", {"note": "Thanks"}, format="json")
    assert r.json()["status"] == "approved" and "is approved" in mail.outbox[-1].subject
    assert "return number on the parcel" in mail.outbox[-1].body
    staff.post(f"{act}/receive")
    items = staff.get(act).json()["items"]
    before_main, before_q = on_hand(sku), on_hand(sku, "quarantine")
    missing_note = {"outcomes": {items[0]["id"]: {"outcome": "damaged", "note": ""}}}
    assert staff.post(f"{act}/inspect", missing_note, format="json").status_code == 400
    ok = {"outcomes": {items[0]["id"]: {"outcome": "quarantine", "note": "loose seam"}}}
    r = staff.post(f"{act}/inspect", ok, format="json")
    assert r.status_code == 200 and r.json()["status"] == "inspected", r.content
    assert on_hand(sku) == before_main and on_hand(sku, "quarantine") == before_q + 2
    order.refresh_from_db()
    assert order.status == OrderStatus.RETURNED  # everything came back
    suggested = r.json()["suggested_refund"]
    assert float(suggested) == float(order.subtotal - order.discount)

    StaffSession.objects.update(stepped_up_at=None)
    assert staff.post(f"{act}/complete", {}, format="json").json()["type"].endswith("step-up-required")
    step_up(staff, support)
    # COD money hasn't come back from the courier, so nothing is refundable yet.
    assert staff.post(f"{act}/complete", {}, format="json").status_code == 400
    Order.objects.filter(pk=order.pk).update(payment_status="cod_reconciled")
    r = staff.post(f"{act}/complete", {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "completed", r.content
    refund = Refund.objects.get(order=order)
    assert refund.source == "return" and refund.state == RefundState.REQUESTED and str(refund.amount) == suggested
    assert {"return.approve", "return.receive", "return.inspect", "return.complete"} <= set(
        AuditLog.objects.filter(target_id=r.json()["number"]).values_list("action", flat=True)
    )


def test_exchange_creates_a_no_charge_order_for_the_new_size() -> None:
    s, order, sku = delivered_order(1)
    other = sibling_sku(sku)
    url = f"/api/v1/orders/{order.number}/returns"
    same = {"kind": "exchange", "reason": "size", "lines": [{"sku": sku, "quantity": 1, "exchange_sku": sku}]}
    assert s.write("post", url, same).status_code == 400
    r = s.write(
        "post",
        url,
        {"kind": "exchange", "reason": "size", "lines": [{"sku": sku, "quantity": 1, "exchange_sku": other}]},
    )
    assert r.status_code == 201, r.content
    staff = sign_in(make_staff(RoleCode.STORE_ADMIN))
    rid = staff.get(f"{STAFF}/returns").json()["results"][0]["id"]
    act = f"{STAFF}/returns/{rid}"
    for step in ("approve", "receive"):
        staff.post(f"{act}/{step}", {"note": ""}, format="json")
    item = staff.get(act).json()["items"][0]
    before = on_hand(sku)
    staff.post(f"{act}/inspect", {"outcomes": {item["id"]: {"outcome": "sellable"}}}, format="json")
    assert on_hand(sku) == before + 1
    other_before = on_hand(other)
    r = staff.post(f"{act}/complete", {}, format="json")
    assert r.status_code == 200, r.content
    exchange = Order.objects.get(number=r.json()["exchange_order"])
    assert exchange.payment_method == PaymentMethod.EXCHANGE and exchange.total == 0
    assert exchange.status == OrderStatus.CONFIRMED and exchange.items.get().sku == other
    assert on_hand(other) == other_before - 1
    assert "replacement is on its way" in mail.outbox[-1].body


def test_staff_permissions() -> None:
    assert sign_in(make_staff(RoleCode.INVENTORY_MANAGER)).get(f"{STAFF}/returns").status_code == 403
    accountant = sign_in(make_staff(RoleCode.ACCOUNTANT))
    assert accountant.get(f"{STAFF}/returns").status_code == 200
    s, order, sku = delivered_order(1)
    s.write(
        "post",
        f"/api/v1/orders/{order.number}/returns",
        {"kind": "refund", "reason": "size", "lines": [{"sku": sku, "quantity": 1}]},
    )
    rid = accountant.get(f"{STAFF}/returns").json()["results"][0]["id"]
    assert accountant.post(f"{STAFF}/returns/{rid}/approve", {"note": "x"}, format="json").status_code == 403
