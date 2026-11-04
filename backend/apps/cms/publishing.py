"""Every CMS and SEO write (MTS §5: all writes go through services). Who may call what is decided by the
staff API; these functions validate, store, audit and refresh the storefront once the change commits."""

import re
from typing import Any

from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.catalog.models import Collection

from . import content as c
from .models import (
    Banner,
    HomepageSection,
    NavigationItem,
    NavigationMenu,
    Page,
    PageKind,
    Redirect,
    RedirectSource,
    SEORecord,
)
from .tasks import refresh_storefront

CMS_TAG = "cms"
FIXED_SEO_KEYS = ("home", "shop", "collections")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class NotFound(LookupError):
    pass


def _refresh_after_commit() -> None:
    transaction.on_commit(lambda: refresh_storefront.delay([CMS_TAG]))


# --- Pages -----------------------------------------------------------------------------------------------


def page_path(slug: str) -> str:
    return f"/pages/{slug}"


def _check_slug(slug: Any, exclude: Page | None = None) -> str:
    if not isinstance(slug, str) or not _SLUG.match(slug) or len(slug) > 80:
        raise c.ContentError("Address: use lower-case letters, numbers and hyphens, such as about-us.")
    clash = Page.objects.filter(slug=slug)
    if exclude is not None:
        clash = clash.exclude(pk=exclude.pk)
    if clash.exists():
        raise c.ContentError("Address: another page already uses it.")
    return slug


@transaction.atomic
def create_page(slug: Any, kind: Any, raw: Any, actor: Actor, request: HttpRequest | None = None) -> Page:
    if kind not in PageKind.values:
        raise c.ContentError("Type: choose content or policy.")
    page = Page.objects.create(slug=_check_slug(slug), kind=kind, draft=c.validate_page(raw))
    record("cms.page.create", actor, target_type="page", target_id=page.pk, after={"slug": page.slug}, request=request)
    return page


@transaction.atomic
def change_page_settings(page: Page, slug: Any, kind: Any, actor: Actor, request: HttpRequest | None = None) -> Page:
    """Renaming a published page keeps old links working: a permanent redirect from the old address."""
    page = Page.objects.select_for_update().get(pk=page.pk)
    if kind not in PageKind.values:
        raise c.ContentError("Type: choose content or policy.")
    before = {"slug": page.slug, "kind": page.kind}
    new_slug = _check_slug(slug, exclude=page)
    if new_slug != page.slug and page.is_published:
        _redirect_internal(page_path(page.slug), page_path(new_slug), RedirectSource.SLUG_CHANGE)
    Redirect.objects.filter(from_path=page_path(new_slug)).delete()  # the address is a real page again
    page.slug, page.kind = new_slug, kind
    page.save(update_fields=["slug", "kind", "updated_at"])
    record(
        "cms.page.settings",
        actor,
        target_type="page",
        target_id=page.pk,
        before=before,
        after={"slug": new_slug, "kind": kind},
        request=request,
    )
    if page.is_published:
        _refresh_after_commit()
    return page


def save_page_draft(page: Page, raw: Any) -> Page:
    page.draft = c.validate_page(raw)
    page.save(update_fields=["draft", "updated_at"])
    return page


@transaction.atomic
def publish_page(page: Page, actor: Actor, request: HttpRequest | None = None) -> Page:
    page = Page.objects.select_for_update().get(pk=page.pk)
    if page.draft is None and not page.content:
        raise c.ContentError("There is nothing to publish yet.")
    before = {"is_published": page.is_published, "content": page.content}
    if page.draft is not None:
        page.content, page.draft = page.draft, None
    page.is_published = True
    page.published_at = page.published_at or timezone.now()
    page.save()
    Redirect.objects.filter(from_path=page_path(page.slug)).delete()
    record(
        "cms.page.publish",
        actor,
        target_type="page",
        target_id=page.pk,
        before=before,
        after={"is_published": True, "content": page.content},
        request=request,
    )
    _refresh_after_commit()
    return page


