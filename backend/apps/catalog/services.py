"""Catalogue writes. Other apps call these, never the models directly (MTS §5)."""

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models import Max, Min, Value

from .models import Category, Colour, Product, ProductTranslation, ProductVariant

# Search configuration per language: English stemming; Urdu as plain words (PostgreSQL has no Urdu stemmer).
SEARCH_CONFIG = {"en": "english", "ur": "simple"}


def sku_for(category: Category, style_number: int, colour: Colour, size: str) -> str:
    """AV-{category}-{style no.}-{colour}-{size}, e.g. AV-WKU-0012-IVR-M (decision 0006, #6)."""
    return f"AV-{category.code}-{style_number:04d}-{colour.code}-{size.upper()}"


def next_style_number() -> int:
    current = Product.objects.aggregate(n=Max("style_number"))["n"]
    return (current or 0) + 1


@transaction.atomic
def refresh_price_range(product: Product) -> None:
    """Keep the denormalised price range in step with the product's active variants."""
    agg = product.variants.filter(is_active=True).aggregate(lo=Min("price"), hi=Max("price"))
    Product.objects.filter(pk=product.pk).update(price_min=agg["lo"], price_max=agg["hi"])
    product.price_min, product.price_max = agg["lo"], agg["hi"]


@transaction.atomic
def apply_base_price(product: Product) -> None:
    """Every variant without its own price follows the product's base price (decision 0006, #7)."""
    ProductVariant.objects.filter(product=product, price_overridden=False).update(price=product.base_price)
    refresh_price_range(product)


def refresh_search(product: Product) -> None:
    """Rebuild the product's search text per language: name, category and colours first, then the details."""
    colours_en = " ".join(product.variants.values_list("colour__name_en", flat=True).distinct())
    colours_ur = " ".join(product.variants.values_list("colour__name_ur", flat=True).distinct())
    category = product.category
    for t in ProductTranslation.objects.filter(product=product):
        config = SEARCH_CONFIG.get(t.locale, "simple")
        extra_a = f"{category.name_en} {category.name_ur} {colours_en} {colours_ur}"
        ProductTranslation.objects.filter(pk=t.pk).update(
            search_vector=SearchVector("name", weight="A", config=config)
            + SearchVector(Value(extra_a), weight="A", config=config)
            + SearchVector("description", "fabric", weight="B", config=config)
        )
