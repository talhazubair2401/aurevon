"""M5 staff catalogue: roles, drafts and publishing, variants and SKUs, prices with re-confirmation, categories
with their own sizes and charts, colours, CSV import (decision 0006)."""

from typing import Any

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import StaffSession
from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, Staff, make_staff, sign_in, step_up
from apps.audit.models import AuditLog
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import InventoryItem

pytestmark = pytest.mark.django_db
CAT = f"{STAFF}/catalog"


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


@pytest.fixture
def admin() -> tuple[APIClient, Staff]:
    staff = make_staff(RoleCode.STORE_ADMIN, "admin@aurevon.test")
    return sign_in(staff), staff


def new_product(client: APIClient, slug: str = "linen-kurta", **extra: Any) -> Any:
    body = {
        "slug": slug,
        "category": "women-kurtas",
        "copy": {"en": {"name": "Linen Kurta", "fabric": "Linen"}, "ur": {"name": "لینن کرتا"}},
        **extra,
    }
    return client.post(f"{CAT}/products", body, format="json")


def test_roles(admin: tuple[APIClient, Staff]) -> None:
    support = sign_in(make_staff(RoleCode.SUPPORT))
    assert support.get(f"{CAT}/products").status_code == 200  # catalogue: read
    assert new_product(support).status_code == 403
    accountant = sign_in(make_staff(RoleCode.ACCOUNTANT))
    assert accountant.get(f"{CAT}/products").status_code == 403
    content = sign_in(make_staff(RoleCode.CONTENT_MARKETING))
    r = new_product(content, base_price="5000")
    assert r.status_code == 201 and r.json()["base_price"] == "0.00"  # no price rights: no price
    pid = r.json()["id"]
    assert content.put(f"{CAT}/products/{pid}/prices", {"base_price": "5000"}, format="json").status_code == 403
    assert content.post(f"{CAT}/products/{pid}/status", {"status": "published"}, format="json").status_code == 403


def test_product_lifecycle(admin: tuple[APIClient, Staff], client: Any) -> None:
    api, staff = admin
    r = new_product(api)
    assert r.status_code == 201, r.content
    pid = r.json()["id"]
    assert client.get("/api/v1/catalog/products/linen-kurta").status_code == 404  # draft

    r = api.post(f"{CAT}/products/{pid}/status", {"status": "published"}, format="json")
    assert r.status_code == 400 and "colour and size" in r.json()["detail"]

    r = api.put(f"{CAT}/products/{pid}/variants", {"colours": ["ivory", "sage"], "sizes": ["S", "M"]}, format="json")
    assert r.status_code == 200
    skus = sorted(v["sku"] for v in r.json()["variant_list"])
    style = r.json()["style_number"]
    assert skus[0].startswith(f"AV-WKU-{style}-") and len(skus) == 4
    assert InventoryItem.objects.filter(variant__sku__in=skus, on_hand=0).count() == 4  # stock records at 0

    # Prices need re-confirmation (signing in counts as one for five minutes; age it).
    StaffSession.objects.filter(account=staff.account).update(stepped_up_at=None)
    assert api.put(f"{CAT}/products/{pid}/prices", {"base_price": "12500"}, format="json").status_code == 403
    step_up(api, staff)
    sku = skus[0]
    r = api.put(f"{CAT}/products/{pid}/prices", {"base_price": "12500", "overrides": {sku: "13500"}}, format="json")
    assert r.status_code == 200
    prices = {v["sku"]: v["price"] for v in r.json()["variant_list"]}
    assert prices[sku] == "13500.00" and prices[skus[1]] == "12500.00"
    audit = AuditLog.objects.get(action="catalog.prices.change").after
    assert audit is not None and audit["base_price"] == "12500.00"

    r = api.post(f"{CAT}/products/{pid}/status", {"status": "published"}, format="json")
    assert r.status_code == 200 and r.json()["publish_problems"] == []
    body = client.get("/api/v1/catalog/products/linen-kurta").json()
    assert body["fabric"] == "Linen" and body["price_min"]["amount"] == "12500.00"
    found = [p["slug"] for p in client.get("/api/v1/catalog/products", {"q": "linen"}).json()["results"]]
    assert "linen-kurta" in found

    # Removing a size deactivates its variants and keeps their SKUs; adding it back reuses them.
    api.put(f"{CAT}/products/{pid}/variants", {"colours": ["ivory", "sage"], "sizes": ["S"]}, format="json")
    assert ProductVariant.objects.filter(sku__in=skus, is_active=False).count() == 2
    api.put(f"{CAT}/products/{pid}/variants", {"colours": ["ivory", "sage"], "sizes": ["S", "M"]}, format="json")
    assert sorted(ProductVariant.objects.filter(product_id=pid).values_list("sku", flat=True)) == skus

    # Renaming a live product keeps the old address working.
    api.put(
        f"{CAT}/products/{pid}", {"slug": "linen-kurta-ivory", "copy": {"en": {"name": "Linen Kurta"}}}, format="json"
    )
    resolved = client.get("/api/v1/cms/redirects/resolve", {"path": "/products/linen-kurta"}).json()
    assert resolved["to"] == "/products/linen-kurta-ivory"

    r = api.post(f"{CAT}/products/{pid}/status", {"status": "archived"}, format="json")
    assert client.get("/api/v1/catalog/products/linen-kurta-ivory").status_code == 404


