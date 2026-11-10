"""Staff order operations through the staff API: list and detail, packing, dispatch with tracking, delivery,
undelivered parcels, cash-on-delivery remittance, refunds with two approvers, payment reviews and alerts."""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import StaffSession
from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, Staff, make_staff, sign_in, step_up
from apps.audit.models import AuditLog
from apps.notifications.models import StaffAlert
from apps.orders.models import Order, PaymentStatus
from apps.payments import services as payments
from apps.payments.models import Refund, RefundState
from apps.shipping.models import Shipment

from .test_commerce import Shopper, _paid_order, demo, sku_with_stock, stock_of  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db
ORD = f"{STAFF}/orders"


def cod_order(sku: str, qty: int = 1) -> Order:
    s = Shopper()
    s.add(sku, qty)
    r = s.place("cod")
    assert r.status_code == 201, r.content
    return Order.objects.get(number=r.json()["order"]["number"])


@pytest.fixture
def admin() -> tuple[APIClient, Staff]:
    staff = make_staff(RoleCode.STORE_ADMIN, "admin@aurevon.test")
    return sign_in(staff), staff


def test_roles_see_and_change_only_what_they_may() -> None:
    order = cod_order(sku_with_stock(3))
    content = sign_in(make_staff(RoleCode.CONTENT_MARKETING))
    assert content.get(ORD).status_code == 403
    stock = sign_in(make_staff(RoleCode.INVENTORY_MANAGER))
    assert stock.get(ORD).status_code == 200  # orders.view
    assert stock.post(f"{ORD}/{order.number}/status", {"to": "packing"}, format="json").status_code == 403
    accountant = sign_in(make_staff(RoleCode.ACCOUNTANT))
    assert accountant.post(f"{ORD}/{order.number}/cancel", {"reason": "x"}, format="json").status_code == 403


