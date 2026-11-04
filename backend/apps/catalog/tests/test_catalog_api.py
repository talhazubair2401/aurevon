from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from apps.catalog.models import Product, ProductStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def get(client: Client, path: str, **params: Any) -> Any:
    response = client.get(path, params)
    assert response.status_code == 200, response.content
    return response.json()


def all_pages(client: Client, **params: Any) -> list[dict[str, Any]]:
    page = get(client, "/api/v1/catalog/products", **params)
    results = list(page["results"])
    while page["next"]:
        page = client.get(page["next"]).json()
        results += page["results"]
    return results


def test_lists_published_products_with_money_as_decimal_strings(client: Client) -> None:
    page = get(client, "/api/v1/catalog/products")
    assert len(page["results"]) == 24
    card = page["results"][0]
    assert card["price_min"] == {"amount": "38500.00", "currency": "PKR"}
    assert card["image"]["demo_art"] == "dress" and card["image"]["url"] is None
    assert {"slug", "name", "department", "category", "colours", "sizes", "is_new"} <= card.keys()


def test_featured_order_alternates_women_and_men(client: Client) -> None:
    depts = [p["department"] for p in get(client, "/api/v1/catalog/products")["results"][:8]]
    assert depts == ["women", "men"] * 4


def test_drafts_and_archived_are_hidden(client: Client) -> None:
    Product.objects.filter(slug="silk-column-dress").update(status=ProductStatus.DRAFT)
    Product.objects.filter(slug="wool-overcoat").update(status=ProductStatus.ARCHIVED)
    slugs = {p["slug"] for p in all_pages(client)}
    assert "silk-column-dress" not in slugs and "wool-overcoat" not in slugs and len(slugs) == 22


def test_filters_combine(client: Client) -> None:
    women = all_pages(client, department="women")
    assert len(women) == 12 and {p["department"] for p in women} == {"women"}
    kurtas = all_pages(client, category="women-kurtas")
    assert {p["slug"] for p in kurtas} == {"embroidered-lawn-kurta", "block-print-kurta", "chikankari-kurta"}
    # One variant must match both size and colour.
    xxl_ivory = all_pages(client, size="XXL", colour="ivory")
    assert {p["slug"] for p in xxl_ivory} == {"cotton-silk-kurta", "band-collar-shirt"}
    priced = all_pages(client, price_min="20000", price_max="30000")
    assert all(Decimal("20000") <= Decimal(p["price_min"]["amount"]) <= Decimal("30000") for p in priced)
    heritage = all_pages(client, collection="heritage-edit")
    assert len(heritage) == 6


def test_sorting_and_cursor_pagination(client: Client) -> None:
    asc = all_pages(client, sort="price_asc", limit="5")
    prices = [Decimal(p["price_min"]["amount"]) for p in asc]
    assert len(asc) == 24 and prices == sorted(prices)
    desc = all_pages(client, sort="price_desc", limit="7")
    assert [p["slug"] for p in desc] == [p["slug"] for p in reversed(asc)]
    newest = get(client, "/api/v1/catalog/products", sort="newest")["results"]
    assert newest[0]["slug"] == "wool-overcoat" and newest[0]["is_new"] is True


@pytest.mark.parametrize(
    "params",
    [{"sort": "random"}, {"department": "kids"}, {"price_min": "abc"}, {"price_min": "-5"}, {"locale": "fr"}],
)
def test_invalid_parameters_are_rejected(client: Client, params: dict[str, str]) -> None:
    assert client.get("/api/v1/catalog/products", params).status_code == 400


def test_urdu_names(client: Client) -> None:
    card = get(client, "/api/v1/catalog/products", locale="ur")["results"][0]
    assert card["name"] == "ریشمی کالم ڈریس"
    assert card["category"]["name"] == "ڈریسز"


def test_facets_do_not_hide_their_own_options(client: Client) -> None:
    facets = get(client, "/api/v1/catalog/facets", department="women")
    assert {d["value"]: d["count"] for d in facets["departments"]} == {"men": 12, "women": 12}
    assert all(c["department"] == "women" for c in facets["categories"])
    assert [s["value"] for s in facets["sizes"]] == ["XS", "S", "M", "L", "XL"]
    assert facets["price"] == {"min": "9800.00", "max": "48500.00", "currency": "PKR"}


def test_public_endpoints_ignore_sessions_and_are_not_cached(client: Client) -> None:
    client.cookies["__Host-av_session"] = "anything"
    response = client.get("/api/v1/catalog/collections")
    assert response.status_code == 200
    assert [c["slug"] for c in response.json()] == ["heritage-edit", "modern-tailoring", "evening"]