def test_variants_only_in_the_category_sizes(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    pid = new_product(api).json()["id"]
    r = api.put(f"{CAT}/products/{pid}/variants", {"colours": ["ivory"], "sizes": ["32"]}, format="json")
    assert r.status_code == 400 and "XS" in r.json()["detail"]


def test_categories_with_numeric_sizes_and_charts(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    body = {
        "slug": "women-jeans",
        "code": "WJN",
        "department": "women",
        "name_en": "Jeans",
        "name_ur": "جینز",
        "sizes": ["24", "26", "28"],
        "size_chart": [{"name": {"en": "Waist", "ur": "کمر"}, "values": {"24": "61", "26": "66", "28": "71.5"}}],
    }
    r = api.post(f"{CAT}/categories", body, format="json")
    assert r.status_code == 201, r.content
    assert api.post(f"{CAT}/categories", body, format="json").status_code == 400  # code and address taken
    bad = {**body, "slug": "x", "code": "XXQ", "size_chart": [{"name": {"en": "W"}, "values": {"24": "wide"}}]}
    assert api.post(f"{CAT}/categories", bad, format="json").status_code == 400
    # A size that products still sell can't be removed.
    trousers = Category.objects.get(slug="men-trousers")
    r = api.put(
        f"{CAT}/categories/men-trousers", {"name_en": "Trousers", "sizes": ["30"], "code": trousers.code}, format="json"
    )
    assert r.status_code == 400 and "still sell" in r.json()["detail"]
    r = api.put(
        f"{CAT}/categories/men-trousers", {"name_en": "Trousers", "sizes": trousers.sizes, "code": "ZZZ"}, format="json"
    )
    assert r.status_code == 400  # code is in SKUs


def test_colours(admin: tuple[APIClient, Staff]) -> None:
    api, _ = admin
    r = api.post(
        f"{CAT}/colours",
        {"slug": "rust", "code": "RST", "name_en": "Rust", "name_ur": "زنگ", "hex": "#9A4A2B"},
        format="json",
    )
    assert r.status_code == 201
    assert (
        api.put(f"{CAT}/colours/rust", {"code": "RUS", "name_en": "Rust", "hex": "#9A4A2B"}, format="json").status_code
        == 400
    )
    assert api.put(f"{CAT}/colours/rust", {"name_en": "Rust", "hex": "red"}, format="json").status_code == 400


CSV = """slug,category,name_en,name_ur,description_en,base_price,colours,sizes,featured
sand-kurta,women-kurtas,Sand Kurta,ریتیلا کرتا,Light lawn,9900,sand|ivory,S|M|L,yes
relaxed-chino,men-trousers,Relaxed Chino,ریلیکسڈ چینو,,8700,olive,30|32,no
"""


def test_csv_import_checks_everything_first_then_applies(admin: tuple[APIClient, Staff]) -> None:
    api, staff = admin
    r = api.post(f"{CAT}/import", {"csv": CSV}, format="json")  # dry run
    body = r.json()
    assert r.status_code == 200 and body["applied"] is False and body["errors"] == []
    assert body["created"] == ["sand-kurta"] and body["updated"] == ["relaxed-chino"]
    assert not Product.objects.filter(slug="sand-kurta").exists()

    bad = CSV + "x-kurta,women-kurtas,X,,,,teal,S,no\n"
    StaffSession.objects.filter(account=staff.account).update(stepped_up_at=None)
    body = api.post(f"{CAT}/import", {"csv": bad, "apply": True}, format="json")
    assert body.status_code == 403  # applying needs the authenticator code
    step_up(api, staff)
    body = api.post(f"{CAT}/import", {"csv": bad, "apply": True}, format="json").json()
    assert body["applied"] is False and body["errors"][0]["row"] == 4
    assert not Product.objects.filter(slug="sand-kurta").exists()  # nothing written

    body = api.post(f"{CAT}/import", {"csv": CSV, "apply": True}, format="json").json()
    assert body["applied"] is True
    sand = Product.objects.get(slug="sand-kurta")
    assert sand.status == "draft" and sand.is_featured and sand.variants.count() == 6
    assert Product.objects.get(slug="relaxed-chino").base_price == 8700
    assert api.get(f"{CAT}/import/template").content.decode().startswith("slug,category,name_en")
