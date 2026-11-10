"""M13 reports: totals from real orders, period comparison, CSV exports, the personal-data boundary and audit."""

import csv
import io
from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.audit.models import AuditLog
from apps.orders.models import Order, OrderStatus
from apps.orders.tests.test_commerce import KARACHI, Shopper, sku_with_stock
from apps.reports import services as reports

pytestmark = pytest.mark.django_db
DASH = f"{STAFF}/reports/dashboard"


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def place(qty: int = 1, name: str = "Ayesha Khan") -> Order:
    s = Shopper()
    s.add(sku_with_stock(10), qty)
    r = s.place("cod", address={**KARACHI, "full_name": name})
    assert r.status_code == 201, r.content
    return Order.objects.get(number=r.json()["order"]["number"])


def test_dashboard_totals_match_the_orders() -> None:
    a, b = place(2), place(1)
    cancelled = place(1)
    Order.objects.filter(pk=cancelled.pk).update(status=OrderStatus.CANCELLED)
    accountant = sign_in(make_staff(RoleCode.ACCOUNTANT))
    d = accountant.get(DASH).json()
    s = d["summary"]
    assert s["orders"] == 2 and s["units"] == 3 and s["cancelled"] == 1
    assert Decimal(s["gross_sales"]) == a.total + b.total
    assert Decimal(s["average_order"]) == ((a.total + b.total) / 2).quantize(Decimal("0.01"))
    assert Decimal(s["cod_sales"]) == a.total + b.total and s["card_sales"] == "0.00"
    assert sum(day["orders"] for day in d["daily"]) == 2 and len(d["daily"]) == 30
    assert sum(p["units"] for p in d["products"]) == 3
    assert d["cities"][0]["city"] == "Karachi" and d["cities"][0]["orders"] == 2
    assert d["customers"]["guest_orders"] == 2
    assert d["change"]["orders"] is None  # nothing in the previous period
    assert d["inventory"]["sellable_units"] > 0
    assert d["exports"] == ["categories", "daily-sales", "orders", "products"]
    assert "Net sales" in d["definitions"]
    assert accountant.get(DASH, {"from": "nope"}).status_code == 400


def test_permissions_and_personal_exports_are_audited() -> None:
    place(1, name='=HYPERLINK("http://evil")')
    for role in (RoleCode.SUPPORT, RoleCode.INVENTORY_MANAGER, RoleCode.CONTENT_MARKETING):
        assert sign_in(make_staff(role)).get(DASH).status_code == 403
    admin = sign_in(make_staff(RoleCode.STORE_ADMIN))
    assert admin.get(DASH).json()["exports"] == ["categories", "daily-sales", "products"]
    daily = admin.get(f"{STAFF}/reports/export/daily-sales")
    assert daily.status_code == 200 and daily["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(daily.content.decode("utf-8-sig"))))
    assert rows[0] == ["date", "orders", "gross_sales_pkr"] and len(rows) == 31
    assert admin.get(f"{STAFF}/reports/export/orders").status_code == 403
    assert admin.get(f"{STAFF}/reports/export/nope").status_code == 404

    owner = sign_in(make_staff(RoleCode.OWNER, "owner@aurevon.test"))
    r = owner.get(f"{STAFF}/reports/export/orders")
    assert r.status_code == 200 and r["Cache-Control"] == "no-store"
    body = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert body[0][0] == "order" and body[1][5].startswith("'=")  # formula neutralised
    log = AuditLog.objects.get(action="report.export_personal")
    assert log.actor_label == "owner@aurevon.test" and (log.after or {})["rows"] == 1
    assert APIClient().get(DASH).status_code in (401, 403)


def test_safe_cell_and_period_bounds() -> None:
    assert reports.safe_cell("-12.50") == "-12.50" and reports.safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert reports.safe_cell(None) == ""
    from datetime import date

    p = reports.period(date(2020, 1, 1), date(2026, 11, 10))
    assert p.days == reports.MAX_DAYS and p.end == date(2026, 11, 10)
    swapped = reports.period(date(2026, 11, 10), date(2026, 11, 1))
    assert swapped.start == date(2026, 11, 1) and swapped.previous().end == date(2026, 10, 31)
