"""Garment models (MTS §4 pipeline; decision 0007). Upload → Celery job (validate, measure, Draco) → draft →
staff check it in the viewer → approve (copied to public storage) or retire. Shoppers see approved models only
when THREED_FOR_SHOPPERS is on, which stays off until V-01, V-02 and V-03 pass."""

import hashlib
import hmac
import json
import subprocess  # nosec B404  (runs our own pipeline with fixed arguments, never shell)
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import Actor, record
from integrations.storage import private_storage, storage

from .editing import CatalogError, _refresh
from .models import Product, ProductStatus, ThreeDAsset, ThreeDStatus

MAX_BYTES = 100 * 1024 * 1024
GLB_MAGIC = b"glTF"


def upload(product: Product, name: str, data: bytes, actor: Actor, request: Any = None) -> ThreeDAsset:
    if not name.lower().endswith(".glb"):
        raise CatalogError("Upload a .glb file (binary glTF).")
    if len(data) > MAX_BYTES:
        raise CatalogError("The file is larger than 100 MB.")
    if data[:4] != GLB_MAGIC:
        raise CatalogError("This file isn't a valid .glb model.")
    key = f"3d/sources/{uuid.uuid4().hex}.glb"
    private_storage().put(key, data, "model/gltf-binary")
    with transaction.atomic():
        asset = ThreeDAsset.objects.create(
            product=product, file_name=Path(name).name[:200], source_key=key, uploaded_by=actor.label
        )
        record(
            "catalog.3d.upload",
            actor,
            target_type="product",
            target_id=product.pk,
            after={"asset": str(asset.pk), "file": asset.file_name, "bytes": len(data)},
            request=request,
        )
        from .tasks import process_threed

        transaction.on_commit(lambda: process_threed.delay(str(asset.pk)))
    return asset


