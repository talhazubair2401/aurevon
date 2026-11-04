"""M5: product detail, fresh availability, search and the P-12 catalogue rules (decision 0006)."""

import re
from typing import Any

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from apps.catalog import services
from apps.catalog.models import Category, Product, ProductStatus, ProductVariant
from apps.inventory import selectors as inventory
from apps.inventory.models import InventoryItem

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def test_skus_follow_the_approved_format() -> None:
    pattern = re.compile(r"^AV-[A-Z]{3}-\d{4}-[A-Z]{3}-[A-Z0-9]+$")
    assert all(pattern.match(sku) for sku in ProductVariant.objects.values_list("sku", flat=True))
    v = ProductVariant.objects.select_related("product__category", "colour").first()
    assert v is not None
    assert v.sku == services.sku_for(v.product.category, v.product.style_number, v.colour, v.size)


def test_detail_has_copy_sizes_in_category_order_chart_and_variants(client: Client) -> None:
    body = client.get("/api/v1/catalog/products/relaxed-chino").json()
    assert body["name"] == "Relaxed Chino" and body["fabric"] and body["care"] and body["fit_note"]
    assert body["sizes"] == ["30", "32", "34", "36"]  # numeric sizes, the category's order
    assert [row["name"] for row in body["size_chart"]] == ["Waist", "Hip", "Inseam"]
    assert set(body["size_chart"][0]["values"]) == set(Category.objects.get(slug="men-trousers").sizes)
    assert {v["colour"] for v in body["variants"]} == {"sand", "olive", "black"}
    ur = client.get("/api/v1/catalog/products/relaxed-chino", {"locale": "ur"}).json()
    assert ur["size_chart"][0]["name"] == "کمر" and ur["fabric"] == body["fabric"]  # falls back to English


def test_only_published_products_have_a_page(client: Client) -> None:
    Product.objects.filter(slug="relaxed-chino").update(status=ProductStatus.DRAFT)
    assert client.get("/api/v1/catalog/products/relaxed-chino").status_code == 404
    assert client.get("/api/v1/catalog/products/relaxed-chino/availability").status_code == 404


def test_availability_is_fresh_and_never_cached(client: Client) -> None:
    r = client.get("/api/v1/catalog/products/silk-column-dress/availability")
    assert r["Cache-Control"] == "no-store"
    variants = r.json()["variants"]
    sold_out = next(v for v in variants if v["available"])
    InventoryItem.objects.filter(variant__sku=sold_out["sku"]).update(on_hand=0, reserved=0)
    again = client.get("/api/v1/catalog/products/silk-column-dress/availability").json()["variants"]
    assert next(v for v in again if v["sku"] == sold_out["sku"])["available"] is False


def test_demo_shows_both_states_and_only_sellable_stock_counts() -> None:
    ids = list(ProductVariant.objects.values_list("id", flat=True))
    counts = inventory.available(ids)
    assert any(n == 0 for n in counts.values()) and any(n > 0 for n in counts.values())


def test_the_database_refuses_negative_or_over_reserved_stock() -> None:
    item = InventoryItem.objects.first()
    assert item is not None
    for change in ({"on_hand": -1}, {"reserved": item.on_hand + 1}):
        with pytest.raises(IntegrityError), transaction.atomic():
            InventoryItem.objects.filter(pk=item.pk).update(**change)


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("kurta", "embroidered-lawn-kurta"),  # English
        ("kurtas", "cotton-silk-kurta"),  # stemmed
        ("chik", "chikankari-kurta"),  # prefix of the last word
        ("کرتا", "block-print-kurta"),  # Urdu
        ("olive chino", "relaxed-chino"),  # colour and name together
    ],
)
def test_search_finds_products(client: Client, q: str, expected: str) -> None:
    slugs = [p["slug"] for p in client.get("/api/v1/catalog/products", {"q": q, "limit": "48"}).json()["results"]]
    assert expected in slugs


def test_search_ignores_query_syntax_and_matches_nothing_when_it_should(client: Client) -> None:
    assert client.get("/api/v1/catalog/products", {"q": "zzzz"}).json()["results"] == []
    assert client.get("/api/v1/catalog/products", {"q": "&|!:*()'"}).status_code == 200
    facets = client.get("/api/v1/catalog/facets", {"q": "kurta"}).json()
    assert sum(d["count"] for d in facets["departments"]) == 5  # the five kurtas
