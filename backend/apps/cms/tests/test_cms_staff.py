"""M4 CMS and SEO: drafts never reach shoppers, publishing needs `cms.publish`, links stay on the storefront,
renamed pages keep working through redirects, and every live change is audited and refreshes the storefront."""

from typing import Any
from unittest import mock

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.audit.models import AuditLog
from apps.cms import content as c
from apps.cms.models import Page, Redirect

pytestmark = pytest.mark.django_db
CMS = f"{STAFF}/cms"


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


@pytest.fixture
def editor() -> APIClient:
    return sign_in(make_staff(RoleCode.CONTENT_MARKETING, "content@aurevon.test"))


def hero_content(title: str) -> dict[str, Any]:
    return {
        "en": {"title": title, "primary_label": "Shop Women", "primary_href": "/shop?department=women"},
        "ur": {"title": "عنوان"},
    }


def public_hero(client: APIClient) -> Any:
    sections = client.get("/api/v1/cms/home").json()["sections"]
    return next(s for s in sections if s["key"] == "hero")["content"]


# --- Permissions -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [RoleCode.SUPPORT, RoleCode.ACCOUNTANT, RoleCode.INVENTORY_MANAGER])
def test_roles_without_cms_permissions_are_refused(role: str) -> None:
    client = sign_in(make_staff(role))
    assert client.get(f"{CMS}/home-sections").status_code == 403
    assert (
        client.put(f"{CMS}/home-sections/hero/draft", {"content": hero_content("x")}, format="json").status_code == 403
    )
    assert client.get(f"{STAFF}/seo").status_code == 403
    assert client.get(f"{STAFF}/redirects").status_code == 403


@pytest.mark.parametrize("role", [RoleCode.OWNER, RoleCode.STORE_ADMIN, RoleCode.CONTENT_MARKETING])
def test_content_roles_can_edit_and_publish(role: str) -> None:
    client = sign_in(make_staff(role))
    assert (
        client.put(f"{CMS}/home-sections/hero/draft", {"content": hero_content("New")}, format="json").status_code
        == 200
    )
    assert client.post(f"{CMS}/home-sections/hero/publish").status_code == 200


def test_editing_without_publish_permission_cannot_go_live(editor: APIClient) -> None:
    with mock.patch("apps.accounts.services.access.has_perm", side_effect=lambda account, perm: perm != "cms.publish"):
        assert (
            editor.put(f"{CMS}/home-sections/hero/draft", {"content": hero_content("Draft")}, format="json").status_code
            == 200
        )
        assert editor.post(f"{CMS}/home-sections/hero/publish").status_code == 403
        assert editor.put(f"{CMS}/navigation/header", {"items": []}, format="json").status_code == 403


# --- Drafts and publishing -------------------------------------------------------------------------------


