"""Product catalogue (MTS v2.1 §6 Catalogue; M02) under the launch-catalogue rules (decision 0006, P-12).

Rules kept from the MTS: unique SKU per variant, unique (product, size, colour), the variant's price is what is
sold (A-17), money is NUMERIC(12,2) plus a currency code, products are archived rather than deleted, status
columns carry CHECK constraints. From P-12: each category has its own ordered size list (letters or numbers) and
size chart in cm; colours are a staff-managed list; a product has one base price that a variant may override;
SKUs are AV-{category}-{style no.}-{colour}-{size} and never change once created.
"""

import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q


class Department(models.TextChoices):
    WOMEN = "women", "Women"
    MEN = "men", "Men"


class ProductStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class DemoArt(models.TextChoices):
    """Illustrated stand-ins for product photography until approved imagery exists (M4 limitation)."""

    DRESS = "dress"
    SHIRT = "shirt"
    COAT = "coat"
    TROUSERS = "trousers"
    KNIT = "knit"
    BLAZER = "blazer"
    KURTA = "kurta"
    SKIRT = "skirt"


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    department = models.CharField(max_length=10, choices=Department.choices)
    name_en = models.CharField(max_length=80)
    name_ur = models.CharField(max_length=80)
    position = models.PositiveIntegerField(default=0)
    # Three letters in every SKU of this category, e.g. WKU (decision 0006, #6). Never changed once used.
    code = models.CharField(max_length=3, unique=True)
    # Ordered sizes this category sells: letters (XS…XXL), numbers (28, 30…) or a single size (#4).
    sizes = models.JSONField(default=list)
    # [{"name": {"en": "Chest", "ur": "سینہ"}, "values": {"S": "88", "M": "96"}}], all in cm (#4).
    size_chart = models.JSONField(default=list)

    class Meta:
        ordering = ["department", "position", "slug"]
        constraints = [
            models.CheckConstraint(condition=Q(department__in=Department.values), name="category_department_valid"),
            models.CheckConstraint(condition=Q(code__regex=r"^[A-Z]{3}$"), name="category_code_format"),
        ]

    def __str__(self) -> str:
        return self.slug


class Colour(models.Model):
    """The staff-managed colour list (decision 0006, #5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=40, unique=True)
    code = models.CharField(max_length=3, unique=True)  # in SKUs, e.g. IVR
    name_en = models.CharField(max_length=40)
    name_ur = models.CharField(max_length=40)
    hex = models.CharField(max_length=7)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name_en"]
        constraints = [
            models.CheckConstraint(condition=Q(code__regex=r"^[A-Z]{3}$"), name="colour_code_format"),
            models.CheckConstraint(condition=Q(hex__regex=r"^#[0-9A-Fa-f]{6}$"), name="colour_hex_format"),
        ]

    def __str__(self) -> str:
        return self.slug


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    name_en = models.CharField(max_length=80)
    name_ur = models.CharField(max_length=80)
    description_en = models.TextField(blank=True)
    description_ur = models.TextField(blank=True)
    demo_art = models.CharField(max_length=20, choices=DemoArt.choices, blank=True)
    tone = models.CharField(max_length=7, default="#3B2F2F", help_text="Background tone for its card, #RRGGBB")
    is_published = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "slug"]

    def __str__(self) -> str:
        return self.slug


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=120, unique=True)
    department = models.CharField(max_length=10, choices=Department.choices)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    status = models.CharField(max_length=10, choices=ProductStatus.choices, default=ProductStatus.DRAFT)
    style_number = models.PositiveIntegerField(unique=True)  # the "0012" in AV-WKU-0012-IVR-M
    # One price per product (decision 0006, #7); each variant's price follows it unless overridden.
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_featured = models.BooleanField(default=False)
    # Staff-curated merchandising order for "Featured" sorting; seeded to alternate women's and men's.
    position = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    # Denormalised from active variants by services.refresh_price_range, so lists can sort and paginate by price.
    price_min = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    price_max = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, default="PKR")
    collections: "models.ManyToManyField[Collection, CollectionItem]" = models.ManyToManyField(
        Collection, through="CollectionItem", related_name="products"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(status__in=ProductStatus.values), name="product_status_valid"),
            models.CheckConstraint(condition=Q(department__in=Department.values), name="product_department_valid"),
            models.CheckConstraint(
                condition=Q(status="published", published_at__isnull=False) | ~Q(status="published"),
                name="product_published_has_date",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "position"]),
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["status", "price_min"]),
        ]

    def __str__(self) -> str:
        return self.slug


class ProductTranslation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="translations")
    locale = models.CharField(max_length=5)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    fabric = models.CharField(max_length=300, blank=True)
    care = models.CharField(max_length=300, blank=True)
    fit_note = models.CharField(max_length=300, blank=True)
    # Full-text search (R-07): name, category and colours weigh most, then description and fabric.
    search_vector = SearchVectorField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "locale"], name="product_translation_unique")]
        indexes = [GinIndex(fields=["search_vector"], name="product_translation_search")]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.locale}"


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="variants")
    sku = models.CharField(max_length=40, unique=True)
    size = models.CharField(max_length=10)
    colour = models.ForeignKey(Colour, on_delete=models.PROTECT, related_name="variants")
    # The price this variant sells at: the product's base price, or its own when overridden (#7).
    price = models.DecimalField(max_digits=12, decimal_places=2)
    price_overridden = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default="PKR")
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "sku"]
        constraints = [
            models.UniqueConstraint(fields=["product", "size", "colour"], name="variant_size_colour_unique"),
            models.CheckConstraint(condition=Q(price__gte=0), name="variant_price_not_negative"),
        ]

    def __str__(self) -> str:
        return self.sku


class ProductImage(models.Model):
    """A product image. `url` is a real asset (object storage, M5); `demo_art` is the illustrated stand-in."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.CharField(max_length=300, blank=True)  # "/media/products/<hash>.webp", served via the CDN
    thumb_url = models.CharField(max_length=300, blank=True)
    storage_key = models.CharField(max_length=200, blank=True)  # for removal from object storage
    demo_art = models.CharField(max_length=20, choices=DemoArt.choices, blank=True)
    colour_slug = models.SlugField(max_length=40, blank=True)
    alt_en = models.CharField(max_length=200)
    alt_ur = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.CheckConstraint(condition=~Q(url="") | ~Q(demo_art=""), name="image_has_source"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.position}"


class CollectionItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["collection", "product"], name="collection_item_unique")]

    def __str__(self) -> str:
        return f"{self.collection_id}:{self.product_id}"
