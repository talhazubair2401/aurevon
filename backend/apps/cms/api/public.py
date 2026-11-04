"""Public CMS reads for the storefront (MTS §8 Content): home, banners, pages, navigation, SEO and redirects.

Only published content is ever returned; drafts never leave the staff API."""

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.catalog import presenters as catalog_presenters
from apps.catalog import selectors as catalog
from apps.catalog.api.views import CollectionCardSerializer, ProductCardSerializer
from common.api import PublicAPIView, request_locale
from common.exceptions import ApiProblem

from ..content import localised
from ..models import (
    Banner,
    HomepageSection,
    HomepageSectionKey,
    NavigationItem,
    NavigationMenu,
    Page,
    Redirect,
    SEORecord,
)

LOCALE_PARAM = OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"])
HOME_PRODUCTS = 8


class HomeSectionSerializer(serializers.Serializer[Any]):
    key = serializers.ChoiceField(choices=HomepageSectionKey.values)
    content = serializers.DictField()
    collections = CollectionCardSerializer(many=True, required=False)
    products = ProductCardSerializer(many=True, required=False)


class HomeSerializer(serializers.Serializer[Any]):
    sections = HomeSectionSerializer(many=True)


class BannerSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    content = serializers.DictField()


class HomeView(PublicAPIView):
    @extend_schema(tags=["content"], operation_id="cms_home", parameters=[LOCALE_PARAM], responses=HomeSerializer)
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        sections: list[dict[str, Any]] = []
        for section in HomepageSection.objects.filter(is_enabled=True).order_by("position"):
            item: dict[str, Any] = {"key": section.key, "content": localised(section.content, locale)}
            if section.key == HomepageSectionKey.COLLECTIONS:
                item["collections"] = [
                    catalog_presenters.collection(c, locale) for c in catalog.published_collections()[:4]
                ]
            elif section.key == HomepageSectionKey.FEATURED_PRODUCTS:
                item["products"] = [catalog_presenters.product_card(p, locale) for p in catalog.featured(HOME_PRODUCTS)]
            elif section.key == HomepageSectionKey.NEW_ARRIVALS:
                item["products"] = [
                    catalog_presenters.product_card(p, locale) for p in catalog.new_arrivals(HOME_PRODUCTS)
                ]
            sections.append(item)
        return Response({"sections": sections})


class BannerView(PublicAPIView):
    @extend_schema(tags=["content"], operation_id="cms_banner", parameters=[LOCALE_PARAM], responses=BannerSerializer)
    def get(self, request: Request, key: str) -> Response:
        locale = request_locale(request)
        banner = Banner.objects.filter(key=key, is_enabled=True).first()
        if banner is None:
            raise ApiProblem(404, "not-found", "No such banner.")
        return Response({"key": banner.key, "content": localised(banner.content, locale)})


class PageBlockSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=["heading", "paragraph", "list"])
    text = serializers.CharField(required=False)
    items = serializers.ListField(child=serializers.CharField(), required=False)


class PageSerializer(serializers.Serializer[Any]):
    slug = serializers.CharField()
    kind = serializers.ChoiceField(choices=["content", "policy"])
    title = serializers.CharField()
    summary = serializers.CharField(allow_blank=True)
    body = PageBlockSerializer(many=True)
    seo_title = serializers.CharField(allow_blank=True)
    seo_description = serializers.CharField(allow_blank=True)
    # True when this language has its own copy; false when the page is shown in English as a fallback.
    translated = serializers.BooleanField()
    updated_at = serializers.DateTimeField()


class PageSummarySerializer(serializers.Serializer[Any]):
    slug = serializers.CharField()
    kind = serializers.ChoiceField(choices=["content", "policy"])
    title = serializers.CharField()
    updated_at = serializers.DateTimeField()


def page_body(page: Page, locale: str) -> dict[str, Any]:
    copy = localised(page.content, locale)
    own = page.content.get(locale, {}) if locale != "en" else page.content.get("en", {})
    return {
        "slug": page.slug,
        "kind": page.kind,
        "title": copy.get("title", page.slug),
        "summary": copy.get("summary", ""),
        "body": copy.get("body", []),
        "seo_title": copy.get("seo_title", ""),
        "seo_description": copy.get("seo_description", "") or copy.get("summary", ""),
        "translated": bool(own.get("title") and own.get("body")),
        "updated_at": page.updated_at,
    }


class PageListView(PublicAPIView):
    @extend_schema(
        tags=["content"],
        operation_id="cms_pages",
        parameters=[LOCALE_PARAM],
        responses=PageSummarySerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        return Response(
            [
                {
                    "slug": p.slug,
                    "kind": p.kind,
                    "title": localised(p.content, locale).get("title", p.slug),
                    "updated_at": p.updated_at,
                }
                for p in Page.objects.filter(is_published=True).order_by("kind", "slug")
            ]
        )


class PageView(PublicAPIView):
    @extend_schema(tags=["content"], operation_id="cms_page", parameters=[LOCALE_PARAM], responses=PageSerializer)
    def get(self, request: Request, slug: str) -> Response:
        locale = request_locale(request)
        page = Page.objects.filter(slug=slug, is_published=True).first()
        if page is None:
            raise ApiProblem(404, "not-found", "No such page.")
        return Response(page_body(page, locale))


class NavLinkSerializer(serializers.Serializer[Any]):
    label = serializers.CharField()  # type: ignore[assignment]
    href = serializers.CharField()


class NavigationSerializer(serializers.Serializer[Any]):
    header = NavLinkSerializer(many=True)
    footer_shop = NavLinkSerializer(many=True)
    footer_help = NavLinkSerializer(many=True)


class NavigationView(PublicAPIView):
    @extend_schema(
        tags=["content"], operation_id="cms_navigation", parameters=[LOCALE_PARAM], responses=NavigationSerializer
    )
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        menus: dict[str, list[dict[str, str]]] = {menu: [] for menu in NavigationMenu.values}
        for item in NavigationItem.objects.order_by("menu", "position"):
            label = item.label.get(locale) or item.label.get("en", "")
            menus[item.menu].append({"label": label, "href": item.href})
        return Response(menus)


class SeoSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    noindex = serializers.BooleanField()


class SeoView(PublicAPIView):
    @extend_schema(tags=["content"], operation_id="cms_seo", parameters=[LOCALE_PARAM], responses=SeoSerializer)
    def get(self, request: Request, key: str) -> Response:
        locale = request_locale(request)
        seo = SEORecord.objects.filter(key=key).first()
        if seo is None:
            raise ApiProblem(404, "not-found", "No search settings for that page.")
        copy = localised(seo.content, locale)
        return Response(
            {
                "key": seo.key,
                "title": copy.get("title", ""),
                "description": copy.get("description", ""),
                "noindex": seo.noindex,
            }
        )


class RedirectSerializer(serializers.Serializer[Any]):
    to = serializers.CharField()
    permanent = serializers.BooleanField()


class RedirectResolveView(PublicAPIView):
    """Asked by the storefront only for addresses that would otherwise be 'not found'."""

    @extend_schema(
        tags=["content"],
        operation_id="cms_redirect_resolve",
        parameters=[OpenApiParameter("path", OpenApiTypes.STR, required=True)],
        responses=RedirectSerializer,
    )
    def get(self, request: Request) -> Response:
        path = (request.query_params.get("path") or "").rstrip("/")[:200]
        redirect = Redirect.objects.filter(from_path=path).first() if path.startswith("/") else None
        if redirect is None:
            raise ApiProblem(404, "not-found", "No redirect for that path.")
        return Response({"to": redirect.to_path, "permanent": redirect.is_permanent})
