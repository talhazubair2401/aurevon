"""M6: garment models (decision 0007). Real pipeline on the fixture garments; drafts private; approval needs
publishing rights and a confirmed check; shoppers get nothing while 3D is off."""

from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.audit.models import AuditLog
from apps.catalog import threed
from apps.catalog.models import Product, ThreeDAsset

pytestmark = pytest.mark.django_db
FIXTURES = Path(__file__).resolve().parents[4] / "packages" / "asset-pipeline" / "fixtures"


@pytest.fixture(autouse=True)
def demo(settings: Any, tmp_path: Path) -> None:
    settings.ALLOW_DEMO_DATA = True
    settings.MEDIA_ROOT = str(tmp_path / "public")
    settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "private")
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def kurta() -> Product:
    """Block-Print Kurta comes in ivory and sage, the fixture's two variants."""
    product = Product.objects.get(slug="block-print-kurta")
    assert set(product.variants.values_list("colour__slug", flat=True)) >= {"ivory", "sage"}
    return product


def upload(api: APIClient, product: Product, name: str = "garment.glb") -> Any:
    data = (FIXTURES / name).read_bytes() if (FIXTURES / name).exists() else b"glTF" + b"\0" * 40
    return api.post(
        f"{STAFF}/catalog/products/{product.pk}/models3d", {"file": SimpleUploadedFile(name, data)}, format="multipart"
    )


def test_upload_processes_into_a_private_draft(tmp_path: Path, client: Client) -> None:
    api = sign_in(make_staff(RoleCode.CONTENT_MARKETING))
    r = upload(api, kurta())
    assert r.status_code == 201, r.content
    model = r.json()["models3d"][0]
    assert model["status"] == "draft"  # processed eagerly in tests
    assert model["compression"] == "draco" and model["variants"] == ["ivory", "sage"]
    assert model["variant_map"] == {"ivory": "ivory", "sage": "sage"}
    assert model["triangles"] == 672 and model["report"]["warnings"] == []
    assert not (tmp_path / "public").exists() or not list((tmp_path / "public").rglob("*.glb"))  # nothing public

    # The signed preview works for staff, and not without the signature or once expired.
    preview = api.get(model["preview_url"])
    assert preview.status_code == 200 and preview["Content-Type"] == "model/gltf-binary"
    assert preview.content[:4] == b"glTF" and preview["Cache-Control"] == "private, no-store"
    assert api.get(model["preview_url"].replace("sig=", "sig=0")).status_code == 403
    assert client.get(model["preview_url"]).status_code in (401, 403)  # no staff session


def test_approval_needs_publish_rights_and_a_check(settings: Any, client: Client) -> None:
    product = kurta()
    editor = sign_in(make_staff(RoleCode.CONTENT_MARKETING))
    model = upload(editor, product).json()["models3d"][0]
    base = f"{STAFF}/catalog/products/{product.pk}/models3d/{model['id']}"
    # Content/Marketing edits the catalogue but doesn't publish it (decision 0003).
    assert editor.post(f"{base}/approve", {"checked": True}, format="json").status_code == 403
    editor = sign_in(make_staff(RoleCode.STORE_ADMIN, "admin@aurevon.test"))
    r = editor.post(f"{base}/approve", {"checked": False}, format="json")
    assert r.status_code == 400 and "Check the model" in r.json()["detail"]
    r = editor.post(f"{base}/approve", {"checked": True}, format="json")
    assert r.status_code == 200
    approved = r.json()["models3d"][0]
    assert approved["status"] == "approved" and approved["url"].startswith("/media/products/3d/")
    assert AuditLog.objects.filter(action="catalog.3d.approve").exists()

    # 3D is off for shoppers: the approved model isn't sent.
    assert client.get(f"/api/v1/catalog/products/{product.slug}").json()["model3d"] is None
    settings.THREED_FOR_SHOPPERS = True
    sent = client.get(f"/api/v1/catalog/products/{product.slug}").json()["model3d"]
    assert sent["url"] == approved["url"] and sent["variant_map"] == {"ivory": "ivory", "sage": "sage"}

    # A newer approved model for the same colours retires the older one.
    second = upload(editor, product, "garment-draco.glb").json()["models3d"][0]
    editor.post(
        f"{STAFF}/catalog/products/{product.pk}/models3d/{second['id']}/approve", {"checked": True}, format="json"
    )
    assert ThreeDAsset.objects.get(pk=model["id"]).status == "retired"
    editor.post(f"{STAFF}/catalog/products/{product.pk}/models3d/{second['id']}/retire")
    assert client.get(f"/api/v1/catalog/products/{product.slug}").json()["model3d"] is None


def test_a_model_without_variants_covers_the_colours_staff_choose(client: Client) -> None:
    product = kurta()
    api = sign_in(make_staff(RoleCode.STORE_ADMIN))
    model = upload(api, product, "garment-novariants.glb").json()["models3d"][0]
    assert model["variant_map"] == {}
    base = f"{STAFF}/catalog/products/{product.pk}/models3d/{model['id']}"
    r = api.post(f"{base}/approve", {"checked": True}, format="json")
    assert r.status_code == 400 and "No colour" in r.json()["detail"]
    r = api.put(f"{base}/colours", {"colours": ["sage"]}, format="json")
    assert r.json()["models3d"][0]["variant_map"] == {"sage": ""}
    assert api.put(f"{base}/colours", {"colours": ["teal"]}, format="json").status_code == 400


@pytest.mark.parametrize(
    ("name", "reason"),
    [("corrupt.glb", "damaged"), ("truncated.glb", "incomplete"), ("needs-unknown-extension.glb", "EXT_made_up")],
)
def test_bad_models_fail_with_a_reason(name: str, reason: str) -> None:
    api = sign_in(make_staff(RoleCode.STORE_ADMIN))
    model = upload(api, kurta(), name).json()["models3d"][0]
    assert model["status"] == "failed" and reason in model["report"]["error"]
    assert model["preview_url"] is None


def test_wrong_files_are_refused_at_upload() -> None:
    api = sign_in(make_staff(RoleCode.STORE_ADMIN))
    product = kurta()
    r = api.post(
        f"{STAFF}/catalog/products/{product.pk}/models3d",
        {"file": SimpleUploadedFile("model.obj", b"v 0 0 0")},
        format="multipart",
    )
    assert r.status_code == 400
    r = upload(api, product, "not-a-model.glb")
    assert r.status_code == 400


def test_provisional_figures_warn_but_still_allow_approval() -> None:
    api = sign_in(make_staff(RoleCode.STORE_ADMIN))
    product = kurta()
    model = upload(api, product, "garment-large-texture.glb").json()["models3d"][0]
    assert model["status"] == "draft" and any("2560 px" in w for w in model["report"]["warnings"])
    r = api.post(
        f"{STAFF}/catalog/products/{product.pk}/models3d/{model['id']}/approve", {"checked": True}, format="json"
    )
    assert r.status_code == 200


def test_preview_signatures() -> None:
    asset_id = "00000000-0000-0000-0000-000000000001"
    url = threed.preview_url(ThreeDAsset(pk=asset_id))
    expires = url.split("expires=")[1].split("&")[0]
    sig = url.split("sig=")[1]
    assert threed.preview_allowed(asset_id, expires, sig)
    assert not threed.preview_allowed("00000000-0000-0000-0000-000000000002", expires, sig)
    assert not threed.preview_allowed(asset_id, "1", sig)