@transaction.atomic
def unpublish_page(page: Page, actor: Actor, request: HttpRequest | None = None) -> Page:
    page = Page.objects.select_for_update().get(pk=page.pk)
    page.is_published = False
    page.published_at = None
    page.save(update_fields=["is_published", "published_at", "updated_at"])
    record("cms.page.unpublish", actor, target_type="page", target_id=page.pk, request=request)
    _refresh_after_commit()
    return page


def discard_page_draft(page: Page) -> Page:
    page.draft = None
    page.save(update_fields=["draft", "updated_at"])
    return page


# --- Homepage sections and banners -----------------------------------------------------------------------


def _section(key: str) -> HomepageSection:
    section = HomepageSection.objects.select_for_update().filter(key=key).first()
    if section is None:
        raise NotFound(key)
    return section


def save_section_draft(key: str, raw: Any) -> HomepageSection:
    with transaction.atomic():
        section = _section(key)
        section.draft = c.validate_section(key, raw)
        section.save(update_fields=["draft", "updated_at"])
    return section


@transaction.atomic
def publish_section(key: str, actor: Actor, request: HttpRequest | None = None) -> HomepageSection:
    section = _section(key)
    if section.draft is None:
        raise c.ContentError("There are no unpublished changes.")
    before = section.content
    section.content, section.draft = section.draft, None
    section.save(update_fields=["content", "draft", "updated_at"])
    record(
        "cms.section.publish",
        actor,
        target_type="homepage_section",
        target_id=key,
        before={"content": before},
        after={"content": section.content},
        request=request,
    )
    _refresh_after_commit()
    return section


def discard_section_draft(key: str) -> HomepageSection:
    with transaction.atomic():
        section = _section(key)
        section.draft = None
        section.save(update_fields=["draft", "updated_at"])
    return section


@transaction.atomic
def set_homepage_layout(layout: Any, actor: Actor, request: HttpRequest | None = None) -> list[HomepageSection]:
    """Order and visibility of the homepage sections: every section, listed once, in display order."""
    sections = {s.key: s for s in HomepageSection.objects.select_for_update()}
    if not isinstance(layout, list) or sorted(
        str(item.get("key")) for item in layout if isinstance(item, dict)
    ) != sorted(sections):
        raise c.ContentError("List every homepage section once, in the order to show them.")
    before = [{"key": s.key, "is_enabled": s.is_enabled} for s in sorted(sections.values(), key=lambda s: s.position)]
    for position, item in enumerate(layout):
        section = sections[item["key"]]
        section.position, section.is_enabled = position, bool(item.get("is_enabled", True))
        section.save(update_fields=["position", "is_enabled", "updated_at"])
    record(
        "cms.homepage.layout",
        actor,
        target_type="homepage",
        before={"layout": before},
        after={"layout": [{"key": i["key"], "is_enabled": bool(i.get("is_enabled", True))} for i in layout]},
        request=request,
    )
    _refresh_after_commit()
    return sorted(sections.values(), key=lambda s: s.position)


def _banner(key: str) -> Banner:
    banner = Banner.objects.select_for_update().filter(key=key).first()
    if banner is None or key not in c.BANNER_FIELDS:
        raise NotFound(key)
    return banner


def save_banner_draft(key: str, raw: Any) -> Banner:
    with transaction.atomic():
        banner = _banner(key)
        banner.draft = c.validate_banner(key, raw)
        banner.save(update_fields=["draft", "updated_at"])
    return banner


@transaction.atomic
def publish_banner(key: str, actor: Actor, request: HttpRequest | None = None) -> Banner:
    banner = _banner(key)
    if banner.draft is None:
        raise c.ContentError("There are no unpublished changes.")
    before = banner.content
    banner.content, banner.draft = banner.draft, None
    banner.save(update_fields=["content", "draft", "updated_at"])
    record(
        "cms.banner.publish",
        actor,
        target_type="banner",
        target_id=key,
        before={"content": before},
        after={"content": banner.content},
        request=request,
    )
    _refresh_after_commit()
    return banner


def discard_banner_draft(key: str) -> Banner:
    with transaction.atomic():
        banner = _banner(key)
        banner.draft = None
        banner.save(update_fields=["draft", "updated_at"])
    return banner


