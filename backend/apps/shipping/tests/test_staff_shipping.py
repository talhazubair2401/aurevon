"""M10 staff settings: delivery zones and rates that checkout quotes from, and effective-dated tax rules."""

from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import StaffSession
from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in, step_up
from apps.audit.models import AuditLog
from apps.orders.tests.test_commerce import KARACHI, Shopper, sku_with_stock
from apps.shipping.models import ShippingZone

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


@pytest.fixture
def admin() -> APIClient:
    return sign_in(make_staff(RoleCode.STORE_ADMIN, "admin@aurevon.test"))


def test_only_store_settings_roles_can_manage_delivery_and_tax() -> None:
    for role in (RoleCode.SUPPORT, RoleCode.INVENTORY_MANAGER, RoleCode.CONTENT_MARKETING, RoleCode.ACCOUNTANT):
        assert sign_in(make_staff(role)).get(f"{STAFF}/shipping-zones").status_code == 403


def test_a_new_city_zone_changes_what_checkout_quotes(admin: APIClient) -> None:
    sku = sku_with_stock(5)
    shopper = Shopper()
    shopper.add(sku)
    before = shopper.write("post", "/api/v1/checkout/quote", {"address": KARACHI}).json()
    zones = admin.get(f"{STAFF}/shipping-zones").json()
    assert zones and any(z["is_fallback"] for z in zones)

    body = {"code": "karachi-same-day", "name": "Karachi same day", "cities": ["karachi"], "position": 0}
    taken = admin.post(f"{STAFF}/shipping-zones", body, format="json")
    assert taken.status_code == 400 and "already in the Karachi zone" in taken.json()["detail"]
    assert admin.delete(f"{STAFF}/shipping-zones/karachi").status_code == 204
    taken = admin.post(f"{STAFF}/shipping-zones", body, format="json")
    assert taken.status_code == 201, taken.content
    assert taken.json()["cities"] == ["Karachi"]

    rate = {
        "zone": "karachi-same-day",
        "method": "express",
        "fee": "400",
        "days_min": 0,
        "days_max": 1,
        "cod_allowed": False,
        "cod_fee": "99",
    }
    r = admin.post(f"{STAFF}/shipping-rates", rate, format="json")
    assert r.status_code == 201 and r.json()["cod_fee"] == "0.00"  # no COD, no COD fee
    assert admin.post(f"{STAFF}/shipping-rates", rate, format="json").status_code == 400  # one per method
    bad = {**rate, "method": "standard", "days_min": 3, "days_max": 1}
    assert admin.post(f"{STAFF}/shipping-rates", bad, format="json").status_code == 400

    after = shopper.write("post", "/api/v1/checkout/quote", {"address": KARACHI, "shipping_method": "express"}).json()
    assert [o["method"] for o in after["shipping_options"]] == ["express"]
    assert Decimal(after["shipping_fee"]["amount"]) == 400 and after != before
    assert "cod" not in after["payment_methods"]

    assert admin.delete(f"{STAFF}/shipping-zones/karachi-same-day").status_code == 204
    assert not ShippingZone.objects.filter(pk="karachi-same-day").exists()
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"shipping.zone_save", "shipping.rate_save", "shipping.zone_delete"} <= actions


def test_only_one_catch_all_zone(admin: APIClient) -> None:
    r = admin.post(f"{STAFF}/shipping-zones", {"code": "north", "name": "North", "is_fallback": True}, format="json")
    assert r.status_code == 201
    assert list(ShippingZone.objects.filter(is_fallback=True).values_list("code", flat=True)) == ["north"]
    nothing = {"code": "empty", "name": "Empty"}
    assert admin.post(f"{STAFF}/shipping-zones", nothing, format="json").status_code == 400


def test_tax_rules_need_step_up_never_overlap_and_are_ended_not_edited() -> None:
    staff = make_staff(RoleCode.OWNER, "owner@aurevon.test")
    owner = sign_in(staff)
    assert owner.get(f"{STAFF}/tax-rules").json() == {"rules": [], "in_force": None}
    rule = {"name": "Sales tax", "rate_percent": "18", "prices_include_tax": True, "effective_from": "2026-01-01"}
    StaffSession.objects.update(stepped_up_at=None)  # signing in counts as a fresh check; let it lapse
    assert owner.post(f"{STAFF}/tax-rules", rule, format="json").status_code == 403  # step-up first
    step_up(owner, staff)
    r = owner.post(f"{STAFF}/tax-rules", rule, format="json")
    assert r.status_code == 201, r.content
    first = r.json()["rules"][0]
    assert first["rate_percent"] == "18.00" and first["in_force"] and r.json()["in_force"] == first["id"]
    later = {**rule, "name": "New rate", "rate_percent": "17", "effective_from": "2027-07-01"}
    assert owner.post(f"{STAFF}/tax-rules", later, format="json").status_code == 400  # overlaps the open rule
    end = owner.post(f"{STAFF}/tax-rules/{first['id']}/end", {"effective_to": "2027-06-30"}, format="json")
    assert end.status_code == 200
    assert owner.post(f"{STAFF}/tax-rules", later, format="json").status_code == 201
    longer = owner.post(f"{STAFF}/tax-rules/{first['id']}/end", {"effective_to": "2027-12-31"}, format="json")
    assert longer.status_code == 400
    assert owner.post(f"{STAFF}/tax-rules", {**rule, "rate_percent": "60"}, format="json").status_code == 400
    assert AuditLog.objects.filter(action="tax.rule_end").exists()
