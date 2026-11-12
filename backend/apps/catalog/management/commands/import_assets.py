"""Import the owner's photographs and product details from an assets folder.

    python manage.py import_assets /path/to/aurevon-assets

Layout (any part may be missing):
    products/<product-slug>/1.jpg 2.jpg …  info.txt
    collections/<collection-slug>.jpg
    story.jpg
    hero.mp4       (optional silent loop behind the homepage hero; hero-poster.jpg or hero.jpg is its first frame)

- Products: details from info.txt (name, price, sizes, colours, fabric, description, care) update the existing
  product with that slug; photographs are centre-cropped to 4:5 and added through the normal image pipeline
  (they replace earlier photographs and the illustrated stand-ins). Sizes and colours not listed are switched
  off, not deleted. The first product folder becomes the homepage hero garment.
- Collections and story: stored in the media library and set as the collection cover and brand-story photo.
Re-running replaces what an earlier run added. Every change goes through the services and the audit log.
"""

import hashlib
import io
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageFilter, ImageOps

from apps.audit.services import SYSTEM, record
from apps.catalog import editing, images, services
from apps.catalog.editing import _refresh
from apps.catalog.models import Collection, Product
from apps.cms.models import HomepageSection
from apps.inventory import services as inventory
from integrations.storage import storage

FIELDS = {
    "product name": "name",
    "price": "price",
    "available sizes": "sizes",
    "available colours": "colours",
    "available colors": "colours",
    "fabric": "fabric",
    "description": "description",
    "care instructions": "care",
}


