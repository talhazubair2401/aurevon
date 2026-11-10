"""M11 staff promotions: coupon codes and scheduled automatic promotions, as checkout sees them."""

from datetime import timedelta
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.audit.models import AuditLog
from apps.orders.tests.test_commerce import KARACHI, customer, sku_with_stock

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


@pytest.fixture
def marketing() -> APIClient:
    return sign_in(make_staff(RoleCode.CONTENT_MARKETING, "marketing@aurevon.test"))


def iso(delta: timedelta) -> str:
    return (timezone.now() + delta).isoformat()


def test_permissions() -> None:
    for role in (RoleCode.SUPPORT, RoleCode.ACCOUNTANT, RoleCode.INVENTORY_MANAGER):
        assert sign_in(make_staff(role)).get(f"{STAFF}/coupons").status_code == 403
    assert sign_in(make_staff(RoleCode.STORE_ADMIN)).get(f"{STAFF}/promotions").status_code == 200


def test_coupon_lifecycle_and_usage_totals(marketing: APIClient) -> None:
    body = {"code": "eid15", "kind": "percent", "value": "15", "usage_limit": 100, "description": "Eid"}
    r = marketing.post(f"{STAFF}/coupons", body, format="json")
    assert r.status_code == 201, r.content
    coupon = r.json()
    assert coupon["code"] == "EID15" and coupon["state"] == "live" and coupon["created_by"] == "marketing@aurevon.test"
    assert marketing.post(f"{STAFF}/coupons", body, format="json").status_code == 400  # duplicate code
    assert marketing.post(f"{STAFF}/coupons", {**body, "code": "X1", "value": "95"}, format="json").status_code == 400
    bad_cat = {**body, "code": "CAT1", "categories": ["no-such-category"]}
    assert marketing.post(f"{STAFF}/coupons", bad_cat, format="json").status_code == 400

    sku = sku_with_stock(5)
    shopper = customer()
    shopper.add(sku)
    assert shopper.c.post("/api/v1/cart/coupon", {"code": "eid15"}, format="json").status_code == 200
    assert shopper.place().status_code == 201

    used = marketing.get(f"{STAFF}/coupons").json()[0]
    assert used["times_used"] == 1 and float(used["discount_given"]) > 0 and float(used["order_value"]) > 0
    url = f"{STAFF}/coupons/{coupon['id']}"
    assert marketing.put(url, {**body, "code": "EID20"}, format="json").status_code == 400  # used: can't rename
    off = marketing.put(url, {**body, "is_active": False}, format="json")
    assert off.status_code == 200 and off.json()["state"] == "off"
    shopper.add(sku)
    assert shopper.c.post("/api/v1/cart/coupon", {"code": "EID15"}, format="json").status_code == 400
    assert AuditLog.objects.filter(action="coupon.save").count() == 2


def test_scheduled_promotion_applies_only_inside_its_window(marketing: APIClient) -> None:
    sku = sku_with_stock(5)
    shopper = customer()
    shopper.add(sku)
    body = {
        "name": "Winter",
        "label_en": "Winter sale",
        "label_ur": "سرما سیل",
        "kind": "percent",
        "value": "20",
        "starts_at": iso(timedelta(days=1)),
        "ends_at": iso(timedelta(days=8)),
    }
    no_end = {**body, "ends_at": None}
    assert marketing.post(f"{STAFF}/promotions", no_end, format="json").status_code == 400
    r = marketing.post(f"{STAFF}/promotions", body, format="json")
    assert r.status_code == 201 and r.json()["state"] == "scheduled"
    quote = shopper.c.post("/api/v1/checkout/quote", {"address": KARACHI}, format="json").json()
    assert quote["discount"]["amount"] == "0.00"
    started = {**body, "starts_at": iso(-timedelta(hours=1))}
    r = marketing.put(f"{STAFF}/promotions/{r.json()['id']}", started, format="json")
    assert r.json()["state"] == "live"
    quote = shopper.c.post("/api/v1/checkout/quote", {"address": KARACHI}, format="json").json()
    assert quote["discount_label"] == "Winter sale" and float(quote["discount"]["amount"]) > 0
    backwards = {**body, "ends_at": iso(-timedelta(days=3))}
    assert marketing.post(f"{STAFF}/promotions", backwards, format="json").status_code == 400
