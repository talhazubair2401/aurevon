"""Shapes catalogue records for the storefront in the requested language."""

from typing import Any

from common.api import money

from . import selectors, threed
from .models import Category, Collection, Product


def _pick(en: str, ur: str, locale: str) -> str:
    return ur if locale == "ur" and ur else en


def product_card(product: Product, locale: str) -> dict[str, Any]:
    names = selectors.translations(product)
    name = names.get(locale, names.get("en", {"name": product.slug}))["name"]
    variants = list(product.variants.all())
    colours = selectors.unique_colours(variants)
    images = list(product.images.all())
    # A real photograph comes first; the illustrated stand-ins only when there is none (decision 0006, #9).
    image = next((i for i in images if i.url), images[0] if images else None)
    photos = [i for i in images if i.url]
    hover = photos[1] if len(photos) > 1 else None  # a second photograph, shown on hover
    first_colour = colours[0] if colours else None
    sizes = sorted({v.size for v in variants}, key=selectors.size_sort_key)
    return {
        "slug": product.slug,
        "name": name,
        "department": product.department,
        "category": category(product.category, locale),
        "price_min": money(product.price_min, product.currency),
        "price_max": money(product.price_max, product.currency),
        "colours": [
            {"slug": c.colour.slug, "name": _pick(c.colour.name_en, c.colour.name_ur, locale), "hex": c.colour.hex}
            for c in colours
        ],
        "sizes": sizes,
        "image": None
        if image is None
        else {
            "url": (image.thumb_url or image.url) or None,
            "demo_art": image.demo_art or None,
            "tone": first_colour.colour.hex if first_colour else "#E4E1D9",
            "alt": _pick(image.alt_en, image.alt_ur, locale),
        },
        "hover_image": None
        if hover is None
        else {"url": hover.thumb_url or hover.url, "alt": _pick(hover.alt_en, hover.alt_ur, locale)},
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
        "image": collection_image(col, locale),
    }


def collection_image(col: Collection, locale: str) -> dict[str, str] | None:
    """The collection's cover: the first photograph of its first published product that has one. Collections
    have no image of their own yet (no schema change in the homepage redesign)."""
    from .models import ProductImage, ProductStatus

    if col.cover_url.startswith("/media/"):
        return {"url": col.cover_url, "alt": _pick(col.cover_alt_en, col.cover_alt_ur, locale)}
    image = (
        ProductImage.objects.filter(product__collectionitem__collection=col, product__status=ProductStatus.PUBLISHED)
        .exclude(url="")
        .order_by("product__collectionitem__position", "position")
        .first()
    )
    if image is None:
        return None
    return {"url": image.url, "alt": _pick(image.alt_en, image.alt_ur, locale)}


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


def size_chart(cat: Category, locale: str) -> list[dict[str, Any]]:
    return [
        {
            "name": _pick(row.get("name", {}).get("en", ""), row.get("name", {}).get("ur", ""), locale),
            "values": row.get("values", {}),
        }
        for row in cat.size_chart
    ]


def product_detail(product: Product, locale: str) -> dict[str, Any]:
    """Everything the product page shows. Price and stock decisions come from availability, read fresh (A-15)."""
    names = selectors.translations(product)
    own = names.get(locale) or {}
    english = names.get("en") or {}
    copy = {k: own.get(k) or english.get(k, "") for k in ("name", "description", "fabric", "care", "fit_note")}
    variants = list(product.variants.all())
    colour_hex = {v.colour.slug: v.colour.hex for v in variants}
    category_sizes = [s for s in product.category.sizes if s in {v.size for v in variants}]
    return {
        **product_card(product, locale),
        **copy,
        "style_number": f"{product.style_number:04d}",
        "sizes": category_sizes or product_card(product, locale)["sizes"],
        "images": [
            {
                "url": i.url or None,
                "demo_art": i.demo_art or None,
                "colour": i.colour_slug or None,
                "tone": colour_hex.get(i.colour_slug, "#E4E1D9"),
                "alt": _pick(i.alt_en, i.alt_ur, locale),
            }
            for i in product.images.all()
        ],
        "variants": [
            {"sku": v.sku, "size": v.size, "colour": v.colour.slug, "price": money(v.price, v.currency)}
            for v in variants
        ],
        "size_chart": size_chart(product.category, locale),
        "collections": [collection(c, locale) for c in product.collections.all() if c.is_published],
        # None while 3D is off for shoppers (until V-01 to V-03 pass) or when no model is approved.
        "model3d": threed.for_shoppers(product),
    }
