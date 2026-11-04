"""Staff catalogue writes (M5; decision 0006). Validation, audit and storefront refresh live here; who may call
what is decided by the staff API. Variants are never deleted (orders will reference them from M8): a variant
taken out of a product is deactivated, and its SKU never changes."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.cms.tasks import refresh_storefront
from apps.inventory import services as inventory

from . import services
from .models import Category, Colour, Department, Product, ProductStatus, ProductTranslation, ProductVariant

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CODE = re.compile(r"^[A-Z]{3}$")
SIZE = re.compile(r"^[A-Z0-9]{1,6}$")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
CM = re.compile(r"^\d{1,3}(\.\d)?$")
MAX_PRICE = Decimal("9999999.99")


class CatalogError(ValueError):
    """A readable reason, shown to staff as-is."""


def _refresh() -> None:
    transaction.on_commit(lambda: refresh_storefront.delay(["catalogue"]))


def _text(value: Any, label: str, max_length: int, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise CatalogError(f"{label}: must be text.")
    text = value.strip()
    if required and not text:
        raise CatalogError(f"{label} is required.")
    if len(text) > max_length:
        raise CatalogError(f"{label}: use at most {max_length} characters.")
    return text


def _slug(value: Any, label: str = "Address") -> str:
    if not isinstance(value, str) or not SLUG.match(value) or len(value) > 120:
        raise CatalogError(f"{label}: use lower-case letters, numbers and hyphens.")
    return value


def price(value: Any, label: str = "Price") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CatalogError(f"{label}: enter an amount in PKR, such as 14500.") from exc
    if not amount.is_finite() or amount < 0 or amount > MAX_PRICE or amount != amount.quantize(Decimal("0.01")):
        raise CatalogError(f"{label}: enter an amount in PKR with at most two decimals.")
    return amount


# --- Colours -----------------------------------------------------------------------------------------------


@transaction.atomic
def save_colour(colour: Colour | None, data: dict[str, Any], actor: Actor, request: Any = None) -> Colour:
    before = None if colour is None else {"name_en": colour.name_en, "name_ur": colour.name_ur, "hex": colour.hex}
    code = str(data.get("code", "")).upper()
    if colour is None:
        if not CODE.match(code):
            raise CatalogError("Code: three capital letters, used in SKUs (e.g. IVR).")
        slug = _slug(data.get("slug"), "Colour address")
        if Colour.objects.filter(slug=slug).exists() or Colour.objects.filter(code=code).exists():
            raise CatalogError("A colour with that address or code already exists.")
        colour = Colour(slug=slug, code=code, position=Colour.objects.count())
    elif code and code != colour.code:
        raise CatalogError("A colour's code can't change: it is part of existing SKUs.")
    colour.name_en = _text(data.get("name_en"), "English name", 40, required=True)
    colour.name_ur = _text(data.get("name_ur"), "Urdu name", 40) or colour.name_en
    hex_value = str(data.get("hex", ""))
    if not HEX.match(hex_value):
        raise CatalogError("Swatch: use a colour such as #F2EDE4.")
    colour.hex = hex_value.upper()
    colour.save()
    record(
        "catalog.colour.save",
        actor,
        target_type="colour",
        target_id=colour.slug,
        before=before,
        after={"name_en": colour.name_en, "name_ur": colour.name_ur, "hex": colour.hex},
        request=request,
    )
    _refresh()
    return colour


# --- Categories --------------------------------------------------------------------------------------------


def _sizes(value: Any) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= 20:
        raise CatalogError("Sizes: list 1 to 20 sizes in order, letters (XS…XXL) or numbers (28, 30…).")
    sizes = [str(s).strip().upper() for s in value]
    if any(not SIZE.match(s) for s in sizes) or len(set(sizes)) != len(sizes):
        raise CatalogError("Sizes: each size once, up to six letters or digits (e.g. M, XXL, 32).")
    return sizes


def _chart(value: Any, sizes: list[str]) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 12:
        raise CatalogError("Size chart: at most 12 measurements.")
    rows = []
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            raise CatalogError(f"Size chart row {index}: invalid.")
        name = row.get("name") or {}
        en = _text(name.get("en"), f"Size chart row {index} name", 40, required=True)
        ur = _text(name.get("ur"), f"Size chart row {index} Urdu name", 40)
        values = row.get("values") or {}
        if not isinstance(values, dict) or set(values) - set(sizes):
            raise CatalogError(f"Size chart row {index}: values only for this category's sizes.")
        clean = {}
        for size in sizes:
            cm = str(values.get(size, "")).strip()
            if cm and not CM.match(cm):
                raise CatalogError(f"Size chart {en}, {size}: centimetres, such as 96 or 96.5.")
            if cm:
                clean[size] = cm
        rows.append({"name": {"en": en, "ur": ur}, "values": clean})
    return rows


@transaction.atomic
def save_category(category: Category | None, data: dict[str, Any], actor: Actor, request: Any = None) -> Category:
    sizes = _sizes(data.get("sizes"))
    code = str(data.get("code", "")).upper()
    if category is None:
        if data.get("department") not in Department.values:
            raise CatalogError("Department: women or men.")
        if not CODE.match(code) or Category.objects.filter(code=code).exists():
            raise CatalogError("Code: three capital letters, not used by another category (e.g. WKU).")
        slug = _slug(data.get("slug"), "Category address")
        if Category.objects.filter(slug=slug).exists():
            raise CatalogError("Another category already uses that address.")
        category = Category(slug=slug, code=code, department=data["department"], position=Category.objects.count())
        before = None
    else:
        before = {"name_en": category.name_en, "sizes": category.sizes, "size_chart": category.size_chart}
        if code and code != category.code and category.products.exists():
            raise CatalogError("The code can't change: it is part of this category's SKUs.")
        if code and code != category.code:
            if not CODE.match(code) or Category.objects.filter(code=code).exists():
                raise CatalogError("Code: three capital letters, not used by another category.")
            category.code = code
        in_use = set(
            ProductVariant.objects.filter(product__category=category, is_active=True).values_list("size", flat=True)
        )
        missing = sorted(in_use - set(sizes))
        if missing:
            raise CatalogError(f"Products still sell these sizes: {', '.join(missing)}. Remove them there first.")
    category.name_en = _text(data.get("name_en"), "English name", 80, required=True)
    category.name_ur = _text(data.get("name_ur"), "Urdu name", 80) or category.name_en
    category.sizes = sizes
    category.size_chart = _chart(data.get("size_chart"), sizes)
    category.save()
    record(
        "catalog.category.save",
        actor,
        target_type="category",
        target_id=category.slug,
        before=before,
        after={"name_en": category.name_en, "sizes": sizes, "size_chart": category.size_chart},
        request=request,
    )
    _refresh()
    return category


# --- Products ----------------------------------------------------------------------------------------------

TRANSLATED = (
    ("name", 160, True),
    ("description", 4000, False),
    ("fabric", 300, False),
    ("care", 300, False),
    ("fit_note", 300, False),
)


def _translations(product: Product, data: dict[str, Any]) -> None:
    for locale in ("en", "ur"):
        copy = (data.get("copy") or {}).get(locale) or {}
        if not isinstance(copy, dict):
            raise CatalogError('Copy must be {"en": {...}, "ur": {...}}.')
        values = {
            field: _text(
                copy.get(field),
                f"{'Urdu ' if locale == 'ur' else ''}{field.replace('_', ' ')}",
                limit,
                required=required and locale == "en",
            )
            for field, limit, required in TRANSLATED
        }
        if locale == "ur" and not values["name"]:
            ProductTranslation.objects.filter(product=product, locale="ur").delete()
            continue
        ProductTranslation.objects.update_or_create(product=product, locale=locale, defaults=values)


def product_snapshot(product: Product) -> dict[str, Any]:
    return {
        "slug": product.slug,
        "category": product.category.slug,
        "status": product.status,
        "base_price": f"{product.base_price:.2f}",
        "copy": {t.locale: {f: getattr(t, f) for f, _, _ in TRANSLATED} for t in product.translations.all()},
    }


@transaction.atomic
def create_product(data: dict[str, Any], actor: Actor, can_price: bool, request: Any = None) -> Product:
    slug = _slug(data.get("slug"))
    if Product.objects.filter(slug=slug).exists():
        raise CatalogError("Another product already uses that address.")
    category = Category.objects.filter(slug=data.get("category")).first()
    if category is None:
        raise CatalogError("Category: choose one.")
    base = price(data.get("base_price", 0)) if can_price else Decimal("0")
    product = Product.objects.create(
        slug=slug,
        department=category.department,
        category=category,
        status=ProductStatus.DRAFT,
        style_number=services.next_style_number(),
        base_price=base,
        position=Product.objects.count(),
        is_featured=bool(data.get("is_featured", False)),
    )
    _translations(product, data)
    record(
        "catalog.product.create",
        actor,
        target_type="product",
        target_id=product.pk,
        after=product_snapshot(product),
        request=request,
    )
    return product


@transaction.atomic
def update_product(product: Product, data: dict[str, Any], actor: Actor, request: Any = None) -> Product:
    """Details only; prices go through set_prices (they need `prices.edit` and re-confirmation)."""
    product = Product.objects.select_for_update().get(pk=product.pk)
    before = product_snapshot(product)
    category = Category.objects.filter(slug=data.get("category", product.category.slug)).first()
    if category is None:
        raise CatalogError("Category: choose one.")
    if category != product.category and product.variants.exists():
        raise CatalogError("A product with variants keeps its category: its SKUs carry the category code.")
    new_slug = _slug(data.get("slug", product.slug))
    if new_slug != product.slug:
        if Product.objects.filter(slug=new_slug).exists():
            raise CatalogError("Another product already uses that address.")
        if product.status == ProductStatus.PUBLISHED:
            from apps.cms.publishing import add_slug_redirect

            add_slug_redirect(f"/products/{product.slug}", f"/products/{new_slug}")
        product.slug = new_slug
    product.category, product.department = category, category.department
    product.is_featured = bool(data.get("is_featured", product.is_featured))
    product.save()
    _translations(product, data)
    services.refresh_search(product)
    record(
        "catalog.product.update",
        actor,
        target_type="product",
        target_id=product.pk,
        before=before,
        after=product_snapshot(product),
        request=request,
    )
    if product.status == ProductStatus.PUBLISHED:
        _refresh()
    return product


@transaction.atomic
def set_variants(product: Product, colours: Any, sizes: Any, actor: Actor, request: Any = None) -> Product:
    """The colour-by-size grid a product sells. New combinations get a SKU and a stock record; removed ones are
    deactivated, never deleted; switching one back on reuses its SKU."""
    product = Product.objects.select_for_update().get(pk=product.pk)
    if not isinstance(colours, list) or not isinstance(sizes, list) or not colours or not sizes:
        raise CatalogError("Choose at least one colour and one size.")
    colour_rows = {c.slug: c for c in Colour.objects.filter(slug__in=colours)}
    if len(colour_rows) != len(set(colours)):
        raise CatalogError("Unknown colour.")
    if set(sizes) - set(product.category.sizes):
        raise CatalogError(f"Sizes: this category sells {', '.join(product.category.sizes)}.")
    wanted = {(c, s) for c in colours for s in sizes}
    before = sorted(
        f"{v.colour.slug}/{v.size}" for v in product.variants.filter(is_active=True).select_related("colour")
    )
    existing = {(v.colour.slug, v.size): v for v in product.variants.select_related("colour")}
    created = []
    for index, (c, s) in enumerate(
        sorted(wanted, key=lambda k: (colours.index(k[0]), product.category.sizes.index(k[1])))
    ):
        variant = existing.get((c, s))
        if variant is None:
            variant = ProductVariant.objects.create(
                product=product,
                size=s,
                colour=colour_rows[c],
                price=product.base_price,
                sku=services.sku_for(product.category, product.style_number, colour_rows[c], s),
                position=index,
            )
            created.append(variant.pk)
        else:
            variant.is_active, variant.position = True, index
            variant.save(update_fields=["is_active", "position"])
    for key, variant in existing.items():
        if key not in wanted and variant.is_active:
            variant.is_active = False
            variant.save(update_fields=["is_active"])
    inventory.ensure_items(created)
    services.refresh_price_range(product)
    services.refresh_search(product)
    record(
        "catalog.variants.set",
        actor,
        target_type="product",
        target_id=product.pk,
        before={"variants": before},
        after={"variants": sorted(f"{c}/{s}" for c, s in wanted)},
        request=request,
    )
    if product.status == ProductStatus.PUBLISHED:
        _refresh()
    return product


@transaction.atomic
def set_prices(product: Product, base_price: Any, overrides: Any, actor: Actor, request: Any = None) -> Product:
    """Base price and per-variant overrides ({sku: amount or null}). Audited with before and after (MTS §9)."""
    product = Product.objects.select_for_update().get(pk=product.pk)
    before = {
        "base_price": f"{product.base_price:.2f}",
        "variants": {v.sku: f"{v.price:.2f}" for v in product.variants.filter(price_overridden=True)},
    }
    product.base_price = price(base_price, "Base price")
    product.save(update_fields=["base_price", "updated_at"])
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise CatalogError("Overrides: {sku: amount or null}.")
        variants = {v.sku: v for v in product.variants.all()}
        for sku, amount in overrides.items():
            variant = variants.get(sku)
            if variant is None:
                raise CatalogError(f"Unknown SKU {sku}.")
            if amount in (None, ""):
                variant.price_overridden = False
            else:
                variant.price_overridden, variant.price = True, price(amount, sku)
            variant.save(update_fields=["price_overridden", "price"])
    services.apply_base_price(product)
    after = {
        "base_price": f"{product.base_price:.2f}",
        "variants": {v.sku: f"{v.price:.2f}" for v in product.variants.filter(price_overridden=True)},
    }
    record(
        "catalog.prices.change",
        actor,
        target_type="product",
        target_id=product.pk,
        before=before,
        after=after,
        request=request,
    )
    if product.status == ProductStatus.PUBLISHED:
        _refresh()
    return product


def publish_problems(product: Product) -> list[str]:
    problems = []
    if not product.translations.filter(locale="en").exists():
        problems.append("Add an English name.")
    active = product.variants.filter(is_active=True)
    if not active.exists():
        problems.append("Add at least one colour and size.")
    if active.filter(price__lte=0).exists() or product.base_price <= 0:
        problems.append("Set a price above zero.")
    return problems


@transaction.atomic
def set_status(product: Product, status: str, actor: Actor, request: Any = None) -> Product:
    product = Product.objects.select_for_update().get(pk=product.pk)
    if status not in ProductStatus.values:
        raise CatalogError("Status: draft, published or archived.")
    if status == ProductStatus.PUBLISHED:
        problems = publish_problems(product)
        if problems:
            raise CatalogError(" ".join(problems))
        product.published_at = product.published_at or timezone.now()
    before = product.status
    product.status = status
    product.save(update_fields=["status", "published_at", "updated_at"])
    record(
        "catalog.product.status",
        actor,
        target_type="product",
        target_id=product.pk,
        before={"status": before},
        after={"status": status},
        request=request,
    )
    _refresh()
    return product
