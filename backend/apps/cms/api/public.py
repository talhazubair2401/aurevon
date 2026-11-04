"""Public CMS reads for the storefront (MTS §8 Content): GET /cms/home and GET /cms/banners/{key}."""

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

from ..models import Banner, HomepageSection, HomepageSectionKey

LOCALE_PARAM = OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"])
HOME_PRODUCTS = 8


def localised(content: dict[str, Any], locale: str) -> dict[str, Any]:
    """The section's copy in `locale`, falling back field by field to English."""
    english: dict[str, Any] = content.get("en", {})
    chosen: dict[str, Any] = content.get(locale, {})
    return {**english, **{k: v for k, v in chosen.items() if v not in (None, "")}}


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
