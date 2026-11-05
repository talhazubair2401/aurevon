"""/api/v1/staff/catalog/… (MTS §8 "Staff: catalogue"; decision 0006).

Permissions (decision 0003): `catalog.view` reads; `catalog.edit` creates and edits products, variants,
categories and colours; `catalog.publish` publishes and archives; `prices.edit` sets prices and imports (prices
come from the file), and every price change asks for the authenticator code again (decision 0003, 2.5)."""

from typing import Any

from django.conf import settings
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

from .. import editing, images, importing, threed
from ..models import Category, Colour, Product, ProductImage, ProductStatus, ThreeDAsset, ThreeDStatus

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


class Model3DOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=ThreeDStatus.values)
    file_name = serializers.CharField()
    colours = serializers.ListField(child=serializers.CharField())
    variants = serializers.ListField(child=serializers.CharField())
    variant_map = serializers.DictField(child=serializers.CharField(allow_blank=True))
    compression = serializers.CharField(allow_blank=True)
    bytes = serializers.IntegerField(allow_null=True)
    triangles = serializers.IntegerField(allow_null=True)
    max_texture_px = serializers.IntegerField(allow_null=True)
    est_gpu_mb = serializers.CharField(allow_null=True)
    report = serializers.JSONField()
    preview_url = serializers.CharField(allow_null=True)
    url = serializers.CharField(allow_blank=True)
    uploaded_by = serializers.CharField(allow_blank=True)
    approved_by = serializers.CharField(allow_blank=True)
    approved_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class Model3DIn(serializers.Serializer[Any]):
    file = serializers.FileField()


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
    models3d = Model3DOut(many=True)
    shoppers_see_3d = serializers.BooleanField()
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
        "models3d": [model3d_out(a) for a in p.models3d.exclude(status=ThreeDStatus.RETIRED)],
        "shoppers_see_3d": settings.THREED_FOR_SHOPPERS,
        "updated_at": p.updated_at,
    }


def model3d_out(a: ThreeDAsset) -> dict[str, Any]:
    has_file = a.status in (ThreeDStatus.DRAFT, ThreeDStatus.APPROVED)
    return {
        "id": a.pk,
        "status": a.status,
        "file_name": a.file_name,
        "colours": a.colours,
        "variants": a.variants,
        "variant_map": a.variant_map,
        "compression": a.compression,
        "bytes": a.bytes,
        "triangles": a.triangles,
        "max_texture_px": a.max_texture_px,
        "est_gpu_mb": None if a.est_gpu_mb is None else str(a.est_gpu_mb),
        "report": a.report,
        "preview_url": threed.preview_url(a) if has_file else None,
        "url": a.url,
        "uploaded_by": a.uploaded_by,
        "approved_by": a.approved_by,
        "approved_at": a.approved_at,
        "created_at": a.created_at,
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


class Models3DView(_CatalogView):
    """Upload a garment model (decision 0007). Processing runs in the background; the editor polls."""

    required_permission = Perm.CATALOG_EDIT
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=TAG,
        request={"multipart/form-data": Model3DIn},
        responses={201: ProductOut},
        operation_id="staff_catalog_3d_upload",
    )
    def post(self, request: Request, product_id: str) -> Response:
        serializer = Model3DIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        if upload.size > threed.MAX_BYTES:
            raise editing.CatalogError("The file is larger than 100 MB.")
        product = Product.objects.get(pk=product_id)
        threed.upload(product, upload.name, upload.read(), self.actor(), request)
        return Response(product_out(product), status=status.HTTP_201_CREATED)


def _asset(product_id: str, asset_id: str) -> ThreeDAsset:
    asset = ThreeDAsset.objects.filter(product_id=product_id, pk=asset_id).select_related("product").first()
    if asset is None:
        raise ApiProblem(404, "not-found", "No such model.")
    return asset


class Model3DColoursView(_CatalogView):
    required_permission = Perm.CATALOG_EDIT

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={200: ProductOut}, operation_id="staff_catalog_3d_colours"
    )
    def put(self, request: Request, product_id: str, asset_id: str) -> Response:
        asset = threed.set_colours(_asset(product_id, asset_id), _body(request).get("colours"), self.actor(), request)
        return Response(product_out(asset.product))


class Model3DApproveView(_CatalogView):
    required_permission = Perm.CATALOG_PUBLISH

    @extend_schema(
        tags=TAG, request=OpenApiTypes.OBJECT, responses={200: ProductOut}, operation_id="staff_catalog_3d_approve"
    )
    def post(self, request: Request, product_id: str, asset_id: str) -> Response:
        asset = threed.approve(
            _asset(product_id, asset_id), _body(request).get("checked") is True, self.actor(), request
        )
        return Response(product_out(asset.product))


class Model3DRetireView(_CatalogView):
    required_permission = Perm.CATALOG_PUBLISH

    @extend_schema(tags=TAG, request=None, responses={200: ProductOut}, operation_id="staff_catalog_3d_retire")
    def post(self, request: Request, product_id: str, asset_id: str) -> Response:
        asset = threed.retire(_asset(product_id, asset_id), self.actor(), request)
        return Response(product_out(asset.product))


class Model3DFileView(_CatalogView):
    """Draft preview for staff: a short-lived signed link, plus the staff session (never public /media/)."""

    required_permission = Perm.CATALOG_VIEW

    @extend_schema(
        tags=TAG,
        responses={(200, "model/gltf-binary"): bytes},
        operation_id="staff_catalog_3d_file",
        parameters=[OpenApiParameter("expires", str), OpenApiParameter("sig", str)],
    )
    def get(self, request: Request, asset_id: str) -> HttpResponse:
        if not threed.preview_allowed(
            asset_id, request.query_params.get("expires", ""), request.query_params.get("sig", "")
        ):
            raise ApiProblem(403, "link-expired", "This preview link has expired. Reload the page.")
        asset = ThreeDAsset.objects.filter(pk=asset_id).first()
        if asset is None:
            raise ApiProblem(404, "not-found", "No such model.")
        response = HttpResponse(threed.preview_bytes(asset), content_type="model/gltf-binary")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
