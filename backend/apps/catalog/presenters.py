"""Shapes catalogue records for the storefront in the requested language."""

from typing import Any

from common.api import money

from . import selectors
from .models import Category, Collection, Product


def _pick(en: str, ur: str, locale: str) -> str:
    return ur if locale == "ur" and ur else en


def product_card(product: Product, locale: str) -> dict[str, Any]:
    names = selectors.translations(product)
    name = names.get(locale, names.get("en", {"name": product.slug}))["name"]
    variants = list(product.variants.all())
    colours = selectors.unique_colours(variants)
    images = list(product.images.all())
    image = images[0] if images else None
    first_colour = colours[0] if colours else None
    sizes: list[str] = []
    for v in variants:
        if v.size not in sizes:
            sizes.append(v.size)
    return {
        "slug": product.slug,
        "name": name,
        "department": product.department,
        "category": category(product.category, locale),
        "price_min": money(product.price_min, product.currency),
        "price_max": money(product.price_max, product.currency),
        "colours": [
            {"slug": c.colour_slug, "name": _pick(c.colour_name_en, c.colour_name_ur, locale), "hex": c.colour_hex}
            for c in colours
        ],
        "sizes": sizes,
        "image": None
        if image is None
        else {
            "url": image.url or None,
            "demo_art": image.demo_art or None,
            "tone": first_colour.colour_hex if first_colour else "#E5E0DB",
            "alt": _pick(image.alt_en, image.alt_ur, locale),
        },
        "is_new": selectors.is_new(product),
        "is_featured": product.is_featured,
    }


def category(cat: Category, locale: str) -> dict[str, Any]:
    return {"slug": cat.slug, "department": cat.department, "name": _pick(cat.name_en, cat.name_ur, locale)}


def collection(col: Collection, locale: str) -> dict[str, Any]:
    return {
        "slug": col.slug,
        "name": _pick(col.name_en, col.name_ur, locale),
        "description": _pick(col.description_en, col.description_ur, locale),
        "demo_art": col.demo_art or None,
        "tone": col.tone,
    }


def localise_facets(facets: dict[str, Any], locale: str) -> dict[str, Any]:
    for key in ("categories", "colours"):
        for item in facets[key]:
            item["name"] = _pick(item["name"]["en"], item["name"]["ur"], locale)
    price = facets["price"]
    facets["price"] = {
        "min": None if price["min"] is None else f"{price['min']:.2f}",
        "max": None if price["max"] is None else f"{price['max']:.2f}",
        "currency": "PKR",
    }
    return facets
