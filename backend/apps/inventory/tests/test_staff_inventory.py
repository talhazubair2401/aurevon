"""M9 inventory through the staff API: stock levels, corrections, transfers, reorder levels and low-stock alerts,
suppliers, purchase orders with partial receiving, permissions and the audit trail."""

from typing import Any

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.audit.models import AuditLog
from apps.catalog.models import ProductVariant
from apps.inventory.models import InventoryItem, StockMovement
from apps.notifications.models import StaffAlert

pytestmark = pytest.mark.django_db
INV = f"{STAFF}/inventory"


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


@pytest.fixture
def manager() -> APIClient:
    return sign_in(make_staff(RoleCode.INVENTORY_MANAGER, "stock@aurevon.test"))


def a_sku(on_hand: int = 10, reserved: int = 0) -> str:
    v = ProductVariant.objects.filter(is_active=True).order_by("sku").first()
    assert v is not None
    InventoryItem.objects.filter(variant=v, location_id="main").update(on_hand=on_hand, reserved=reserved)
    return v.sku


def test_permissions() -> None:
    sku = a_sku()
    support = sign_in(make_staff(RoleCode.SUPPORT))
    assert support.get(INV).status_code == 403  # support has no inventory.view
    admin = sign_in(make_staff(RoleCode.STORE_ADMIN))
    assert admin.get(INV).status_code == 200
    assert admin.post(f"{INV}/{sku}/adjust", {"delta": 1}, format="json").status_code == 403  # view only
    assert admin.post(f"{STAFF}/suppliers", {"name": "X"}, format="json").status_code == 403


def test_list_search_and_detail(manager: APIClient) -> None:
    sku = a_sku(7, 2)
    rows = manager.get(INV, {"q": sku}).json()
    assert len(rows) == 1 and rows[0]["available"] == 5 and rows[0]["quarantine"] == 0
    assert manager.get(f"{INV}/{sku}").json()["sku"] == sku
    assert manager.get(f"{INV}/NOPE-SKU").status_code == 404


def test_corrections_never_go_below_what_orders_hold(manager: APIClient) -> None:
    sku = a_sku(5, 3)
    url = f"{INV}/{sku}/adjust"
    assert manager.post(url, {"delta": -1, "reason": "adjustment"}, format="json").status_code == 400  # note needed
    assert manager.post(url, {"delta": -3, "reason": "adjustment", "note": "count"}, format="json").status_code == 400
    assert manager.post(url, {"delta": 2, "reason": "sale", "note": "x"}, format="json").status_code == 400  # reason
    r = manager.post(url, {"delta": -2, "reason": "write_off", "note": "moth damage"}, format="json")
    assert r.status_code == 200 and r.json()["on_hand"] == 3 and r.json()["available"] == 0
    m = StockMovement.objects.filter(item__variant__sku=sku).first()
    assert m is not None and m.quantity == -2 and m.reason == "write_off" and m.actor_label == "stock@aurevon.test"
    assert AuditLog.objects.filter(action="stock.adjust", target_id=sku).exists()


def test_transfers_between_sellable_quarantine_and_damaged(manager: APIClient) -> None:
    sku = a_sku(6)
    url = f"{INV}/{sku}/transfer"
    r = manager.post(url, {"from": "main", "to": "quarantine", "quantity": 4, "note": "stain check"}, format="json")
    assert r.json()["on_hand"] == 2 and r.json()["quarantine"] == 4
    r = manager.post(url, {"from": "quarantine", "to": "main", "quantity": 3}, format="json")
    assert r.json()["on_hand"] == 5 and r.json()["quarantine"] == 1
    r = manager.post(url, {"from": "quarantine", "to": "damaged", "quantity": 1}, format="json")
    assert r.json()["damaged"] == 1 and r.json()["quarantine"] == 0
    assert manager.post(url, {"from": "damaged", "to": "main", "quantity": 1}, format="json").status_code == 400
    assert manager.post(url, {"from": "main", "to": "quarantine", "quantity": 99}, format="json").status_code == 400


