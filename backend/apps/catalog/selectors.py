"""Catalogue reads for the storefront: published products only, filtering, facets and card data."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Max, Min, Prefetch, Q, QuerySet
from django.utils import timezone

from .models import Category, Collection, Product, ProductImage, ProductStatus, ProductVariant

NEW_ARRIVAL_DAYS = 30
SORTS = {
    "featured": ("position", "id"),
    "newest": ("-published_at", "-id"),
    "price_asc": ("price_min", "id"),
    "price_desc": ("-price_min", "-id"),
}
DEFAULT_SORT = "featured"


@dataclass
class ProductFilters:
    department: str | None = None
    category: str | None = None
    collection: str | None = None
    sizes: list[str] = field(default_factory=list)
    colours: list[str] = field(default_factory=list)
    price_min: Decimal | None = None
    price_max: Decimal | None = None


def published() -> QuerySet[Product]:
    return Product.objects.filter(status=ProductStatus.PUBLISHED, price_min__isnull=False)


def with_card_data(qs: QuerySet[Product]) -> QuerySet[Product]:
    return qs.select_related("category").prefetch_related(
        "translations",
        Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True)),
        Prefetch("images", queryset=ProductImage.objects.order_by("position")),
    )


def apply_filters(qs: QuerySet[Product], f: ProductFilters, *, skip: str | None = None) -> QuerySet[Product]:
    """Apply every filter except `skip` (used for facet counts, so a facet doesn't hide its own options)."""
    if f.department and skip != "department":
        qs = qs.filter(department=f.department)
    if f.category and skip != "category":
        qs = qs.filter(category__slug=f.category)
    if f.collection:
        qs = qs.filter(collections__slug=f.collection, collections__is_published=True)
    variant_q = Q(variants__is_active=True)
    variant_filtered = False
    if f.sizes and skip != "size":
        variant_q &= Q(variants__size__in=f.sizes)
        variant_filtered = True
    if f.colours and skip != "colour":
        variant_q &= Q(variants__colour_slug__in=f.colours)
        variant_filtered = True
    if variant_filtered:
        # One variant must match both size and colour, so "M in Ivory" means that variant exists.
        qs = qs.filter(variant_q)
    if skip != "price":
        if f.price_min is not None:
            qs = qs.filter(price_max__gte=f.price_min)
        if f.price_max is not None:
            qs = qs.filter(price_min__lte=f.price_max)
    return qs.distinct()


def products(f: ProductFilters, sort: str) -> QuerySet[Product]:
    return with_card_data(apply_filters(published(), f)).order_by(*SORTS.get(sort, SORTS[DEFAULT_SORT]))


SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def facets(f: ProductFilters) -> dict[str, Any]:
    base = published()
    dept = (
        apply_filters(base, f, skip="department")
        .values("department")
        .annotate(n=Count("id", distinct=True))
        .order_by("department")
    )
    cats = (
        apply_filters(base, f, skip="category")
        .values("category__slug", "category__name_en", "category__name_ur", "category__department")
        .annotate(n=Count("id", distinct=True))
        .order_by("category__department", "category__position")
    )
    size_rows = (
        ProductVariant.objects.filter(is_active=True, product__in=apply_filters(base, f, skip="size"))
        .values("size")
        .annotate(n=Count("product", distinct=True))
    )
    colour_rows = (
        ProductVariant.objects.filter(is_active=True, product__in=apply_filters(base, f, skip="colour"))
        .values("colour_slug", "colour_name_en", "colour_name_ur", "colour_hex")
        .annotate(n=Count("product", distinct=True))
        .order_by("colour_name_en")
    )
    price = apply_filters(base, f, skip="price").aggregate(lo=Min("price_min"), hi=Max("price_max"))
    return {
        "departments": [{"value": r["department"], "count": r["n"]} for r in dept],
        "categories": [
            {
                "slug": r["category__slug"],
                "department": r["category__department"],
                "name": {"en": r["category__name_en"], "ur": r["category__name_ur"]},
                "count": r["n"],
            }
            for r in cats
        ],
        "sizes": sorted(
            ({"value": r["size"], "count": r["n"]} for r in size_rows),
            key=lambda s: SIZE_ORDER.index(s["value"]) if s["value"] in SIZE_ORDER else len(SIZE_ORDER),
        ),
        "colours": [
            {
                "slug": r["colour_slug"],
                "name": {"en": r["colour_name_en"], "ur": r["colour_name_ur"]},
                "hex": r["colour_hex"],
                "count": r["n"],
            }
            for r in colour_rows
        ],
        "price": {"min": price["lo"], "max": price["hi"]},
    }


def published_collections() -> QuerySet[Collection]:
    return Collection.objects.filter(is_published=True).order_by("position", "slug")


def categories() -> QuerySet[Category]:
    return Category.objects.all()


def featured(limit: int = 8) -> list[Product]:
    return list(with_card_data(published().filter(is_featured=True)).order_by("position", "id")[:limit])


def new_arrivals(limit: int = 8) -> list[Product]:
    return list(with_card_data(published()).order_by("-published_at", "-id")[:limit])


def is_new(product: Product) -> bool:
    return bool(product.published_at and product.published_at >= timezone.now() - timedelta(days=NEW_ARRIVAL_DAYS))


def translations(product: Product) -> dict[str, dict[str, str]]:
    return {t.locale: {"name": t.name, "description": t.description} for t in product.translations.all()}


def unique_colours(variants: Iterable[ProductVariant]) -> list[ProductVariant]:
    seen: dict[str, ProductVariant] = {}
    for v in variants:
        seen.setdefault(v.colour_slug, v)
    return list(seen.values())
