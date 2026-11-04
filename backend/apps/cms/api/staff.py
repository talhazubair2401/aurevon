"""/api/v1/staff/cms/…, /staff/seo and /staff/redirects (MTS §8 "Staff: content and marketing").

Permissions (decision 0003, matrix): `cms.edit` reads content and saves drafts; `cms.publish` makes anything
live (publishing, unpublishing, homepage order and visibility, navigation, renaming a live page); `seo.edit`
covers search settings and redirects. Every live change is written to the audit log by the services."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor
from apps.catalog.models import Collection
from common.exceptions import ApiProblem

from .. import content as c
from .. import publishing
from ..models import Banner, HomepageSection, HomepageSectionKey, NavigationMenu, Page, Redirect, SEORecord

TAG = ["staff content"]
BANNER_LABELS = {"shop_editorial": "Shop All editorial banner"}


class FieldSpecOut(serializers.Serializer[Any]):
    name = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    kind = serializers.ChoiceField(choices=["text", "textarea", "href"])
    max_length = serializers.IntegerField()
    required = serializers.BooleanField()  # type: ignore[assignment]
    translatable = serializers.BooleanField()


class EditableBlockOut(serializers.Serializer[Any]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    is_enabled = serializers.BooleanField()
    position = serializers.IntegerField()
    content = serializers.JSONField()
    draft = serializers.JSONField(allow_null=True)
    fields = FieldSpecOut(many=True)  # type: ignore[assignment]
    updated_at = serializers.DateTimeField()


class ContentIn(serializers.Serializer[Any]):
    content = serializers.JSONField()


class LayoutItemIn(serializers.Serializer[Any]):
    key = serializers.CharField()
    is_enabled = serializers.BooleanField()


class LayoutIn(serializers.Serializer[Any]):
    sections = LayoutItemIn(many=True)


class EnabledIn(serializers.Serializer[Any]):
    is_enabled = serializers.BooleanField()


class PageSummaryOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    path = serializers.CharField()
    kind = serializers.ChoiceField(choices=["content", "policy"])
    title = serializers.CharField()
    is_published = serializers.BooleanField()
    published_at = serializers.DateTimeField(allow_null=True)
    has_draft = serializers.BooleanField()
    updated_at = serializers.DateTimeField()


class PageOut(PageSummaryOut):
    content = serializers.JSONField()
    draft = serializers.JSONField(allow_null=True)
    fields = FieldSpecOut(many=True)  # type: ignore[assignment]


class PageCreateIn(serializers.Serializer[Any]):
    slug = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=["content", "policy"])
    content = serializers.JSONField()


class PageSettingsIn(serializers.Serializer[Any]):
    slug = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=["content", "policy"])


class NavLinkOut(serializers.Serializer[Any]):
    label = serializers.DictField(child=serializers.CharField())  # type: ignore[assignment]
    href = serializers.CharField()


class MenuOut(serializers.Serializer[Any]):
    menu = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    items = NavLinkOut(many=True)


class MenuIn(serializers.Serializer[Any]):
    items = serializers.JSONField()


class SeoOut(serializers.Serializer[Any]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    path = serializers.CharField()
    content = serializers.JSONField()
    noindex = serializers.BooleanField()
    fields = FieldSpecOut(many=True)  # type: ignore[assignment]


class SeoIn(serializers.Serializer[Any]):
    content = serializers.JSONField()
    noindex = serializers.BooleanField()


class RedirectOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    from_path = serializers.CharField()
    to_path = serializers.CharField()
    is_permanent = serializers.BooleanField()
    source = serializers.ChoiceField(choices=["manual", "slug_change"])  # type: ignore[assignment]
    created_at = serializers.DateTimeField()


class RedirectIn(serializers.Serializer[Any]):
    from_path = serializers.CharField(max_length=200)
    to_path = serializers.CharField(max_length=200)
    is_permanent = serializers.BooleanField(default=True)


def _valid(serializer_class: type[serializers.Serializer[Any]], request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class _ContentView(StaffAPIView):
    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, c.ContentError):
            exc = ApiProblem(400, "invalid-content", str(exc))
        elif isinstance(exc, publishing.NotFound | Page.DoesNotExist | Redirect.DoesNotExist):
            exc = ApiProblem(404, "not-found", "Not found.")
        return super().handle_exception(exc)


# --- Homepage sections and banners -----------------------------------------------------------------------


def section_out(s: HomepageSection) -> dict[str, Any]:
    return {
        "key": s.key,
        "label": HomepageSectionKey(s.key).label,
        "is_enabled": s.is_enabled,
        "position": s.position,
        "content": s.content,
        "draft": s.draft,
        "fields": [f.describe() for f in c.SECTION_FIELDS[s.key]],
        "updated_at": s.updated_at,
    }


def banner_out(b: Banner) -> dict[str, Any]:
    return {
        "key": b.key,
        "label": BANNER_LABELS.get(b.key, b.key),
        "is_enabled": b.is_enabled,
        "position": 0,
        "content": b.content,
        "draft": b.draft,
        "fields": [f.describe() for f in c.BANNER_FIELDS[b.key]],
        "updated_at": b.updated_at,
    }


class HomeSectionsView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(tags=TAG, responses={200: EditableBlockOut(many=True)}, operation_id="staff_cms_sections")
    def get(self, request: Request) -> Response:
        return Response([section_out(s) for s in HomepageSection.objects.order_by("position")])


class HomeLayoutView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(
        tags=TAG, request=LayoutIn, responses={200: EditableBlockOut(many=True)}, operation_id="staff_cms_layout"
    )
    def put(self, request: Request) -> Response:
        data = _valid(LayoutIn, request)
        sections = publishing.set_homepage_layout(data["sections"], self.actor(), request)
        return Response([section_out(s) for s in sections])


class HomeSectionDraftView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(
        tags=TAG, request=ContentIn, responses={200: EditableBlockOut}, operation_id="staff_cms_section_draft"
    )
    def put(self, request: Request, key: str) -> Response:
        if key not in HomepageSectionKey.values:
            raise publishing.NotFound(key)
        return Response(section_out(publishing.save_section_draft(key, _valid(ContentIn, request)["content"])))

    @extend_schema(tags=TAG, responses={200: EditableBlockOut}, operation_id="staff_cms_section_discard")
    def delete(self, request: Request, key: str) -> Response:
        if key not in HomepageSectionKey.values:
            raise publishing.NotFound(key)
        return Response(section_out(publishing.discard_section_draft(key)))


class HomeSectionPublishView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(tags=TAG, request=None, responses={200: EditableBlockOut}, operation_id="staff_cms_section_publish")
    def post(self, request: Request, key: str) -> Response:
        if key not in HomepageSectionKey.values:
            raise publishing.NotFound(key)
        return Response(section_out(publishing.publish_section(key, self.actor(), request)))


class BannersView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(tags=TAG, responses={200: EditableBlockOut(many=True)}, operation_id="staff_cms_banners")
    def get(self, request: Request) -> Response:
        return Response([banner_out(b) for b in Banner.objects.filter(key__in=c.BANNER_FIELDS).order_by("key")])


class BannerView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(
        tags=TAG, request=EnabledIn, responses={200: EditableBlockOut}, operation_id="staff_cms_banner_visibility"
    )
    def put(self, request: Request, key: str) -> Response:
        data = _valid(EnabledIn, request)
        return Response(banner_out(publishing.set_banner_enabled(key, data["is_enabled"], self.actor(), request)))


class BannerDraftView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(
        tags=TAG, request=ContentIn, responses={200: EditableBlockOut}, operation_id="staff_cms_banner_draft"
    )
    def put(self, request: Request, key: str) -> Response:
        return Response(banner_out(publishing.save_banner_draft(key, _valid(ContentIn, request)["content"])))

    @extend_schema(tags=TAG, responses={200: EditableBlockOut}, operation_id="staff_cms_banner_discard")
    def delete(self, request: Request, key: str) -> Response:
        return Response(banner_out(publishing.discard_banner_draft(key)))


class BannerPublishView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(tags=TAG, request=None, responses={200: EditableBlockOut}, operation_id="staff_cms_banner_publish")
    def post(self, request: Request, key: str) -> Response:
        return Response(banner_out(publishing.publish_banner(key, self.actor(), request)))


# --- Pages -----------------------------------------------------------------------------------------------


def _page_title(page: Page) -> str:
    for source in (page.draft, page.content):
        if source and source.get("en", {}).get("title"):
            return str(source["en"]["title"])
    return page.slug


def page_summary(page: Page) -> dict[str, Any]:
    return {
        "id": page.pk,
        "slug": page.slug,
        "path": publishing.page_path(page.slug),
        "kind": page.kind,
        "title": _page_title(page),
        "is_published": page.is_published,
        "published_at": page.published_at,
        "has_draft": page.draft is not None,
        "updated_at": page.updated_at,
    }


def page_out(page: Page) -> dict[str, Any]:
    return {
        **page_summary(page),
        "content": page.content,
        "draft": page.draft,
        "fields": [f.describe() for f in c.PAGE_FIELDS],
    }


class PagesView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(tags=TAG, responses={200: PageSummaryOut(many=True)}, operation_id="staff_cms_pages")
    def get(self, request: Request) -> Response:
        return Response([page_summary(p) for p in Page.objects.order_by("kind", "slug")])

    @extend_schema(tags=TAG, request=PageCreateIn, responses={201: PageOut}, operation_id="staff_cms_page_create")
    def post(self, request: Request) -> Response:
        data = _valid(PageCreateIn, request)
        page = publishing.create_page(data["slug"], data["kind"], data["content"], self.actor(), request)
        return Response(page_out(page), status=status.HTTP_201_CREATED)


class PageView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(tags=TAG, responses={200: PageOut}, operation_id="staff_cms_page")
    def get(self, request: Request, page_id: str) -> Response:
        return Response(page_out(Page.objects.get(pk=page_id)))

    @extend_schema(tags=TAG, request=PageSettingsIn, responses={200: PageOut}, operation_id="staff_cms_page_settings")
    def put(self, request: Request, page_id: str) -> Response:
        page = Page.objects.get(pk=page_id)
        data = _valid(PageSettingsIn, request)
        if page.is_published and not access.has_perm(self.account, Perm.CMS_PUBLISH):
            raise ApiProblem(403, "permission-denied", "Changing a live page's address needs publishing rights.")
        return Response(
            page_out(publishing.change_page_settings(page, data["slug"], data["kind"], self.actor(), request))
        )


class PageDraftView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(tags=TAG, request=ContentIn, responses={200: PageOut}, operation_id="staff_cms_page_draft")
    def put(self, request: Request, page_id: str) -> Response:
        page = Page.objects.get(pk=page_id)
        return Response(page_out(publishing.save_page_draft(page, _valid(ContentIn, request)["content"])))

    @extend_schema(tags=TAG, responses={200: PageOut}, operation_id="staff_cms_page_discard")
    def delete(self, request: Request, page_id: str) -> Response:
        return Response(page_out(publishing.discard_page_draft(Page.objects.get(pk=page_id))))


class PagePublishView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(tags=TAG, request=None, responses={200: PageOut}, operation_id="staff_cms_page_publish")
    def post(self, request: Request, page_id: str) -> Response:
        return Response(page_out(publishing.publish_page(Page.objects.get(pk=page_id), self.actor(), request)))


class PageUnpublishView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(tags=TAG, request=None, responses={200: PageOut}, operation_id="staff_cms_page_unpublish")
    def post(self, request: Request, page_id: str) -> Response:
        return Response(page_out(publishing.unpublish_page(Page.objects.get(pk=page_id), self.actor(), request)))


# --- Navigation ------------------------------------------------------------------------------------------


def menu_out(menu: str) -> dict[str, Any]:
    return {"menu": menu, "label": NavigationMenu(menu).label, "items": publishing.menu_items(menu)}


class NavigationView(_ContentView):
    required_permission = Perm.CMS_EDIT

    @extend_schema(tags=TAG, responses={200: MenuOut(many=True)}, operation_id="staff_cms_navigation")
    def get(self, request: Request) -> Response:
        return Response([menu_out(menu) for menu in NavigationMenu.values])


class MenuView(_ContentView):
    required_permission = Perm.CMS_PUBLISH

    @extend_schema(tags=TAG, request=MenuIn, responses={200: MenuOut}, operation_id="staff_cms_menu_set")
    def put(self, request: Request, menu: str) -> Response:
        publishing.replace_menu(menu, _valid(MenuIn, request)["items"], self.actor(), request)
        return Response(menu_out(menu))


# --- SEO and redirects -----------------------------------------------------------------------------------


def _seo_label_and_path(key: str, names: dict[str, str]) -> tuple[str, str]:
    fixed = {"home": ("Homepage", "/"), "shop": ("Shop All", "/shop"), "collections": ("Collections", "/collections")}
    if key in fixed:
        return fixed[key]
    slug = key.removeprefix("collection:")
    return f"Collection: {names.get(slug, slug)}", f"/collections/{slug}"


def seo_out(key: str, record: SEORecord | None, names: dict[str, str]) -> dict[str, Any]:
    label, path = _seo_label_and_path(key, names)
    return {
        "key": key,
        "label": label,
        "path": path,
        "content": record.content if record else {"en": {}, "ur": {}},
        "noindex": record.noindex if record else False,
        "fields": [f.describe() for f in c.SEO_FIELDS],
    }


class SeoListView(_ContentView):
    required_permission = Perm.SEO_EDIT

    @extend_schema(tags=TAG, responses={200: SeoOut(many=True)}, operation_id="staff_seo_list")
    def get(self, request: Request) -> Response:
        records = {r.key: r for r in SEORecord.objects.all()}
        names = dict(Collection.objects.values_list("slug", "name_en"))
        return Response([seo_out(key, records.get(key), names) for key in publishing.seo_keys()])


class SeoView(_ContentView):
    required_permission = Perm.SEO_EDIT

    @extend_schema(tags=TAG, request=SeoIn, responses={200: SeoOut}, operation_id="staff_seo_set")
    def put(self, request: Request, key: str) -> Response:
        data = _valid(SeoIn, request)
        record = publishing.set_seo(key, data["content"], data["noindex"], self.actor(), request)
        return Response(seo_out(key, record, dict(Collection.objects.values_list("slug", "name_en"))))


def redirect_out(r: Redirect) -> dict[str, Any]:
    return {
        "id": r.pk,
        "from_path": r.from_path,
        "to_path": r.to_path,
        "is_permanent": r.is_permanent,
        "source": r.source,
        "created_at": r.created_at,
    }


class RedirectsView(_ContentView):
    required_permission = Perm.SEO_EDIT

    @extend_schema(tags=TAG, responses={200: RedirectOut(many=True)}, operation_id="staff_redirects")
    def get(self, request: Request) -> Response:
        return Response([redirect_out(r) for r in Redirect.objects.order_by("from_path")])

    @extend_schema(tags=TAG, request=RedirectIn, responses={201: RedirectOut}, operation_id="staff_redirect_create")
    def post(self, request: Request) -> Response:
        data = _valid(RedirectIn, request)
        redirect = publishing.create_redirect(
            data["from_path"], data["to_path"], data["is_permanent"], self.actor(), request
        )
        return Response(redirect_out(redirect), status=status.HTTP_201_CREATED)


class RedirectView(_ContentView):
    required_permission = Perm.SEO_EDIT

    @extend_schema(tags=TAG, responses={204: None}, operation_id="staff_redirect_delete")
    def delete(self, request: Request, redirect_id: str) -> Response:
        publishing.delete_redirect(Redirect.objects.get(pk=redirect_id), self.actor(), request)
        return Response(status=status.HTTP_204_NO_CONTENT)