def parse_info(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    key = None
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Za-z ]+):\s*(.*)$", line)
        if m and m.group(1).strip().lower() in FIELDS:
            key = FIELDS[m.group(1).strip().lower()]
            out[key] = m.group(2).strip()
        elif key and line.strip():
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def focus_left(img: Image.Image, crop_w: int) -> int:
    """Left edge of a crop window centred on the photo's detail (the garment), so an off-centre subject isn't cut."""
    small = img.convert("L").resize((200, max(3, round(200 * img.height / img.width))))
    edges = small.filter(ImageFilter.FIND_EDGES)
    cols = [sum(edges.getpixel((x, y)) for y in range(1, edges.height - 1)) for x in range(1, 199)]  # type: ignore[misc]
    floor = sorted(cols)[len(cols) // 2]  # flat background texture
    weights = [max(0, c - floor) for c in cols]
    if not sum(weights):
        return (img.width - crop_w) // 2
    centre = (sum((x + 1) * w for x, w in enumerate(weights)) / sum(weights)) * img.width / 200
    return max(0, min(round(centre - crop_w / 2), img.width - crop_w))


def portrait(path: Path) -> bytes:
    """Centre-crop to 4:5 and scale to the catalogue's 1600 x 2000 page size."""
    with Image.open(path) as opened:
        img = ImageOps.exif_transpose(opened).convert("RGB")
    w, h = img.size
    if w / h > 0.8:
        nw = round(h * 0.8)
        img = img.crop((left := focus_left(img, nw), 0, left + nw, h))
    else:
        nh = round(w / 0.8)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    img = img.resize((1600, 2000), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def store_photo(path: Path, folder: str, width: int = 2400) -> str:
    with Image.open(path) as opened:
        img = ImageOps.exif_transpose(opened).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=84)
    data = buf.getvalue()
    key = f"{folder}/{hashlib.sha256(data).hexdigest()[:32]}.webp"
    storage().put(key, data, "image/webp")
    return f"{settings.MEDIA_URL}{key}"


def colour_slugs(wanted: str) -> list[str]:
    """Match listed colours ("Charcoal Black", "Ivory Off-White") to the store's colours, one per listed name."""
    from apps.catalog.models import Colour

    found: list[str] = []
    for part in re.split(r"[,/]| and ", wanted):
        words = {w for w in re.split(r"[^a-z]+", part.lower()) if w}
        for colour in Colour.objects.all():
            if colour.slug in words or set(re.split(r"[^a-z]+", colour.name_en.lower())) & words:
                if colour.slug not in found:
                    found.append(colour.slug)
                break
    return found


def set_section(key: str, field: str, value: str) -> None:
    section = HomepageSection.objects.filter(key=key).first()
    if section is None:
        return
    for attr in ("content", "draft"):
        data = getattr(section, attr)
        if isinstance(data, dict):
            data.setdefault("en", {})[field] = value
    section.save()


class Command(BaseCommand):
    help = "Import product photographs and details, collection covers and the story photo from a folder."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("folder")

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(options["folder"])
        if not root.is_dir():
            raise CommandError(f"No folder at {root}")
        folders = sorted((root / "products").glob("*/"))
        for folder in folders:
            self.product(folder)
        # The hero garment: a coat if there is one (the hanger scene), otherwise the first product.
        hero = next((f.name for f in folders if "coat" in f.name), folders[0].name if folders else None)
        for photo in sorted((root / "collections").glob("*.jp*g")):
            col = Collection.objects.filter(slug=photo.stem).first()
            if col is None:
                self.stdout.write(self.style.WARNING(f"skipped {photo.name}: no collection called {photo.stem}"))
                continue
            col.cover_url = store_photo(photo, "collections")
            col.cover_alt_en = f"{col.name_en} collection"
            col.cover_alt_ur = col.name_ur
            col.save(update_fields=["cover_url", "cover_alt_en", "cover_alt_ur"])
            record(
                "catalog.collection.cover",
                SYSTEM,
                target_type="collection",
                target_id=col.pk,
                after={"cover": col.cover_url},
            )
            self.stdout.write(f"collection {col.slug}: cover set")
        story = next(iter(sorted(root.glob("story.jp*g"))), None)
        if story:
            set_section("brand_story", "image", store_photo(story, "cms"))
            self.stdout.write("brand story: photo set")
        video = next(iter(sorted(root.glob("hero.mp4"))), None)
        if video:
            data = video.read_bytes()
            key = f"cms/{hashlib.sha256(data).hexdigest()[:32]}.mp4"
            storage().put(key, data, "video/mp4")
            set_section("hero", "video", f"{settings.MEDIA_URL}{key}")
            still = next((p for p in (root / "hero-poster.jpg", root / "hero.jpg") if p.exists()), None)
            set_section("hero", "video_poster", store_photo(still, "cms") if still else "")
            self.stdout.write("hero: background video set")
        if hero:
            set_section("hero", "feature_product", hero)
            self.stdout.write(f"hero: featured garment {hero}")
        _refresh()  # published lists are cached; refresh once

    @transaction.atomic
    def product(self, folder: Path) -> None:
        product = Product.objects.filter(slug=folder.name).first()
        if product is None:
            self.stdout.write(self.style.WARNING(f"skipped {folder.name}: no product with that slug"))
            return
        info_file = folder / "info.txt"
        info = parse_info(info_file.read_text(encoding="utf-8-sig")) if info_file.exists() else {}
        en = product.translations.filter(locale="en").first()
        if en is not None:
            for field in ("name", "description", "fabric", "care"):
                value = info.get(field, "")
                if value:
                    limit = getattr(en._meta.get_field(field), "max_length", None)
                    setattr(en, field, value[:limit] if limit else value)
            en.save()
        price = re.sub(r"[^\d.]", "", info.get("price", ""))
        if price:
            product.base_price = Decimal(price)
            product.save(update_fields=["base_price"])
            services.apply_base_price(product)
        colours = colour_slugs(info.get("colours", ""))
        sizes = [
            x
            for x in product.category.sizes
            if x.upper() in {s.strip().upper() for s in info.get("sizes", "").split(",")}
        ]
        if colours and sizes:
            before = set(product.variants.values_list("pk", flat=True))
            editing.set_variants(product, colours, sizes, SYSTEM)
            for v in product.variants.filter(is_active=True).exclude(pk__in=before):
                inventory.receive(v.pk, 10, "receipt", "assets import", "demo stock for a new size or colour")
        keep_colours = set(colours)
        for old in list(product.images.exclude(url="")):
            images.remove_image(old, SYSTEM)
        colour = next(iter(keep_colours)) if len(keep_colours) == 1 else ""
        name = info.get("name") or (en.name if en else product.slug)
        photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
        for n, photo in enumerate(photos, 1):
            images.add_image(product, portrait(photo), colour, f"{name}, view {n}", "", SYSTEM)
        product.images.filter(url="").delete()  # no illustrated stand-ins once it has photographs
        self.stdout.write(f"product {product.slug}: {len(photos)} photos, colours {sorted(keep_colours) or 'all'}")
