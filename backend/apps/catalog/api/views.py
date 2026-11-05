"""Public catalogue API (MTS §8): GET /catalog/products, /catalog/facets, /catalog/categories, /catalog/collections."""

from decimal import Decimal, InvalidOperation
from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.inventory import selectors as inventory
from common.api import PublicAPIView, request_locale
from common.exceptions import ApiProblem

from .. import presenters, selectors
from ..models import Department

MAX_LIST_VALUES = 20


class ProductCursor(CursorPagination):
    page_size = 24
    max_page_size = 48
    page_size_query_param = "limit"
    ordering = selectors.SORTS[selectors.DEFAULT_SORT]


def _list_param(request: Request, name: str) -> list[str]:
    values = [v for raw in request.query_params.getlist(name) for v in raw.split(",") if v]
    return values[:MAX_LIST_VALUES]


def _decimal(request: Request, name: str) -> Decimal | None:
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValidationError({name: "Must be a number."}) from exc
    if value < 0 or not value.is_finite():
        raise ValidationError({name: "Must be zero or more."})
    return value


def parse_filters(request: Request) -> selectors.ProductFilters:
    department = request.query_params.get("department") or None
    if department and department not in Department.values:
        raise ValidationError({"department": "Must be women or men."})
    return selectors.ProductFilters(
        department=department,
        category=request.query_params.get("category") or None,
        collection=request.query_params.get("collection") or None,
        sizes=_list_param(request, "size"),
        colours=_list_param(request, "colour"),
        price_min=_decimal(request, "price_min"),
        price_max=_decimal(request, "price_max"),
        query=(request.query_params.get("q") or "").strip()[:100],
    )


FILTER_PARAMS = [
    OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"]),
    OpenApiParameter("department", OpenApiTypes.STR, enum=["women", "men"]),
    OpenApiParameter("category", OpenApiTypes.STR),
    OpenApiParameter("collection", OpenApiTypes.STR),
    OpenApiParameter("size", OpenApiTypes.STR, description="Comma-separated sizes"),
    OpenApiParameter("colour", OpenApiTypes.STR, description="Comma-separated colour slugs"),
    OpenApiParameter("price_min", OpenApiTypes.DECIMAL),
    OpenApiParameter("price_max", OpenApiTypes.DECIMAL),
    OpenApiParameter("q", OpenApiTypes.STR, description="Search words (English or Urdu)"),
]


class MoneySerializer(serializers.Serializer[Any]):
    amount = serializers.CharField()
    currency = serializers.CharField()


class CategoryRefSerializer(serializers.Serializer[Any]):
    slug = serializers.CharField()
    department = serializers.ChoiceField(choices=Department.values)
    name = serializers.CharField()


class ProductColourSerializer(serializers.Serializer[Any]):
    slug = serializers.CharField()
    name = serializers.CharField()
    hex = serializers.CharField()


class ProductCardImageSerializer(serializers.Serializer[Any]):
    url = serializers.CharField(allow_null=True)
    demo_art = serializers.CharField(allow_null=True)
    tone = serializers.CharField()
    alt = serializers.CharField()


class ProductCardSerializer(serializers.Serializer[Any]):
    slug = serializers.CharField()
    name = serializers.CharField()
    department = serializers.ChoiceField(choices=Department.values)
    category = CategoryRefSerializer()
    price_min = MoneySerializer()
    price_max = MoneySerializer()
    colours = ProductColourSerializer(many=True)
    sizes = serializers.ListField(child=serializers.CharField())
    image = ProductCardImageSerializer(allow_null=True)
    is_new = serializers.BooleanField()
    is_featured = serializers.BooleanField()


class ProductPageSerializer(serializers.Serializer[Any]):
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = ProductCardSerializer(many=True)


class CollectionCardSerializer(serializers.Serializer[Any]):
    slug = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    demo_art = serializers.CharField(allow_null=True)
    tone = serializers.CharField()


class CountFacetSerializer(serializers.Serializer[Any]):
    value = serializers.CharField()
    count = serializers.IntegerField()


class CategoryFacetSerializer(CategoryRefSerializer):
    count = serializers.IntegerField()


class ColourFacetSerializer(ProductColourSerializer):
    count = serializers.IntegerField()


class PriceFacetSerializer(serializers.Serializer[Any]):
    min = serializers.CharField(allow_null=True)
    max = serializers.CharField(allow_null=True)
    currency = serializers.CharField()


class FacetsSerializer(serializers.Serializer[Any]):
    departments = CountFacetSerializer(many=True)
    categories = CategoryFacetSerializer(many=True)
    sizes = CountFacetSerializer(many=True)
    colours = ColourFacetSerializer(many=True)
    price = PriceFacetSerializer()


