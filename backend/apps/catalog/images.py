"""Product image uploads (decision 0006, #9; MTS §12 uploads).

The file's type is read from its content, never its name. Images must be 4:5 portrait and at least
1600 x 2000 px. Every image is re-encoded, which drops metadata (location, camera) and anything hidden in the
file: a 1600 x 2000 WebP for the page and an 800 x 1000 one for cards. Keys are the content hash, so the same
photo uploaded twice is stored once and every stored file can be cached for good.
"""

import hashlib
import io
from typing import Any

from django.conf import settings
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.audit.services import Actor, record
from integrations.storage import storage

from .editing import CatalogError, _refresh, _text
from .models import Product, ProductImage, ProductStatus

ALLOWED = {"JPEG", "PNG", "WEBP"}
MAX_BYTES = 15 * 1024 * 1024
MIN_W, MIN_H = 1600, 2000
RATIO, TOLERANCE = 4 / 5, 0.02
MAX_PIXELS = 60_000_000  # refuse decompression bombs
SIZES = {"page": (1600, 2000), "thumb": (800, 1000)}


def _encode(image: Image.Image, size: tuple[int, int]) -> bytes:
    out = io.BytesIO()
    fitted = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    fitted.save(out, format="WEBP", quality=85, method=6)
    return out.getvalue()


def process(data: bytes) -> dict[str, bytes]:
    if len(data) > MAX_BYTES:
        raise CatalogError("The image is larger than 15 MB.")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            kind = probe.format
            probe.verify()
        opened = Image.open(io.BytesIO(data))
        opened.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise CatalogError("That file isn't a JPEG, PNG or WebP image.") from exc
    if kind not in ALLOWED:
        raise CatalogError("Use a JPEG, PNG or WebP image.")
    image: Image.Image = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = image.size
    if width < MIN_W or height < MIN_H:
        raise CatalogError(f"The image is {width} x {height} px; use at least {MIN_W} x {MIN_H} px.")
    if abs(width / height - RATIO) > TOLERANCE:
        raise CatalogError("Use a 4:5 portrait image (for example 1600 x 2000 px).")
    return {name: _encode(image, size) for name, size in SIZES.items()}


@transaction.atomic
def add_image(
    product: Product, data: bytes, colour: str, alt_en: Any, alt_ur: Any, actor: Actor, request: Any = None
) -> ProductImage:
    if colour and not product.variants.filter(colour__slug=colour).exists():
        raise CatalogError("Choose one of this product's colours, or none for all colours.")
    alt = _text(alt_en, "Description for screen readers (English)", 200, required=True)
    alt_ur_text = _text(alt_ur, "Description for screen readers (Urdu)", 200)
    files = process(data)
    digest = hashlib.sha256(files["page"]).hexdigest()[:32]
    keys = {name: f"products/{digest}-{name}.webp" for name in files}
    store = storage()
    for name, content in files.items():
        store.put(keys[name], content, "image/webp")
    position = (product.images.order_by("-position").values_list("position", flat=True).first() or 0) + 1
    image = ProductImage.objects.create(
        product=product,
        url=f"{settings.MEDIA_URL}{keys['page']}",
        thumb_url=f"{settings.MEDIA_URL}{keys['thumb']}",
        storage_key=keys["page"],
        colour_slug=colour,
        alt_en=alt,
        alt_ur=alt_ur_text or alt,
        position=position,
    )
    # Real photographs replace the illustrated stand-ins for that colour (decision 0006, #9).
    product.images.filter(colour_slug=colour, url="").delete()
    record(
        "catalog.image.add",
        actor,
        target_type="product",
        target_id=product.pk,
        after={"image": image.url, "colour": colour},
        request=request,
    )
    if product.status == ProductStatus.PUBLISHED:
        _refresh()
    return image


@transaction.atomic
def remove_image(image: ProductImage, actor: Actor, request: Any = None) -> None:
    product = image.product
    key, url = image.storage_key, image.url
    image.delete()
    if key and not ProductImage.objects.filter(storage_key=key).exists():
        store = storage()

        def remove_files() -> None:
            for k in (key, key.replace("-page.", "-thumb.")):
                store.delete(k)

        transaction.on_commit(remove_files)
    record(
        "catalog.image.remove",
        actor,
        target_type="product",
        target_id=product.pk,
        before={"image": url},
        request=request,
    )
    if product.status == ProductStatus.PUBLISHED:
        _refresh()