def run_pipeline(source: Path, output: Path) -> dict[str, Any]:
    command = ["node", settings.ASSET_PIPELINE, str(source), str(output)]
    try:
        done = subprocess.run(  # noqa: S603  # nosec B603  (fixed command, no shell)
            command, capture_output=True, timeout=settings.ASSET_PIPELINE_TIMEOUT_SECONDS, check=False
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": "timeout", "message": "Processing took longer than 5 minutes and was stopped."}
    lines = [line for line in done.stdout.decode(errors="replace").splitlines() if line.startswith("{")]
    if done.returncode != 0 or not lines:
        return {
            "ok": False,
            "code": "pipeline",
            "message": "The model couldn't be processed. Try again later.",
            "details": [done.stderr.decode(errors="replace")[-500:]],
        }
    result: dict[str, Any] = json.loads(lines[-1])
    return result


def variant_map(asset: ThreeDAsset) -> dict[str, str]:
    """Which colour shows which variant (D-03). A colour with no variant and no per-colour cover shows photos."""
    product_colours = list(
        dict.fromkeys(asset.product.variants.filter(is_active=True).values_list("colour__slug", flat=True))
    )
    mapping: dict[str, str] = {}
    for colour in product_colours:
        if colour in asset.variants:
            mapping[colour] = colour
        elif colour in asset.colours:
            mapping[colour] = ""
    if not asset.variants and not asset.colours and len(product_colours) == 1:
        mapping[product_colours[0]] = ""
    return mapping


def process(asset_id: str) -> None:
    asset = ThreeDAsset.objects.select_related("product").get(pk=asset_id)
    if asset.status != ThreeDStatus.PROCESSING:
        return
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "source.glb"
        out = Path(tmp) / "output.glb"
        src.write_bytes(private_storage().get(asset.source_key))
        result = run_pipeline(src, out)
        if not result.get("ok"):
            ThreeDAsset.objects.filter(pk=asset.pk, status=ThreeDStatus.PROCESSING).update(
                status=ThreeDStatus.FAILED,
                report={
                    "error": result.get("message"),
                    "code": result.get("code"),
                    "details": result.get("details", []),
                },
                updated_at=timezone.now(),
            )
            return
        report = result["report"]
        draft_key = f"3d/drafts/{report['checksum']}.glb"
        private_storage().put(draft_key, out.read_bytes(), "model/gltf-binary")
    asset.draft_key = draft_key
    asset.compression = report["compression"]
    asset.bytes = report["bytes"]
    asset.triangles = report["triangles"]
    asset.max_texture_px = report["maxTexturePx"]
    asset.est_gpu_mb = report["estGpuMb"]
    asset.variants = report["variants"]
    asset.checksum = report["checksum"]
    asset.report = {
        k: report[k] for k in ("warnings", "notes", "validator", "heightM", "sourceBytes", "meshes", "textures")
    }
    asset.variant_map = variant_map(asset)
    asset.status = ThreeDStatus.DRAFT
    # Only if still processing: a second run of the same job (a retried task) never overwrites a later
    # approval or retirement.
    with transaction.atomic():
        if ThreeDAsset.objects.select_for_update().filter(pk=asset.pk, status=ThreeDStatus.PROCESSING).exists():
            asset.save()


@transaction.atomic
def set_colours(asset: ThreeDAsset, colours: Any, actor: Actor, request: Any = None) -> ThreeDAsset:
    asset = ThreeDAsset.objects.select_for_update().select_related("product").get(pk=asset.pk)
    if asset.status not in (ThreeDStatus.DRAFT, ThreeDStatus.FAILED):
        raise CatalogError("Only a draft's colours can change. Upload the file again to change an approved model.")
    known = set(asset.product.variants.values_list("colour__slug", flat=True))
    if not isinstance(colours, list) or set(colours) - known:
        raise CatalogError("Choose colours this product comes in.")
    asset.colours = colours
    asset.variant_map = variant_map(asset)
    asset.save(update_fields=["colours", "variant_map", "updated_at"])
    record(
        "catalog.3d.colours",
        actor,
        target_type="product",
        target_id=asset.product_id,
        after={"asset": str(asset.pk), "colours": colours},
        request=request,
    )
    return asset


@transaction.atomic
def approve(asset: ThreeDAsset, checked: bool, actor: Actor, request: Any = None) -> ThreeDAsset:
    """After a staff member with publishing rights has checked it in the viewer (MTS §4, step 4)."""
    asset = ThreeDAsset.objects.select_for_update().select_related("product").get(pk=asset.pk)
    if asset.status != ThreeDStatus.DRAFT:
        raise CatalogError("Only a processed draft can be approved.")
    if not checked:
        raise CatalogError("Check the model in the viewer first, then confirm.")
    asset.variant_map = variant_map(asset)
    if not asset.variant_map:
        raise CatalogError(
            "No colour of this product matches the model. Name its variants by colour, or choose "
            "the colours this model shows."
        )
    key = f"products/3d/{asset.checksum}.glb"
    storage().put(key, private_storage().get(asset.draft_key), "model/gltf-binary")
    covered = set(asset.variant_map)
    for other in ThreeDAsset.objects.select_for_update().filter(product=asset.product, status=ThreeDStatus.APPROVED):
        if covered & set(other.variant_map):
            other.status = ThreeDStatus.RETIRED
            other.save(update_fields=["status", "updated_at"])
    asset.url = f"{settings.MEDIA_URL}{key}"
    asset.status = ThreeDStatus.APPROVED
    asset.approved_by = actor.label
    asset.approved_at = timezone.now()
    asset.save()
    record(
        "catalog.3d.approve",
        actor,
        target_type="product",
        target_id=asset.product_id,
        after={
            "asset": str(asset.pk),
            "url": asset.url,
            "variant_map": asset.variant_map,
            "warnings": asset.report.get("warnings", []),
        },
        request=request,
    )
    if asset.product.status == ProductStatus.PUBLISHED:
        _refresh()
    return asset


@transaction.atomic
def retire(asset: ThreeDAsset, actor: Actor, request: Any = None) -> ThreeDAsset:
    asset = ThreeDAsset.objects.select_for_update().select_related("product").get(pk=asset.pk)
    if asset.status in (ThreeDStatus.RETIRED, ThreeDStatus.PROCESSING):
        raise CatalogError("This model can't be retired now.")
    before = asset.status
    asset.status = ThreeDStatus.RETIRED
    asset.save(update_fields=["status", "updated_at"])
    record(
        "catalog.3d.retire",
        actor,
        target_type="product",
        target_id=asset.product_id,
        before={"status": before},
        after={"asset": str(asset.pk), "status": "retired"},
        request=request,
    )
    if before == ThreeDStatus.APPROVED and asset.product.status == ProductStatus.PUBLISHED:
        _refresh()
    return asset


# --- Short-lived signed preview links for drafts (MTS §4: never through public /media/) ---------------


def _signature(asset_id: str, expires: int) -> str:
    message = f"threed-preview:{asset_id}:{expires}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def preview_url(asset: ThreeDAsset) -> str:
    expires = int(time.time()) + settings.THREED_PREVIEW_SECONDS
    return f"/api/v1/staff/catalog/3d/{asset.pk}/file?expires={expires}&sig={_signature(str(asset.pk), expires)}"


def preview_allowed(asset_id: str, expires: str, sig: str) -> bool:
    try:
        until = int(expires)
    except ValueError:
        return False
    if until < time.time() or until > time.time() + settings.THREED_PREVIEW_SECONDS + 5:
        return False
    return hmac.compare_digest(_signature(asset_id, until), sig)


def preview_bytes(asset: ThreeDAsset) -> bytes:
    key = asset.draft_key or (asset.url.removeprefix(settings.MEDIA_URL) if asset.url else "")
    if not key:
        raise CatalogError("This model has no processed file.")
    if asset.draft_key:
        return private_storage().get(asset.draft_key)
    return storage().get(key)


def for_shoppers(product: Product) -> dict[str, Any] | None:
    """Which model and variant each colour shows (D-03), or None. None whenever 3D is off for shoppers.

    Several approved models can cover different colours (a per-colour model); a colour in none shows photos.
    """
    if not settings.THREED_FOR_SHOPPERS:
        return None
    by_colour: dict[str, dict[str, str]] = {}
    approved = ThreeDAsset.objects.filter(product=product, status=ThreeDStatus.APPROVED).order_by("approved_at")
    for asset in approved:  # newest last, so it wins (approval retires overlaps anyway)
        for colour, variant in asset.variant_map.items():
            by_colour[colour] = {"url": asset.url, "variant": variant, "compression": asset.compression}
    return {"by_colour": by_colour} if by_colour else None