def test_list_filters_and_search(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    a = cod_order(sku_with_stock(3))
    cod_order(sku_with_stock(3, skip=1))
    body = api.get(ORD).json()
    assert body["count"] == 2 and body["counts"]["confirmed"] == 2
    assert [r["number"] for r in api.get(ORD, {"q": a.number}).json()["results"]] == [a.number]
    assert api.get(ORD, {"q": "Ayesha"}).json()["count"] == 2
    assert api.get(ORD, {"status": "delivered"}).json()["count"] == 0
    assert api.get(ORD, {"date_from": "not-a-date"}).status_code == 400


def test_pack_dispatch_track_deliver_and_collect_cod(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    sku = sku_with_stock(3)
    order = cod_order(sku)
    detail = api.get(f"{ORD}/{order.number}").json()
    assert detail["next_statuses"] == ["packing"] and detail["can_cancel"] and not detail["can_dispatch"]

    assert api.post(f"{ORD}/{order.number}/dispatch", {"tracking_number": "TCS1"}, format="json").status_code == 409
    assert api.post(f"{ORD}/{order.number}/status", {"to": "packing"}, format="json").status_code == 200
    assert api.post(f"{ORD}/{order.number}/dispatch", {"courier": "manual"}, format="json").status_code == 400
    bad_link = {"tracking_number": "TCS1", "tracking_url": "http://evil.example"}
    assert api.post(f"{ORD}/{order.number}/dispatch", bad_link, format="json").status_code == 400
    mail.outbox.clear()
    r = api.post(
        f"{ORD}/{order.number}/dispatch",
        {"courier": "manual", "tracking_number": "TCS123456", "tracking_url": "https://track.example/TCS123456"},
        format="json",
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["order"]["status"] == "dispatched" and body["order"]["payment_status"] == "cod_collect"
    shipment = body["shipments"][0]
    assert shipment["cod_amount"] == f"{order.total:.2f}" and shipment["status"] == "booked"
    assert any("TCS123456" in m.body for m in mail.outbox)

    # A second order can't reuse the tracking number.
    other = cod_order(sku_with_stock(3, skip=1))
    api.post(f"{ORD}/{other.number}/status", {"to": "packing"}, format="json")
    dup = api.post(f"{ORD}/{other.number}/dispatch", {"tracking_number": "TCS123456"}, format="json")
    assert dup.status_code == 409

    ev = f"{STAFF}/shipments/{shipment['id']}/events"
    assert api.post(ev, {"status": "returned"}, format="json").status_code == 409  # not from booked
    assert api.post(ev, {"status": "in_transit", "location": "Karachi hub"}, format="json").status_code == 200
    r = api.post(ev, {"status": "delivered"}, format="json")
    assert r.json()["order"]["status"] == "delivered"
    assert r.json()["order"]["payment_status"] == "cod_remittance_pending"
    assert r.json()["cod_actions"] == ["received"]

    # Remittance: a short amount is a discrepancy and alerts finance; reconciling it needs a note.
    cod = f"{ORD}/{order.number}/cod"
    assert api.post(cod, {"action": "received"}, format="json").status_code == 403  # an Accountant's job
    api = sign_in(make_staff(RoleCode.ACCOUNTANT, "accounts@aurevon.test"))
    assert api.post(cod, {"action": "received", "amount": "10"}, format="json").status_code == 400  # no ref
    r = api.post(cod, {"action": "received", "amount": "10.00", "reference": "REM-9"}, format="json")
    assert r.json()["order"]["payment_status"] == "cod_discrepancy"
    assert StaffAlert.objects.filter(kind="cod_discrepancy", target_id=order.number).exists()
    assert api.post(cod, {"action": "reconciled"}, format="json").status_code == 400
    r = api.post(cod, {"action": "reconciled", "note": "Courier paid the balance"}, format="json")
    assert r.json()["order"]["payment_status"] == "cod_reconciled" and r.json()["cod_actions"] == []
    actions = set(AuditLog.objects.filter(target_id=order.number).values_list("action", flat=True))
    assert {
        "order.packing",
        "order.dispatch",
        "order.delivered",
        "order.cod_received",
        "order.cod_reconciled",
    } <= actions


def test_undelivered_parcel_comes_back_to_stock(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    sku = sku_with_stock(3)
    order = cod_order(sku, 2)
    assert stock_of(sku) == (1, 0)
    api.post(f"{ORD}/{order.number}/status", {"to": "packing"}, format="json")
    shipment_id = api.post(f"{ORD}/{order.number}/dispatch", {"tracking_number": "LCS1"}, format="json").json()[
        "shipments"
    ][0]["id"]
    ev = f"{STAFF}/shipments/{shipment_id}/events"
    api.post(ev, {"status": "failed", "description": "Customer not home"}, format="json")
    assert StaffAlert.objects.filter(kind="delivery_failed").exists()
    api.post(ev, {"status": "returning"}, format="json")
    r = api.post(ev, {"status": "returned"}, format="json")
    assert r.json()["order"]["status"] == "undelivered" and r.json()["order"]["payment_status"] == "cod_cancelled"
    assert stock_of(sku) == (3, 0)


def test_staff_cancel_before_dispatch_only(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    sku = sku_with_stock(3)
    order = cod_order(sku)
    assert api.post(f"{ORD}/{order.number}/cancel", {"reason": ""}, format="json").status_code == 400
    r = api.post(f"{ORD}/{order.number}/cancel", {"reason": "Customer called"}, format="json")
    assert r.json()["order"]["status"] == "cancelled" and stock_of(sku) == (3, 0)
    assert api.post(f"{ORD}/{order.number}/status", {"to": "packing"}, format="json").status_code == 409


def test_refunds_need_the_code_and_a_second_person(admin: tuple[APIClient, Staff]) -> None:
    api, staff = admin
    order = _paid_order(sku_with_stock(2))
    StaffSession.objects.filter(account=staff.account).update(stepped_up_at=None)
    url = f"{ORD}/{order.number}/refunds"
    assert api.post(url, {"amount": "100", "reason": "Late"}, format="json").status_code == 403  # code again
    step_up(api, staff)
    assert api.post(url, {"amount": "0", "reason": "x"}, format="json").status_code == 400
    too_much = {"amount": str(order.total + 1), "reason": "x"}
    assert api.post(url, too_much, format="json").status_code == 400
    r = api.post(url, {"amount": "500.00", "reason": "Arrived late"}, format="json")
    assert r.status_code == 200 and r.json()["refundable"] == f"{order.total - 500:.2f}"
    refund = Refund.objects.get(order=order)

    # The requester can't approve their own refund; an Accountant and an Owner approve it.
    assert api.post(f"{STAFF}/refunds/{refund.pk}/approve").status_code == 403
    accountant_staff = make_staff(RoleCode.ACCOUNTANT, "accounts@aurevon.test")
    accountant = sign_in(accountant_staff)
    assert accountant.post(f"{STAFF}/refunds/{refund.pk}/approve").status_code == 200
    refund.refresh_from_db()
    assert refund.state == RefundState.REQUESTED and refund.approved_by == "accounts@aurevon.test"
    owner = sign_in(make_staff(RoleCode.OWNER, "owner@aurevon.test"))
    assert owner.post(f"{STAFF}/refunds/{refund.pk}/approve").status_code == 200
    payments.process_refund(refund.pk)  # on_commit doesn't fire inside the test transaction
    refund.refresh_from_db()
    order.refresh_from_db()
    assert refund.state == RefundState.SUCCEEDED and order.payment_status == PaymentStatus.PARTLY_REFUNDED
    listed = api.get(f"{STAFF}/refunds", {"state": "succeeded"}).json()
    assert [x["order"] for x in listed] == [order.number]


def test_rejecting_a_refund_needs_a_reason(admin: tuple[APIClient, Staff]) -> None:
    api, staff = admin
    order = _paid_order(sku_with_stock(2))
    step_up(api, staff)
    api.post(f"{ORD}/{order.number}/refunds", {"amount": "200", "reason": "Goodwill"}, format="json")
    refund = Refund.objects.get(order=order)
    accountant = sign_in(make_staff(RoleCode.ACCOUNTANT))
    assert accountant.post(f"{STAFF}/refunds/{refund.pk}/reject", {}, format="json").status_code == 400
    r = accountant.post(f"{STAFF}/refunds/{refund.pk}/reject", {"note": "Not eligible"}, format="json")
    assert r.json()["state"] == "rejected"


def test_alerts_are_listed_and_resolved(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    from apps.notifications.services import alert

    alert("delivery_failed", "Delivery failed for AV1", target_type="order", target_id="AV1", dedupe_key="x1")
    alert("stock_low", "Low stock", target_type="variant", target_id="SKU", dedupe_key="x2")
    support = sign_in(make_staff(RoleCode.SUPPORT))
    kinds = [a["kind"] for a in support.get(f"{STAFF}/alerts").json()]
    assert kinds == ["delivery_failed"]  # stock alerts go to people who look after stock
    assert len(api.get(f"{STAFF}/alerts").json()) == 2
    first = api.get(f"{STAFF}/alerts").json()[0]["id"]
    assert api.post(f"{STAFF}/alerts/{first}/resolve").json()["resolved_by"] == "admin@aurevon.test"
    assert len(api.get(f"{STAFF}/alerts").json()) == 1


def test_shipments_are_unique_per_tracking_number() -> None:
    assert Shipment._meta.constraints  # guarded in the database as well as the service
