from typing import Any

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from apps.cms.models import HomepageSection
from apps.notifications.models import ConsentRecord, ConsentStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def test_demo_data_refuses_to_run_outside_development(settings: Any) -> None:
    settings.DEBUG = False
    settings.ALLOW_DEMO_DATA = False
    with pytest.raises(CommandError):
        call_command("seed_demo_catalog")


def test_home_returns_enabled_sections_in_order_with_their_data(demo: None, client: Client) -> None:
    body = client.get("/api/v1/cms/home").json()
    assert [s["key"] for s in body["sections"]] == [
        "hero",
        "collections",
        "featured_products",
        "new_arrivals",
        "brand_story",
    ]
    by_key = {s["key"]: s for s in body["sections"]}
    assert by_key["hero"]["content"]["title"] == "Modern Style. Timeless Confidence."
    assert len(by_key["collections"]["collections"]) == 3
    assert len(by_key["featured_products"]["products"]) == 8
    assert all(p["is_featured"] for p in by_key["featured_products"]["products"])
    assert by_key["new_arrivals"]["products"][0]["slug"] == "wool-overcoat"


def test_disabled_sections_are_left_out(demo: None, client: Client) -> None:
    HomepageSection.objects.filter(key="brand_story").update(is_enabled=False)
    keys = [s["key"] for s in client.get("/api/v1/cms/home").json()["sections"]]
    assert "brand_story" not in keys


def test_urdu_copy_falls_back_to_english_per_field(demo: None, client: Client) -> None:
    hero = client.get("/api/v1/cms/home", {"locale": "ur"}).json()["sections"][0]["content"]
    assert hero["title"] == "جدید انداز۔ لازوال اعتماد۔"  # noqa: RUF001
    assert hero["primary_href"] == "/shop?department=women"  # not translated: English value used


def test_shop_editorial_banner(demo: None, client: Client) -> None:
    banner = client.get("/api/v1/cms/banners/shop_editorial").json()
    assert banner["content"]["title"] == "BEYOND THE ORDINARY"
    assert client.get("/api/v1/cms/banners/nope").status_code == 404


def subscribe(client: Client, email: str = "Reader@Example.com", consent: bool = True) -> Any:
    return client.post(
        "/api/v1/newsletter/subscribe",
        {"email": email, "consent": consent, "locale": "en", "source": "shop_all"},
        content_type="application/json",
    )


def test_newsletter_is_double_opt_in(client: Client, django_capture_on_commit_callbacks: Any) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        assert subscribe(client).status_code == 202
    record = ConsentRecord.objects.get()
    assert record.email == "reader@example.com" and record.status == ConsentStatus.PENDING
    (message,) = mail.outbox
    token = message.body.split("#token=")[1].split()[0]
    assert (
        client.post("/api/v1/newsletter/confirm", {"token": "wrong"}, content_type="application/json").status_code
        == 400
    )
    assert (
        client.post("/api/v1/newsletter/confirm", {"token": token}, content_type="application/json").status_code == 200
    )
    record.refresh_from_db()
    assert record.status == ConsentStatus.CONFIRMED and record.confirmed_at is not None
    # The link is single-use.
    assert (
        client.post("/api/v1/newsletter/confirm", {"token": token}, content_type="application/json").status_code == 400
    )


def test_newsletter_requires_consent_and_never_reveals_subscribers(
    client: Client, django_capture_on_commit_callbacks: Any
) -> None:
    assert subscribe(client, consent=False).status_code == 400
    ConsentRecord.objects.create(
        email="known@example.com", purpose="newsletter", status="confirmed", wording_version="x", source="x"
    )
    with django_capture_on_commit_callbacks(execute=True):
        known = subscribe(client, "known@example.com")
        unknown = subscribe(client, "new@example.com")
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert [m.to for m in mail.outbox] == [["new@example.com"]]  # confirmed address isn't mailed again
