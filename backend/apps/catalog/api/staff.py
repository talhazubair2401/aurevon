"""/api/v1/staff/catalog/… (MTS §8 "Staff: catalogue"; decision 0006).

Permissions (decision 0003): `catalog.view` reads; `catalog.edit` creates and edits products, variants,
categories and colours; `catalog.publish` publishes and archives; `prices.edit` sets prices and imports (prices
come from the file), and every price change asks for the authenticator code again (decision 0003, 2.5)."""

from typing import Any

from django.db.models import Q
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor
from apps.inventory import selectors as inventory
from common.exceptions import ApiProblem

from .. import editing, images, importing
from ..models import Category, Colour, Product, ProductImage, ProductStatus

TAG = ["staff catalogue"]


class _CatalogView(StaffAPIView):
    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, editing.CatalogError):
            exc = ApiProblem(400, "invalid-catalogue", str(exc))
        elif isinstance(exc, Product.DoesNotExist | Category.DoesNotExist | Colour.DoesNotExist):
            exc = ApiProblem(404, "not-found", "Not found.")
        return super().handle_exception(exc)


class ColourOut(serializers.Serializer[Any]):
    slug = serializers.CharField()
    code = serializers.CharField()
    name_en = serializers.CharField()
    name_ur = serializers.CharField()
    hex = serializers.CharField()
    in_use = serializers.BooleanField()


class SizeChartRowOut(serializers.Serializer[Any]):
    name = serializers.DictField(child=serializers.CharField(allow_blank=True))
    values = serializers.DictField(child=serializers.CharField())


class CategoryOut(serializers.Serializer[Any]):
    slug = serializers.CharField()
    code = serializers.CharField()
    department = serializers.CharField()
    name_en = serializers.CharField()
    name_ur = serializers.CharField()
    sizes = serializers.ListField(child=serializers.CharField())
    size_chart = SizeChartRowOut(many=True)
    products = serializers.IntegerField()


class VariantOut(serializers.Serializer[Any]):
    sku = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    price = serializers.CharField()
    price_overridden = serializers.BooleanField()
    is_active = serializers.BooleanField()
    available = serializers.IntegerField()


class ProductSummaryOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=ProductStatus.values)
    style_number = serializers.CharField()
    category = serializers.CharField()
    department = serializers.CharField()
    base_price = serializers.CharField()
    variants = serializers.IntegerField()
    updated_at = serializers.DateTimeField()


class ImageOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    url = serializers.CharField()
    thumb_url = serializers.CharField()
    colour = serializers.CharField()
    alt_en = serializers.CharField()
    alt_ur = serializers.CharField()


class ImageIn(serializers.Serializer[Any]):
    file = serializers.FileField()
    colour = serializers.CharField(allow_blank=True, required=False)
    alt_en = serializers.CharField(max_length=200)
    alt_ur = serializers.CharField(max_length=200, allow_blank=True, required=False)


class ProductOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    status = serializers.ChoiceField(choices=ProductStatus.values)
    style_number = serializers.CharField()
    category = serializers.CharField()
    category_sizes = serializers.ListField(child=serializers.CharField())
    department = serializers.CharField()
    base_price = serializers.CharField()
    is_featured = serializers.BooleanField()
    copy = serializers.JSONField()
    variant_list = VariantOut(many=True)
    publish_problems = serializers.ListField(child=serializers.CharField())
    images = ImageOut(many=True)
    updated_at = serializers.DateTimeField()


class ImportIn(serializers.Serializer[Any]):
    csv = serializers.CharField(max_length=importing.MAX_BYTES, allow_blank=True, trim_whitespace=False)
    apply = serializers.BooleanField(default=False)


class ImportErrorOut(serializers.Serializer[Any]):
    row = serializers.IntegerField()
    message = serializers.CharField()


class ImportOut(serializers.Serializer[Any]):
    rows = serializers.IntegerField()
    created = serializers.ListField(child=serializers.CharField())
    updated = serializers.ListField(child=serializers.CharField())
    errors = ImportErrorOut(many=True)  # type: ignore[assignment]
    applied = serializers.BooleanField()


def _body(request: Request) -> dict[str, Any]:
    if not isinstance(request.data, dict):
        raise editing.CatalogError("Send a JSON object.")
    return dict(request.data)


# --- Colours and categories -------------------------------------------------------------------------------


def colour_out(c: Colour) -> dict[str, Any]:
    return {
        "slug": c.slug,
        "code": c.code,
        "name_en": c.name_en,
        "name_ur": c.name_ur,
        "hex": c.hex,
        "in_use": c.variants.exists(),
    }


class ColoursView(_CatalogView):
    required_permission = {"GET": Perm.CATALOG_VIEW, "POST": Perm.CATALOG_EDIT}

    @extend_schema(tags=TAG, responses={200: ColourOut(many=True)}, operation_id="staff_catalog_colours")
    def get(self, request: Request) -> Response:
        return Response([colour_out(c) for c in Colour.objects.all()])

    @extend_schema(tags=TAG, request=ColourOut, responses={201: ColourOut}, operation_id="staff_catalog_colour_create")
    def post(self, request: Request) -> Response:
        colour = editing.save_colour(None, _body(request), self.actor(), request)
        return Response(colour_out(colour), status=status.HTTP_201_CREATED)