@transaction.atomic
def set_banner_enabled(key: str, enabled: bool, actor: Actor, request: HttpRequest | None = None) -> Banner:
    banner = _banner(key)
    before = banner.is_enabled
    banner.is_enabled = enabled
    banner.save(update_fields=["is_enabled", "updated_at"])
    record(
        "cms.banner.visibility",
        actor,
        target_type="banner",
        target_id=key,
        before={"is_enabled": before},
        after={"is_enabled": enabled},
        request=request,
    )
    _refresh_after_commit()
    return banner


# --- Navigation ------------------------------------------------------------------------------------------


def menu_items(menu: str) -> list[dict[str, Any]]:
    return [{"label": i.label, "href": i.href} for i in NavigationItem.objects.filter(menu=menu).order_by("position")]


@transaction.atomic
def replace_menu(menu: str, raw: Any, actor: Actor, request: HttpRequest | None = None) -> list[dict[str, Any]]:
    if menu not in NavigationMenu.values:
        raise NotFound(menu)
    items = c.validate_menu(raw)
    before = menu_items(menu)
    NavigationItem.objects.filter(menu=menu).delete()
    NavigationItem.objects.bulk_create(
        NavigationItem(menu=menu, label=item["label"], href=item["href"], position=position)
        for position, item in enumerate(items)
    )
    record(
        "cms.navigation.change",
        actor,
        target_type="navigation",
        target_id=menu,
        before={"items": before},
        after={"items": items},
        request=request,
    )
    _refresh_after_commit()
    return items


# --- SEO and redirects -----------------------------------------------------------------------------------


def seo_keys() -> list[str]:
    return [*FIXED_SEO_KEYS, *(f"collection:{slug}" for slug in Collection.objects.values_list("slug", flat=True))]


@transaction.atomic
def set_seo(key: str, raw: Any, noindex: bool, actor: Actor, request: HttpRequest | None = None) -> SEORecord:
    if key not in seo_keys():
        raise NotFound(key)
    existing = SEORecord.objects.filter(key=key).first()
    before = None if existing is None else {"content": existing.content, "noindex": existing.noindex}
    seo, _ = SEORecord.objects.update_or_create(key=key, defaults={"content": c.validate_seo(raw), "noindex": noindex})
    record(
        "seo.change",
        actor,
        target_type="seo",
        target_id=key,
        before=before,
        after={"content": seo.content, "noindex": noindex},
        request=request,
    )
    _refresh_after_commit()
    return seo


def _redirect_internal(from_path: str, to_path: str, source: str, permanent: bool = True) -> Redirect:
    """Adds from -> to and points every redirect that ended at `from` straight to `to`, so there are no chains."""
    Redirect.objects.filter(from_path=to_path.split("?")[0], to_path=from_path).delete()  # would loop
    Redirect.objects.filter(from_path=from_path).delete()
    Redirect.objects.filter(to_path=from_path).update(to_path=to_path)
    return Redirect.objects.create(from_path=from_path, to_path=to_path, source=source, is_permanent=permanent)


@transaction.atomic
def create_redirect(
    from_path: Any, to_path: Any, permanent: bool, actor: Actor, request: HttpRequest | None = None
) -> Redirect:
    source = c.validate_redirect_from(from_path)
    target = c.validate_href(to_path, "To")
    if target.split("?")[0] == source:
        raise c.ContentError("A redirect can't point to itself.")
    if Redirect.objects.filter(from_path=source).exists():
        raise c.ContentError("From: there is already a redirect from that path.")
    if Redirect.objects.filter(from_path=target.split("?")[0]).exists():
        raise c.ContentError("To: that path redirects too. Point to its final destination instead.")
    redirect = _redirect_internal(source, target, RedirectSource.MANUAL, permanent)
    record(
        "redirect.create",
        actor,
        target_type="redirect",
        target_id=redirect.pk,
        after={"from": source, "to": target, "permanent": permanent},
        request=request,
    )
    _refresh_after_commit()
    return redirect


@transaction.atomic
def delete_redirect(redirect: Redirect, actor: Actor, request: HttpRequest | None = None) -> None:
    record(
        "redirect.delete",
        actor,
        target_type="redirect",
        target_id=redirect.pk,
        before={"from": redirect.from_path, "to": redirect.to_path},
        request=request,
    )
    redirect.delete()
    _refresh_after_commit()