class ProductListView(PublicAPIView):
    @extend_schema(
        tags=["catalogue"],
        operation_id="catalog_products_list",
        parameters=[
            *FILTER_PARAMS,
            OpenApiParameter("sort", OpenApiTypes.STR, enum=list(selectors.SORTS)),
            OpenApiParameter("cursor", OpenApiTypes.STR),
            OpenApiParameter("limit", OpenApiTypes.INT),
        ],
        responses=ProductPageSerializer,
    )
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        sort = request.query_params.get("sort", selectors.DEFAULT_SORT)
        if sort not in selectors.SORTS:
            raise ValidationError({"sort": f"Must be one of {', '.join(selectors.SORTS)}."})
        paginator = ProductCursor()
        paginator.ordering = selectors.SORTS[sort]
        page = paginator.paginate_queryset(selectors.products(parse_filters(request), sort), request, view=self)
        return paginator.get_paginated_response([presenters.product_card(p, locale) for p in page or []])


class FacetsView(PublicAPIView):
    @extend_schema(
        tags=["catalogue"],
        operation_id="catalog_facets",
        parameters=FILTER_PARAMS,
        responses=FacetsSerializer,
    )
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        return Response(presenters.localise_facets(selectors.facets(parse_filters(request)), locale))


class CategoryListView(PublicAPIView):
    @extend_schema(
        tags=["catalogue"],
        operation_id="catalog_categories",
        parameters=[OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"])],
        responses=CategoryRefSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        return Response([presenters.category(c, locale) for c in selectors.categories()])


class CollectionListView(PublicAPIView):
    @extend_schema(
        tags=["catalogue"],
        operation_id="catalog_collections",
        parameters=[OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"])],
        responses=CollectionCardSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        return Response([presenters.collection(c, locale) for c in selectors.published_collections()])


class CollectionDetailView(PublicAPIView):
    @extend_schema(
        tags=["catalogue"],
        operation_id="catalog_collection",
        parameters=[OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"])],
        responses=CollectionCardSerializer,
    )
    def get(self, request: Request, slug: str) -> Response:
        locale = request_locale(request)
        collection = selectors.published_collections().filter(slug=slug).first()
        if collection is None:
            raise ApiProblem(404, "not-found", "No such collection.")
        return Response(presenters.collection(collection, locale))


class ProductImageSerializer(serializers.Serializer[Any]):
    url = serializers.CharField(allow_null=True)
    demo_art = serializers.CharField(allow_null=True)
    colour = serializers.CharField(allow_null=True)
    tone = serializers.CharField()
    alt = serializers.CharField()


class VariantSerializer(serializers.Serializer[Any]):
    sku = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    price = MoneySerializer()


class SizeChartRowSerializer(serializers.Serializer[Any]):
    name = serializers.CharField()
    values = serializers.DictField(child=serializers.CharField())


class Model3DSerializer(serializers.Serializer[Any]):
    url = serializers.CharField()
    compression = serializers.CharField()
    checksum = serializers.CharField()
    variant_map = serializers.DictField(child=serializers.CharField(allow_blank=True))


class ProductDetailSerializer(ProductCardSerializer):
    description = serializers.CharField(allow_blank=True)
    fabric = serializers.CharField(allow_blank=True)
    care = serializers.CharField(allow_blank=True)
    fit_note = serializers.CharField(allow_blank=True)
    style_number = serializers.CharField()
    images = ProductImageSerializer(many=True)
    variants = VariantSerializer(many=True)
    size_chart = SizeChartRowSerializer(many=True)
    collections = CollectionCardSerializer(many=True)
    model3d = Model3DSerializer(allow_null=True)


class VariantAvailabilitySerializer(serializers.Serializer[Any]):
    sku = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    price = MoneySerializer()
    available = serializers.BooleanField()


class AvailabilitySerializer(serializers.Serializer[Any]):
    variants = VariantAvailabilitySerializer(many=True)


class ProductDetailView(PublicAPIView):
    @extend_schema(
        tags=["catalogue"],
        operation_id="catalog_product",
        parameters=[OpenApiParameter("locale", OpenApiTypes.STR, enum=["en", "ur"])],
        responses=ProductDetailSerializer,
    )
    def get(self, request: Request, slug: str) -> Response:
        locale = request_locale(request)
        product = selectors.product_detail(slug)
        if product is None:
            raise ApiProblem(404, "not-found", "No such product.")
        return Response(presenters.product_detail(product, locale))


class AvailabilityView(PublicAPIView):
    """Fresh price and stock per variant (MTS §8 Availability; A-15). Never cached."""

    @extend_schema(tags=["catalogue"], operation_id="catalog_product_availability", responses=AvailabilitySerializer)
    def get(self, request: Request, slug: str) -> Response:
        product = selectors.product_detail(slug)
        if product is None:
            raise ApiProblem(404, "not-found", "No such product.")
        variants = list(product.variants.all())
        stock = inventory.available(v.pk for v in variants)
        response = Response(
            {
                "variants": [
                    {
                        "sku": v.sku,
                        "size": v.size,
                        "colour": v.colour.slug,
                        "price": {"amount": f"{v.price:.2f}", "currency": v.currency},
                        "available": stock[v.pk] > 0,
                    }
                    for v in variants
                ]
            }
        )
        response["Cache-Control"] = "no-store"
        return response


def cards(products: list[Any], locale: str) -> list[dict[str, Any]]:
    return [presenters.product_card(p, locale) for p in products]
