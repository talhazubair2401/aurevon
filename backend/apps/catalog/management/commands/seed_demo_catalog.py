# ruff: noqa: RUF001  (Urdu copy correctly uses the Arabic full stop)
"""Demo catalogue and storefront content for local development and review (M4).

Idempotent: re-running updates the same records. Never run in production; the real launch catalogue is P-12.
Product imagery is illustrated stand-ins (`demo_art`) until approved photography or Flow assets exist.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog import services
from apps.catalog.models import (
    Category,
    Collection,
    CollectionItem,
    Department,
    Product,
    ProductImage,
    ProductStatus,
    ProductTranslation,
    ProductVariant,
)
from apps.cms.models import Banner, HomepageSection

COLOURS: dict[str, tuple[str, str, str]] = {
    "ivory": ("Ivory", "ہاتھی دانت", "#F2EDE4"),
    "black": ("Black", "سیاہ", "#151515"),
    "camel": ("Camel", "اونٹی", "#B08B5E"),
    "chocolate": ("Chocolate", "چاکلیٹ", "#4A3426"),
    "sand": ("Sand", "ریتیلا", "#D8C8AE"),
    "olive": ("Olive", "زیتونی", "#5E6347"),
    "midnight": ("Midnight", "گہرا نیلا", "#1C2230"),
    "stone-grey": ("Stone Grey", "پتھریلا سرمئی", "#9A958E"),
    "rose-dust": ("Rose Dust", "گلابی خاک", "#C9A79F"),
    "sage": ("Sage", "سیج سبز", "#A3AC94"),
}

CATEGORIES = [
    ("women-dresses", Department.WOMEN, "Dresses", "ڈریسز"),
    ("women-kurtas", Department.WOMEN, "Kurtas", "کرتے"),
    ("women-outerwear", Department.WOMEN, "Outerwear", "بیرونی لباس"),
    ("women-trousers", Department.WOMEN, "Trousers", "پتلونیں"),
    ("women-skirts", Department.WOMEN, "Skirts", "اسکرٹس"),
    ("men-shirts", Department.MEN, "Shirts", "قمیضیں"),
    ("men-kurtas", Department.MEN, "Kurtas", "کرتے"),
    ("men-knitwear", Department.MEN, "Knitwear", "بنائی کے لباس"),
    ("men-tailoring", Department.MEN, "Tailoring", "سلائی شدہ لباس"),
    ("men-trousers", Department.MEN, "Trousers", "پتلونیں"),
]

COLLECTIONS = [
    (
        "heritage-edit",
        "The Heritage Edit",
        "ہیریٹیج ایڈٹ",
        "Craft traditions, cut for today.",
        "روایتی کاریگری، آج کے انداز میں۔",
        "kurta",
        "#3B2F2F",
    ),
    (
        "modern-tailoring",
        "Modern Tailoring",
        "جدید سلائی",
        "Sharp lines with an easy hand.",
        "نفیس تراش، آرام دہ انداز۔",
        "blazer",
        "#121212",
    ),
    ("evening", "Evening", "شام", "Quiet glamour for after dark.", "شام کے لیے پُروقار انداز۔", "dress", "#2A2420"),
]

# slug, department, category, art, EN name, UR name, price, colours, sizes, featured, collections, days since published
PRODUCTS: list[tuple[Any, ...]] = [
    (
        "silk-column-dress",
        "women",
        "women-dresses",
        "dress",
        "Silk Column Dress",
        "ریشمی کالم ڈریس",
        "38500",
        ["ivory", "black"],
        ["XS", "S", "M", "L"],
        True,
        ["evening"],
        4,
    ),
    (
        "oxford-poplin-shirt",
        "men",
        "men-shirts",
        "shirt",
        "Oxford Poplin Shirt",
        "آکسفورڈ پاپلن قمیض",
        "8900",
        ["ivory", "midnight", "sage"],
        ["S", "M", "L", "XL"],
        True,
        ["modern-tailoring"],
        40,
    ),
    (
        "embroidered-lawn-kurta",
        "women",
        "women-kurtas",
        "kurta",
        "Embroidered Lawn Kurta",
        "کڑھائی والا لان کرتا",
        "14500",
        ["sand", "rose-dust"],
        ["XS", "S", "M", "L", "XL"],
        True,
        ["heritage-edit"],
        9,
    ),
    (
        "merino-crew-knit",
        "men",
        "men-knitwear",
        "knit",
        "Merino Crew Knit",
        "میرینو کریو سویٹر",
        "16800",
        ["camel", "stone-grey", "black"],
        ["S", "M", "L", "XL"],
        True,
        [],
        12,
    ),
    (
        "wool-wrap-coat",
        "women",
        "women-outerwear",
        "coat",
        "Wool Wrap Coat",
        "اونی ریپ کوٹ",
        "48500",
        ["camel", "chocolate"],
        ["XS", "S", "M", "L"],
        True,
        ["modern-tailoring"],
        2,
    ),
    (
        "unstructured-linen-blazer",
        "men",
        "men-tailoring",
        "blazer",
        "Unstructured Linen Blazer",
        "لینن بلیزر",
        "34500",
        ["sand", "midnight"],
        ["S", "M", "L", "XL"],
        True,
        ["modern-tailoring"],
        6,
    ),
    (
        "pleated-midi-skirt",
        "women",
        "women-skirts",
        "skirt",
        "Pleated Midi Skirt",
        "پلیٹڈ مڈی اسکرٹ",
        "12900",
        ["black", "olive"],
        ["XS", "S", "M", "L"],
        True,
        [],
        55,
    ),
    (
        "cotton-silk-kurta",
        "men",
        "men-kurtas",
        "kurta",
        "Cotton Silk Kurta",
        "کاٹن سلک کرتا",
        "13500",
        ["ivory", "chocolate"],
        ["S", "M", "L", "XL", "XXL"],
        True,
        ["heritage-edit"],
        3,
    ),
    (
        "wide-leg-trouser",
        "women",
        "women-trousers",
        "trousers",
        "Wide-Leg Trouser",
        "وائیڈ لیگ پتلون",
        "11500",
        ["black", "sand", "stone-grey"],
        ["XS", "S", "M", "L", "XL"],
        False,
        [],
        70,
    ),
    (
        "pleated-wool-trouser",
        "men",
        "men-trousers",
        "trousers",
        "Pleated Wool Trouser",
        "پلیٹڈ اونی پتلون",
        "15900",
        ["stone-grey", "midnight"],
        ["S", "M", "L", "XL"],
        False,
        ["modern-tailoring"],
        22,
    ),
    (
        "satin-slip-dress",
        "women",
        "women-dresses",
        "dress",
        "Satin Slip Dress",
        "ساٹن سلپ ڈریس",
        "24500",
        ["chocolate", "rose-dust"],
        ["XS", "S", "M"],
        False,
        ["evening"],
        15,
    ),
    (
        "textured-overshirt",
        "men",
        "men-shirts",
        "shirt",
        "Textured Overshirt",
        "ٹیکسچرڈ اوور شرٹ",
        "12500",
        ["olive", "camel"],
        ["S", "M", "L", "XL"],
        False,
        [],
        30,
    ),
    (
        "block-print-kurta",
        "women",
        "women-kurtas",
        "kurta",
        "Block-Print Kurta",
        "بلاک پرنٹ کرتا",
        "9800",
        ["ivory", "sage"],
        ["XS", "S", "M", "L"],
        False,
        ["heritage-edit"],
        25,
    ),
    (
        "cable-knit-cardigan",
        "men",
        "men-knitwear",
        "knit",
        "Cable-Knit Cardigan",
        "کیبل نِٹ کارڈیگن",
        "19500",
        ["ivory", "chocolate"],
        ["M", "L", "XL"],
        False,
        [],
        50,
    ),
    (
        "tailored-cape-blazer",
        "women",
        "women-outerwear",
        "blazer",
        "Tailored Cape Blazer",
        "کیپ بلیزر",
        "29500",
        ["black", "ivory"],
        ["XS", "S", "M", "L"],
        False,
        ["modern-tailoring", "evening"],
        8,
    ),
    (
        "double-breasted-suit-jacket",
        "men",
        "men-tailoring",
        "blazer",
        "Double-Breasted Jacket",
        "ڈبل بریسٹڈ جیکٹ",
        "42500",
        ["midnight", "black"],
        ["S", "M", "L", "XL"],
        False,
        ["modern-tailoring", "evening"],
        18,
    ),
    (
        "knit-midi-dress",
        "women",
        "women-dresses",
        "dress",
        "Knit Midi Dress",
        "نِٹ مڈی ڈریس",
        "18900",
        ["camel", "stone-grey"],
        ["XS", "S", "M", "L"],
        False,
        [],
        35,
    ),
    (
        "band-collar-shirt",
        "men",
        "men-shirts",
        "shirt",
        "Band-Collar Shirt",
        "بینڈ کالر قمیض",
        "7900",
        ["ivory", "black"],
        ["S", "M", "L", "XL", "XXL"],
        False,
        ["heritage-edit"],
        11,
    ),
    (
        "chikankari-kurta",
        "women",
        "women-kurtas",
        "kurta",
        "Chikankari Kurta",
        "چکن کاری کرتا",
        "21500",
        ["ivory", "rose-dust"],
        ["XS", "S", "M", "L"],
        False,
        ["heritage-edit", "evening"],
        5,
    ),
    (
        "waistcoat-kurta-set",
        "men",
        "men-kurtas",
        "kurta",
        "Waistcoat Kurta Set",
        "واسکٹ کرتا سیٹ",
        "26500",
        ["sand", "midnight"],
        ["S", "M", "L", "XL"],
        False,
        ["heritage-edit", "evening"],
        7,
    ),
    (
        "cigarette-trouser",
        "women",
        "women-trousers",
        "trousers",
        "Cigarette Trouser",
        "سگریٹ پتلون",
        "10500",
        ["black", "camel"],
        ["XS", "S", "M", "L"],
        False,
        ["modern-tailoring"],
        45,
    ),
    (
        "relaxed-chino",
        "men",
        "men-trousers",
        "trousers",
        "Relaxed Chino",
        "ریلیکسڈ چینو",
        "8500",
        ["sand", "olive", "black"],
        ["S", "M", "L", "XL"],
        False,
        [],
        60,
    ),
    (
        "quilted-gilet",
        "women",
        "women-outerwear",
        "coat",
        "Quilted Gilet",
        "کوئلٹڈ جیلے",
        "16500",
        ["olive", "black"],
        ["S", "M", "L"],
        False,
        [],
        28,
    ),
    (
        "wool-overcoat",
        "men",
        "men-tailoring",
        "coat",
        "Wool Overcoat",
        "اونی اوور کوٹ",
        "46500",
        ["camel", "stone-grey"],
        ["M", "L", "XL"],
        False,
        ["modern-tailoring"],
        1,
    ),
]

DESCRIPTION_EN = "Demo product for review. Final copy, materials and care arrive with the launch catalogue (P-12)."
DESCRIPTION_UR = "جائزے کے لیے نمونہ پروڈکٹ۔ حتمی تفصیل لانچ کیٹلاگ کے ساتھ آئے گی۔"

HOME_SECTIONS: list[tuple[str, int, dict[str, Any]]] = [
    (
        "hero",
        0,
        {
            "en": {
                "eyebrow": "Autumn / Winter 2026",
                "title": "Modern Style. Timeless Confidence.",
                "subtitle": "Heritage craft and modern tailoring, made to be worn now.",
                "primary_label": "Shop Women",
                "primary_href": "/shop?department=women",
                "secondary_label": "Shop Men",
                "secondary_href": "/shop?department=men",
            },
            "ur": {
                "eyebrow": "خزاں / سرما 2026",
                "title": "جدید انداز۔ لازوال اعتماد۔",
                "subtitle": "روایتی کاریگری اور جدید سلائی، آج پہننے کے لیے۔",
                "primary_label": "خواتین",
                "secondary_label": "مرد",
            },
        },
    ),
    (
        "collections",
        1,
        {
            "en": {"title": "The Collections", "subtitle": "Three ways into the season."},
            "ur": {"title": "کلیکشنز", "subtitle": "اس موسم کے تین انداز۔"},
        },
    ),
    (
        "featured_products",
        2,
        {
            "en": {"title": "Featured", "link_label": "View all", "link_href": "/shop"},
            "ur": {"title": "منتخب", "link_label": "سب دیکھیں"},
        },
    ),
    (
        "new_arrivals",
        3,
        {
            "en": {"title": "New Arrivals", "link_label": "Shop new in", "link_href": "/shop?sort=newest"},
            "ur": {"title": "نئی آمد", "link_label": "نئی مصنوعات"},
        },
    ),
    (
        "brand_story",
        4,
        {
            "en": {
                "eyebrow": "Our story",
                "title": "Heritage, reconsidered",
                "body": (
                    "AureVon begins with the craft we grew up around: hand embroidery, fine cotton and the patience "
                    "of a good tailor. We pare it back to clean lines and quiet colour, so every piece feels as "
                    "certain today as it will in ten years."
                ),
                "link_label": "Explore the Heritage Edit",
                "link_href": "/shop?collection=heritage-edit",
            },
            "ur": {
                "eyebrow": "ہماری کہانی",
                "title": "روایت، نئے انداز میں",
                "body": (
                    "AureVon کی ابتدا اُس کاریگری سے ہوتی ہے جس کے ساتھ ہم بڑے ہوئے: ہاتھ کی کڑھائی، عمدہ کاٹن اور "
                    "ایک اچھے درزی کا صبر۔ ہم اسے صاف لکیروں اور پُرسکون رنگوں میں ڈھالتے ہیں، تاکہ ہر لباس آج بھی "
                    "اتنا ہی پُراعتماد لگے جتنا دس سال بعد۔"
                ),
                "link_label": "ہیریٹیج ایڈٹ دیکھیں",
            },
        },
    ),
]

SHOP_BANNER = {
    "en": {
        "title": "BEYOND THE ORDINARY",
        "body": "Pieces made with intent: heritage technique, modern proportion.",
        "link_label": "Explore the Heritage Edit",
        "link_href": "/shop?collection=heritage-edit",
    },
    "ur": {
        "title": "BEYOND THE ORDINARY",
        "body": "سوچ سمجھ کر بنائے گئے لباس: روایتی فن، جدید تراش۔",
        "link_label": "ہیریٹیج ایڈٹ دیکھیں",
    },
}


class Command(BaseCommand):
    help = "Create or update the demo catalogue and storefront content (local and staging only)."

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not getattr(settings, "ALLOW_DEMO_DATA", False):
            raise CommandError("Demo data is only for local development and review environments.")
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS(f"Demo catalogue ready: {len(PRODUCTS)} products."))

    def _seed(self) -> None:
        cats = {}
        for position, (slug, dept, en, ur) in enumerate(CATEGORIES):
            cats[slug], _ = Category.objects.update_or_create(
                slug=slug, defaults={"department": dept, "name_en": en, "name_ur": ur, "position": position}
            )
        cols = {}
        for position, (slug, en, ur, den, dur, art, tone) in enumerate(COLLECTIONS):
            cols[slug], _ = Collection.objects.update_or_create(
                slug=slug,
                defaults={
                    "name_en": en,
                    "name_ur": ur,
                    "description_en": den,
                    "description_ur": dur,
                    "demo_art": art,
                    "tone": tone,
                    "is_published": True,
                    "position": position,
                },
            )
        now = timezone.now()
        for position, row in enumerate(PRODUCTS):
            slug, dept, cat, art, en, ur, price, colours, sizes, featured, collections, age = row
            product, _ = Product.objects.update_or_create(
                slug=slug,
                defaults={
                    "department": dept,
                    "category": cats[cat],
                    "status": ProductStatus.PUBLISHED,
                    "is_featured": featured,
                    "position": position,
                    "published_at": now - timedelta(days=age),
                },
            )
            for locale, name, desc in (("en", en, DESCRIPTION_EN), ("ur", ur, DESCRIPTION_UR)):
                ProductTranslation.objects.update_or_create(
                    product=product, locale=locale, defaults={"name": name, "description": desc}
                )
            sku_base = "".join(part[0] for part in slug.split("-")).upper()
            for ci, colour in enumerate(colours):
                cen, cur, chex = COLOURS[colour]
                for si, size in enumerate(sizes):
                    ProductVariant.objects.update_or_create(
                        product=product,
                        size=size,
                        colour_slug=colour,
                        defaults={
                            "sku": f"AV-{sku_base}-{position:02d}-{colour[:3].upper()}-{size}",
                            "colour_name_en": cen,
                            "colour_name_ur": cur,
                            "colour_hex": chex,
                            "price": Decimal(price),
                            "position": ci * 10 + si,
                        },
                    )
            ProductImage.objects.filter(product=product).delete()
            for ci, colour in enumerate(colours):
                ProductImage.objects.create(
                    product=product,
                    demo_art=art,
                    colour_slug=colour,
                    position=ci,
                    alt_en=f"{en} in {COLOURS[colour][0]} (illustration)",
                    alt_ur=f"{ur}، {COLOURS[colour][1]} (خاکہ)",
                )
            CollectionItem.objects.filter(product=product).exclude(collection__slug__in=collections).delete()
            for col in collections:
                CollectionItem.objects.get_or_create(collection=cols[col], product=product)
            services.refresh_price_range(product)

        for key, position, content in HOME_SECTIONS:
            HomepageSection.objects.update_or_create(
                key=key, defaults={"position": position, "is_enabled": True, "content": content}
            )
        Banner.objects.update_or_create(key="shop_editorial", defaults={"is_enabled": True, "content": SHOP_BANNER})