class ColourView(_CatalogView):
    required_permission = Perm.CATALOG_EDIT

    @extend_schema(tags=TAG, request=ColourOut, responses={200: ColourOut}, operation_id="staff_catalog_colour_update")
    def put(self, request: Request, slug: str) -> Response:
        colour = editing.save_colour(Colour.objects.get(slug=slug), _body(request), self.actor(), request)
        return Response(colour_out(colour))


def category_out(c: Category) -> dict[str, Any]:
    return {
        "slug": c.slug,
        "code": c.code,
        "department": c.department,
        "name_en": c.name_en,
        "name_ur": c.name_ur,
        "sizes": c.sizes,
        "size_chart": c.size_chart,
        "products": c.products.count(),
    }


class CategoriesView(_CatalogView):
    required_permission = {"GET": Perm.CATALOG_VIEW, "POST": Perm.CATALOG_EDIT}

    @extend_schema(tags=TAG, responses={200: CategoryOut(many=True)}, operation_id="staff_catalog_categories")
    def get(self, request: Request) -> Response:
        return Response([category_out(c) for c in Category.objects.all()])

    @extend_schema(
        tags=TAG, request=CategoryOut, responses={201: CategoryOut}, operation_id="staff_catalog_category_create"
    )
    def post(self, request: Request) -> Response:
        category = editing.save_category(None, _body(request), self.actor(), request)
        return Response(category_out(category), status=status.HTTP_201_CREATED)


class CategoryView(_CatalogView):
    required_permission = Perm.CATALOG_EDIT

    @extend_schema(
        tags=TAG, request=CategoryOut, responses={200: CategoryOut}, operation_id="staff_catalog_category_update"
    )
    def put(self, request: Request, slug: str) -> Response:
        category = editing.save_category(Category.objects.get(slug=slug), _body(request), self.actor(), request)
        return Response(category_out(category))


# --- Products ---------------------------------------------------------------------------------------------


def _name(p: Product) -> str:
    names = {t.locale: t.name for t in p.translations.all()}
    return names.get("en") or p.slug


def product_summary(p: Product) -> dict[str, Any]:
    return {
        "id": p.pk,
        "slug": p.slug,
        "name": _name(p),
        "status": p.status,
        "style_number": f"{p.style_number:04d}",
        "category": p.category.slug,
        "department": p.department,
        "base_price": f"{p.base_price:.2f}",
        "variants": sum(1 for v in p.variants.all() if v.is_active),
        "updated_at": p.updated_at,
    }


def product_out(p: Product) -> dict[str, Any]:
    p = Product.objects.select_related("category").prefetch_related("translations").get(pk=p.pk)
    variants = list(p.variants.select_related("colour").order_by("position", "sku"))
    stock = inventory.available(v.pk for v in variants)
    return {
        "id": p.pk,
        "slug": p.slug,
        "status": p.status,
        "style_number": f"{p.style_number:04d}",
        "category": p.category.slug,
        "category_sizes": p.category.sizes,
        "department": p.department,
        "base_price": f"{p.base_price:.2f}",
        "is_featured": p.is_featured,
        "copy": editing.product_snapshot(p)["copy"],
        "variant_list": [
            {
                "sku": v.sku,
                "size": v.size,
                "colour": v.colour.slug,
                "price": f"{v.price:.2f}",
                "price_overridden": v.price_overridden,
                "is_active": v.is_active,
                "available": stock[v.pk],
            }
            for v in variants
        ],
        "publish_problems": editing.publish_problems(p),
        "images": [
            {
                "id": i.pk,
                "url": i.url,
                "thumb_url": i.thumb_url,
                "colour": i.colour_slug,
                "alt_en": i.alt_en,
                "alt_ur": i.alt_ur,
            }
            for i in p.images.exclude(url="").order_by("position")
        ],
        "updated_at": p.updated_at,
    }


class ProductsView(_CatalogView):
    required_permission = {"GET": Perm.CATALOG_VIEW, "POST": Perm.CATALOG_EDIT}

    @extend_schema(
        tags=TAG,
        parameters=[OpenApiParameter("q", str), OpenApiParameter("status", str, enum=ProductStatus.values)],
        responses={200: ProductSummaryOut(many=True)},
        operation_id="staff_catalog_products",
    )
    def get(self, request: Request) -> Response:
        qs = Product.objects.select_related("category").prefetch_related("translations", "variants")
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(slug__icontains=q) | Q(translations__name__icontains=q) | Q(variants__sku__iexact=q))
        wanted = request.query_params.get("status")
        if wanted in ProductStatus.values:
            qs = qs.filter(status=wanted)
        return Response([product_summary(p) for p in qs.distinct().order_by("-updated_at")[:500]])

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={201: ProductOut}, operation_id="staff_catalog_product_create"
    )
    def post(self, request: Request) -> Response:
        can_price = access.has_perm(self.account, Perm.PRICES_EDIT)
        if can_price and not access.stepped_up(self.session) and request.data.get("base_price") not in (None, "", 0):
            raise ApiProblem(403, "step-up-required", "Confirm with your authenticator code to set a price.")
        product = editing.create_product(_body(request), self.actor(), can_price, request)
        return Response(product_out(product), status=status.HTTP_201_CREATED)