def test_a_draft_stays_private_until_published(editor: APIClient, django_capture_on_commit_callbacks: Any) -> None:
    shopper = APIClient()
    original = public_hero(shopper)["title"]
    r = editor.put(f"{CMS}/home-sections/hero/draft", {"content": hero_content("Winter Edit")}, format="json")
    assert r.status_code == 200 and r.json()["draft"]["en"]["title"] == "Winter Edit"
    assert public_hero(shopper)["title"] == original

    with (
        mock.patch("apps.cms.tasks.refresh_storefront.delay") as refresh,
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert editor.post(f"{CMS}/home-sections/hero/publish").status_code == 200
    refresh.assert_called_once_with(["cms"])
    assert public_hero(shopper)["title"] == "Winter Edit"
    entry = AuditLog.objects.get(action="cms.section.publish")
    assert entry.after is not None and entry.before is not None
    assert entry.target_id == "hero" and entry.after["content"]["en"]["title"] == "Winter Edit"
    assert entry.before["content"]["en"]["title"] == original


def test_discarding_a_draft_keeps_the_live_copy(editor: APIClient) -> None:
    editor.put(f"{CMS}/home-sections/hero/draft", {"content": hero_content("Gone")}, format="json")
    r = editor.delete(f"{CMS}/home-sections/hero/draft")
    assert r.status_code == 200 and r.json()["draft"] is None
    assert editor.post(f"{CMS}/home-sections/hero/publish").status_code == 400


@pytest.mark.parametrize(
    "href",
    ["https://evil.example/", "//evil.example", "javascript:alert(1)", "/en/shop", "/staff/", "/api/v1/cms/home"],
)
def test_links_must_be_storefront_paths(editor: APIClient, href: str) -> None:
    content = hero_content("Title")
    content["en"]["primary_href"] = href
    r = editor.put(f"{CMS}/home-sections/hero/draft", {"content": content}, format="json")
    assert r.status_code == 400, href
    assert r.json()["type"].endswith("/invalid-content")


def test_unknown_fields_and_missing_titles_are_refused(editor: APIClient) -> None:
    r = editor.put(f"{CMS}/home-sections/hero/draft", {"content": {"en": {"title": "x", "html": "<b>"}}}, format="json")
    assert r.status_code == 400
    r = editor.put(f"{CMS}/home-sections/hero/draft", {"content": {"en": {"eyebrow": "x"}}}, format="json")
    assert r.status_code == 400 and "required in English" in r.json()["detail"]


def test_homepage_order_and_visibility(editor: APIClient) -> None:
    layout = [
        {"key": "hero", "is_enabled": True},
        {"key": "new_arrivals", "is_enabled": True},
        {"key": "featured_products", "is_enabled": True},
        {"key": "collections", "is_enabled": True},
        {"key": "brand_story", "is_enabled": False},
    ]
    assert editor.put(f"{CMS}/home-sections/layout", {"sections": layout}, format="json").status_code == 200
    keys = [s["key"] for s in APIClient().get("/api/v1/cms/home").json()["sections"]]
    assert keys == ["hero", "new_arrivals", "featured_products", "collections"]
    r = editor.put(f"{CMS}/home-sections/layout", {"sections": layout[:3]}, format="json")
    assert r.status_code == 400  # every section, once
    assert AuditLog.objects.filter(action="cms.homepage.layout").count() == 1


def test_banner_draft_publish_and_visibility(editor: APIClient) -> None:
    content = {"en": {"title": "NEW SEASON", "link_label": "Shop", "link_href": "/shop"}}
    assert editor.put(f"{CMS}/banners/shop_editorial/draft", {"content": content}, format="json").status_code == 200
    assert APIClient().get("/api/v1/cms/banners/shop_editorial").json()["content"]["title"] == "BEYOND THE ORDINARY"
    assert editor.post(f"{CMS}/banners/shop_editorial/publish").status_code == 200
    assert APIClient().get("/api/v1/cms/banners/shop_editorial").json()["content"]["title"] == "NEW SEASON"
    assert editor.put(f"{CMS}/banners/shop_editorial", {"is_enabled": False}, format="json").status_code == 200
    assert APIClient().get("/api/v1/cms/banners/shop_editorial").status_code == 404
    assert editor.put(f"{CMS}/banners/unknown/draft", {"content": content}, format="json").status_code == 404


# --- Pages -----------------------------------------------------------------------------------------------


def page_content(title: str, text: str = "Body text.") -> dict[str, Any]:
    return {"en": {"title": title, "body": [{"type": "paragraph", "text": text}]}}


def test_page_lifecycle(editor: APIClient) -> None:
    r = editor.post(
        f"{CMS}/pages", {"slug": "size-guide", "kind": "content", "content": page_content("Size guide")}, format="json"
    )
    assert r.status_code == 201, r.content
    page_id = r.json()["id"]
    assert APIClient().get("/api/v1/cms/pages/size-guide").status_code == 404  # draft only

    assert editor.post(f"{CMS}/pages/{page_id}/publish").status_code == 200
    body = APIClient().get("/api/v1/cms/pages/size-guide").json()
    assert body["title"] == "Size guide" and body["body"] == [{"type": "paragraph", "text": "Body text."}]
    assert body["translated"] is True
    assert APIClient().get("/api/v1/cms/pages/size-guide", {"locale": "ur"}).json()["translated"] is False

    editor.put(f"{CMS}/pages/{page_id}/draft", {"content": page_content("Size guide v2")}, format="json")
    assert APIClient().get("/api/v1/cms/pages/size-guide").json()["title"] == "Size guide"

    assert editor.post(f"{CMS}/pages/{page_id}/unpublish").status_code == 200
    assert APIClient().get("/api/v1/cms/pages/size-guide").status_code == 404
    actions = list(AuditLog.objects.filter(target_id=page_id).values_list("action", flat=True))
    assert {"cms.page.create", "cms.page.publish", "cms.page.unpublish"} <= set(actions)


def test_page_bodies_are_plain_text_blocks(editor: APIClient) -> None:
    for bad in (
        {"en": {"title": "T", "body": [{"type": "html", "text": "<script>"}]}},
        {"en": {"title": "T", "body": [{"type": "paragraph", "text": "x", "onclick": "y"}]}},
        {"en": {"title": "T", "body": []}},
        {"en": {"title": "T", "body": [{"type": "list", "items": []}]}},
    ):
        r = editor.post(f"{CMS}/pages", {"slug": "bad", "kind": "content", "content": bad}, format="json")
        assert r.status_code == 400, bad
    r = editor.post(
        f"{CMS}/pages", {"slug": "Bad Slug", "kind": "content", "content": page_content("T")}, format="json"
    )
    assert r.status_code == 400
    r = editor.post(f"{CMS}/pages", {"slug": "about", "kind": "content", "content": page_content("T")}, format="json")
    assert r.status_code == 400  # taken


def test_renaming_a_live_page_redirects_the_old_address(editor: APIClient) -> None:
    page = Page.objects.get(slug="about")
    r = editor.put(f"{CMS}/pages/{page.pk}", {"slug": "our-story", "kind": "content"}, format="json")
    assert r.status_code == 200
    resolved = APIClient().get("/api/v1/cms/redirects/resolve", {"path": "/pages/about"}).json()
    assert resolved == {"to": "/pages/our-story", "permanent": True}

    # Renaming again doesn't build a chain: the first old address points straight at the newest.
    editor.put(f"{CMS}/pages/{page.pk}", {"slug": "heritage", "kind": "content"}, format="json")
    assert Redirect.objects.get(from_path="/pages/about").to_path == "/pages/heritage"
    assert Redirect.objects.get(from_path="/pages/our-story").to_path == "/pages/heritage"

    # Going back to an old name removes the redirect from it, and never leaves a loop.
    editor.put(f"{CMS}/pages/{page.pk}", {"slug": "about", "kind": "content"}, format="json")
    assert not Redirect.objects.filter(from_path="/pages/about").exists()
    assert set(Redirect.objects.values_list("to_path", flat=True)) == {"/pages/about"}


# --- Navigation, SEO and redirects -----------------------------------------------------------------------


def test_navigation_menu_is_replaced_whole(editor: APIClient) -> None:
    items = [
        {"label": {"en": "Sale", "ur": "سیل"}, "href": "/shop?sort=price_asc"},
        {"label": {"en": "Men"}, "href": "/shop?department=men"},
    ]
    assert editor.put(f"{CMS}/navigation/header", {"items": items}, format="json").status_code == 200
    header = APIClient().get("/api/v1/cms/navigation", {"locale": "ur"}).json()["header"]
    assert header == [
        {"label": "سیل", "href": "/shop?sort=price_asc"},
        {"label": "Men", "href": "/shop?department=men"},
    ]
    bad = [{"label": {"en": "Out"}, "href": "https://elsewhere.example"}]
    assert editor.put(f"{CMS}/navigation/header", {"items": bad}, format="json").status_code == 400
    assert editor.put(f"{CMS}/navigation/sidebar", {"items": items}, format="json").status_code == 404


def test_seo_settings(editor: APIClient) -> None:
    keys = [row["key"] for row in editor.get(f"{STAFF}/seo").json()]
    assert keys[:3] == ["home", "shop", "collections"] and "collection:heritage-edit" in keys
    content = {"en": {"title": "Heritage", "description": "Craft, cut for today."}}
    r = editor.put(f"{STAFF}/seo/collection:heritage-edit", {"content": content, "noindex": False}, format="json")
    assert r.status_code == 200
    assert APIClient().get("/api/v1/cms/seo/collection:heritage-edit").json()["title"] == "Heritage"
    too_long = {"en": {"title": "x" * 71}}
    assert editor.put(f"{STAFF}/seo/home", {"content": too_long, "noindex": False}, format="json").status_code == 400
    assert (
        editor.put(f"{STAFF}/seo/collection:nope", {"content": content, "noindex": False}, format="json").status_code
        == 404
    )


def test_redirects(editor: APIClient) -> None:
    r = editor.post(f"{STAFF}/redirects", {"from_path": "/sale", "to_path": "/shop?sort=price_asc"}, format="json")
    assert r.status_code == 201
    assert APIClient().get("/api/v1/cms/redirects/resolve", {"path": "/sale"}).json()["to"] == "/shop?sort=price_asc"
    for bad in (
        {"from_path": "/sale", "to_path": "/shop"},  # already exists
        {"from_path": "/en/old", "to_path": "/shop"},  # locale
        {"from_path": "/old", "to_path": "https://x.example"},  # off-site
        {"from_path": "/old", "to_path": "/old"},  # itself
        {"from_path": "/old", "to_path": "/sale"},  # chain
        {"from_path": "/staff/x", "to_path": "/shop"},  # reserved
    ):
        assert editor.post(f"{STAFF}/redirects", bad, format="json").status_code == 400, bad
    assert editor.delete(f"{STAFF}/redirects/{r.json()['id']}").status_code == 204
    assert APIClient().get("/api/v1/cms/redirects/resolve", {"path": "/sale"}).status_code == 404
    assert AuditLog.objects.filter(action__startswith="redirect.").count() == 2


def test_storefront_refresh_task_posts_with_the_shared_secret(settings: Any) -> None:
    from apps.cms.tasks import refresh_storefront

    settings.STOREFRONT_INTERNAL_URL = "http://storefront:3000"
    settings.STOREFRONT_REVALIDATE_SECRET = "s3cret"
    with mock.patch("urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.status = 200
        refresh_storefront(["cms"])
    request = urlopen.call_args.args[0]
    assert request.full_url == "http://storefront:3000/internal/revalidate"
    assert request.get_header("Authorization") == "Bearer s3cret"
    settings.STOREFRONT_REVALIDATE_SECRET = ""
    with mock.patch("urllib.request.urlopen") as urlopen:
        refresh_storefront(["cms"])
    urlopen.assert_not_called()


def test_localised_falls_back_per_field() -> None:
    assert c.localised({"en": {"a": "A", "b": "B"}, "ur": {"a": "اے", "b": ""}}, "ur") == {"a": "اے", "b": "B"}