def test_low_stock_alert_is_raised_and_resolves_itself(manager: APIClient) -> None:
    sku = a_sku(4)
    r = manager.put(f"{INV}/{sku}/reorder-level", {"level": 5}, format="json")
    assert r.json()["low"] is True
    alert = StaffAlert.objects.get(kind="stock_low", target_id=sku, resolved_at__isnull=True)
    assert "reorder level 5" in alert.message
    assert [x["sku"] for x in manager.get(INV, {"low": "1"}).json()] == [sku]
    manager.post(f"{INV}/{sku}/adjust", {"delta": 10, "reason": "receipt", "note": "found a box"}, format="json")
    alert.refresh_from_db()
    assert alert.resolved_at is not None and alert.resolved_by.startswith("system")
    assert manager.put(f"{INV}/{sku}/reorder-level", {"level": -1}, format="json").status_code == 400


def test_suppliers_and_purchase_orders_end_to_end(manager: APIClient) -> None:
    sku = a_sku(1)
    other = ProductVariant.objects.filter(is_active=True).order_by("sku")[1].sku
    r = manager.post(f"{STAFF}/suppliers", {"name": "Lawn House", "email": "orders@lawn.example"}, format="json")
    assert r.status_code == 201
    supplier = r.json()["id"]
    assert manager.post(f"{STAFF}/suppliers", {"name": "lawn house"}, format="json").status_code == 400  # duplicate

    bad = {"supplier": supplier, "lines": [{"sku": "NOPE", "quantity": 1}]}
    assert manager.post(f"{STAFF}/purchase-orders", bad, format="json").status_code == 400
    body = {
        "supplier": supplier,
        "expected_on": "2026-12-01",
        "lines": [{"sku": sku, "quantity": 10, "unit_cost": "1200"}, {"sku": other, "quantity": 5, "unit_cost": "900"}],
    }
    r = manager.post(f"{STAFF}/purchase-orders", body, format="json")
    assert r.status_code == 201, r.content
    po = r.json()
    assert po["number"] == "PO-000001" and po["status"] == "draft" and po["total_cost"] == "16500.00"
    url = f"{STAFF}/purchase-orders/{po['id']}"
    lines = {line["sku"]: line["id"] for line in po["lines"]}

    assert manager.post(f"{url}/receive", {"lines": []}, format="json").status_code == 400  # not sent yet
    assert manager.post(f"{url}/send").json()["status"] == "sent"
    assert manager.put(url, body, format="json").status_code == 400  # only drafts can be edited

    over = {"lines": [{"line_id": lines[sku], "quantity": 11}]}
    assert manager.post(f"{url}/receive", over, format="json").status_code == 400
    r = manager.post(f"{url}/receive", {"lines": [{"line_id": lines[sku], "quantity": 6}]}, format="json")
    assert r.json()["status"] == "partly_received" and r.json()["units_received"] == 6
    assert InventoryItem.objects.get(variant__sku=sku, location_id="main").on_hand == 7
    assert manager.post(f"{url}/cancel").status_code == 400  # stock already received
    r = manager.post(
        f"{url}/receive",
        {"lines": [{"line_id": lines[sku], "quantity": 4}, {"line_id": lines[other], "quantity": 5}]},
        format="json",
    )
    assert r.json()["status"] == "received"
    receipts = StockMovement.objects.filter(reference="PO-000001", reason="receipt")
    assert sum(m.quantity for m in receipts) == 15
    assert manager.get(f"{STAFF}/suppliers").json()[0]["open_orders"] == 0
    actions = set(AuditLog.objects.filter(target_id="PO-000001").values_list("action", flat=True))
    assert {"po.create", "po.send", "po.receive"} <= actions


def test_a_sale_that_reaches_the_reorder_level_raises_the_alert() -> None:
    from apps.inventory import services as stock

    sku = a_sku(3)
    v = ProductVariant.objects.get(sku=sku)
    InventoryItem.objects.filter(variant=v, location_id="main").update(reorder_level=2)
    stock.reserve("00000000-0000-0000-0000-0000000000aa", "AV1", {v.pk: 1}, "2099-01-01T00:00:00Z")
    stock.commit("00000000-0000-0000-0000-0000000000aa", "AV1")
    assert StaffAlert.objects.filter(kind="stock_low", target_id=sku, resolved_at__isnull=True).exists()
