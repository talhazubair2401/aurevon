"""M5 product images: checked by content, size and ratio; re-encoded without metadata; stored once; shown
instead of the illustration for their colour (decision 0006, #9)."""

import io
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.catalog.models import Product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def demo(settings: Any, tmp_path: Path) -> None:
    settings.ALLOW_DEMO_DATA = True
    settings.MEDIA_STORAGE = "local"
    settings.MEDIA_ROOT = str(tmp_path)
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def picture(size: tuple[int, int] = (1600, 2000), fmt: str = "JPEG", exif: bool = False) -> bytes:
    out = io.BytesIO()
    image = Image.new("RGB", size, (200, 180, 150))
    kwargs: dict[str, Any] = {}
    if exif:
        data = Image.Exif()
        data[0x010F] = "SecretCam"  # Make
        kwargs["exif"] = data
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


def upload(client: APIClient, product: Product, data: bytes, name: str = "photo.jpg", **fields: str) -> Any:
    return client.post(
        f"{STAFF}/catalog/products/{product.pk}/images",
        {"file": SimpleUploadedFile(name, data), "colour": "ivory", "alt_en": "Front view", **fields},
        format="multipart",
    )


def test_upload_replaces_the_illustration_for_that_colour(tmp_path: Path, client: Client) -> None:
    api = sign_in(make_staff(RoleCode.CONTENT_MARKETING))
    product = Product.objects.get(slug="silk-column-dress")
    r = upload(api, product, picture(exif=True))
    assert r.status_code == 201, r.content
    image = r.json()["images"][0]
    assert image["url"].startswith("/media/products/") and image["url"].endswith("-page.webp")
    stored = tmp_path / image["url"].removeprefix("/media/")
    with Image.open(stored) as saved:
        assert saved.format == "WEBP" and saved.size == (1600, 2000)
        assert not saved.getexif()  # metadata dropped
    assert (tmp_path / image["thumb_url"].removeprefix("/media/")).exists()

    detail = client.get("/api/v1/catalog/products/silk-column-dress").json()
    ivory = [i for i in detail["images"] if i["colour"] == "ivory"]
    assert len(ivory) == 1 and ivory[0]["url"] == image["url"] and ivory[0]["demo_art"] is None
    card = client.get("/api/v1/catalog/products", {"q": "silk column"}).json()["results"][0]
    assert card["image"]["url"] == image["thumb_url"]

    r = api.delete(f"{STAFF}/catalog/products/{product.pk}/images/{image['id']}")
    assert r.status_code == 200 and r.json()["images"] == []


@pytest.mark.parametrize(
    ("data", "name", "reason"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "photo.jpg", "isn't a JPEG"),  # disguised by its name
        (picture((800, 1000)), "small.jpg", "at least 1600 x 2000"),
        (picture((2000, 2000)), "square.jpg", "4:5 portrait"),
        (picture(fmt="GIF"), "anim.gif", "JPEG, PNG or WebP"),
    ],
)
def test_bad_images_are_refused(data: bytes, name: str, reason: str) -> None:
    api = sign_in(make_staff(RoleCode.STORE_ADMIN))
    r = upload(api, Product.objects.get(slug="silk-column-dress"), data, name)
    assert r.status_code == 400 and reason in r.json()["detail"], r.content


def test_alt_text_colour_and_permissions() -> None:
    product = Product.objects.get(slug="silk-column-dress")
    api = sign_in(make_staff(RoleCode.STORE_ADMIN))
    assert upload(api, product, picture(), alt_en="").status_code == 400
    assert upload(api, product, picture(), colour="olive").status_code == 400  # not this product's colour
    support = sign_in(make_staff(RoleCode.SUPPORT))
    assert upload(support, product, picture()).status_code == 403


def test_s3_storage_writes_immutable_objects(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The adapter used with the production object store (P-10); the client is stubbed here."""
    from integrations import storage as module

    calls: list[dict[str, Any]] = []

    class Client:
        def put_object(self, **kwargs: Any) -> None:
            calls.append(kwargs)

        def delete_object(self, **kwargs: Any) -> None:
            calls.append({"deleted": kwargs["Key"]})

    import boto3

    monkeypatch.setattr(boto3, "client", lambda *a, **k: Client())
    settings.MEDIA_STORAGE = "s3"
    store = module.storage()
    store.put("products/a.webp", b"x", "image/webp")
    store.delete("products/a.webp")
    assert calls[0]["Bucket"] == settings.MEDIA_BUCKET and "immutable" in calls[0]["CacheControl"]
    assert calls[1] == {"deleted": "products/a.webp"}


def test_local_storage_refuses_keys_outside_its_folder(tmp_path: Path) -> None:
    from integrations.storage import LocalStorage

    with pytest.raises(ValueError):
        LocalStorage(tmp_path).put("../escape.webp", b"x", "image/webp")