class ProductView(_CatalogView):
    required_permission = {"GET": Perm.CATALOG_VIEW, "PUT": Perm.CATALOG_EDIT}

    @extend_schema(tags=TAG, responses={200: ProductOut}, operation_id="staff_catalog_product")
    def get(self, request: Request, product_id: str) -> Response:
        return Response(product_out(Product.objects.get(pk=product_id)))

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={200: ProductOut}, operation_id="staff_catalog_product_update"
    )
    def put(self, request: Request, product_id: str) -> Response:
        product = Product.objects.get(pk=product_id)
        renaming_live = (
            product.status == ProductStatus.PUBLISHED and request.data.get("slug", product.slug) != product.slug
        )
        if renaming_live and not access.has_perm(self.account, Perm.CATALOG_PUBLISH):
            raise ApiProblem(403, "permission-denied", "Changing a live product's address needs publishing rights.")
        return Response(product_out(editing.update_product(product, _body(request), self.actor(), request)))


class ProductVariantsView(_CatalogView):
    required_permission = Perm.CATALOG_EDIT

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={200: ProductOut}, operation_id="staff_catalog_variants_set"
    )
    def put(self, request: Request, product_id: str) -> Response:
        body = _body(request)
        product = editing.set_variants(
            Product.objects.get(pk=product_id), body.get("colours"), body.get("sizes"), self.actor(), request
        )
        return Response(product_out(product))


class ProductPricesView(_CatalogView):
    required_permission = Perm.PRICES_EDIT
    step_up = True

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={200: ProductOut}, operation_id="staff_catalog_prices_set"
    )
    def put(self, request: Request, product_id: str) -> Response:
        body = _body(request)
        product = editing.set_prices(
            Product.objects.get(pk=product_id), body.get("base_price"), body.get("overrides"), self.actor(), request
        )
        return Response(product_out(product))


class ProductStatusView(_CatalogView):
    required_permission = Perm.CATALOG_PUBLISH

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={200: ProductOut}, operation_id="staff_catalog_status_set"
    )
    def post(self, request: Request, product_id: str) -> Response:
        product = editing.set_status(
            Product.objects.get(pk=product_id), str(_body(request).get("status")), self.actor(), request
        )
        return Response(product_out(product))


class ImportTemplateView(_CatalogView):
    required_permission = Perm.CATALOG_EDIT

    @extend_schema(tags=TAG, responses={(200, "text/csv"): str}, operation_id="staff_catalog_import_template")
    def get(self, request: Request) -> HttpResponse:
        response = HttpResponse(importing.template(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="aurevon-catalogue-template.csv"'
        return response


class ImportView(_CatalogView):
    required_permission = Perm.PRICES_EDIT

    @extend_schema(tags=TAG, request=ImportIn, responses={200: ImportOut}, operation_id="staff_catalog_import")
    def post(self, request: Request) -> Response:
        serializer = ImportIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        apply = serializer.validated_data["apply"]
        if apply and not access.stepped_up(self.session):
            raise ApiProblem(403, "step-up-required", "Confirm with your authenticator code to import prices.")
        report = importing.run(serializer.validated_data["csv"].encode(), self.actor(), apply=apply, request=request)
        return Response(report.__dict__)


class ProductImagesView(_CatalogView):
    """Uploads go through the API so every file is checked and re-encoded before it is stored (MTS §12)."""

    required_permission = Perm.CATALOG_EDIT
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=TAG,
        request={"multipart/form-data": ImageIn},
        responses={201: ProductOut},
        operation_id="staff_catalog_image_add",
    )
    def post(self, request: Request, product_id: str) -> Response:
        serializer = ImageIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        product = Product.objects.get(pk=product_id)
        images.add_image(
            product,
            data["file"].read(),
            data.get("colour", ""),
            data["alt_en"],
            data.get("alt_ur", ""),
            self.actor(),
            request,
        )
        return Response(product_out(product), status=status.HTTP_201_CREATED)


class ProductImageView(_CatalogView):
    required_permission = Perm.CATALOG_EDIT

    @extend_schema(tags=TAG, responses={200: ProductOut}, operation_id="staff_catalog_image_remove")
    def delete(self, request: Request, product_id: str, image_id: str) -> Response:
        image = ProductImage.objects.filter(product_id=product_id, pk=image_id).exclude(url="").first()
        if image is None:
            raise ApiProblem(404, "not-found", "No such image.")
        product = image.product
        images.remove_image(image, self.actor(), request)
        return Response(product_out(product))
