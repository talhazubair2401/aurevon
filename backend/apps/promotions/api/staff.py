"""/api/v1/staff/coupons, /promotions (MTS §8 "Staff: promotions"; M11).

`promotions.edit` (decision 0003: Owner, Store Admin, Content & Marketing) creates, schedules, edits and switches off
coupon codes and automatic promotions. Usage is shown as totals only (uses, discount given, order value), so the
screen shows no customer details to roles without `orders.view`. Discounts never stack (provisional setting): the
larger of the best promotion and the coupon applies. Every change is audited.
"""

from decimal import Decimal
from typing import Any

from django.db.models import Count, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.audit.services import Actor, record
from apps.catalog.models import Category
from common.exceptions import ApiProblem

from ..models import Coupon, DiscountKind, Promotion

TAG = ["staff promotions"]
ZERO = Decimal("0.00")


class _PromoView(StaffAPIView):
    required_permission = Perm.PROMOTIONS_EDIT

    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)


def state(d: Coupon | Promotion) -> str:
    now = timezone.now()
    if not d.is_active:
        return "off"
    if d.ends_at is not None and d.ends_at <= now:
        return "ended"
    if d.starts_at is not None and d.starts_at > now:
        return "scheduled"
    if isinstance(d, Coupon) and d.usage_limit is not None and d.times_used >= d.usage_limit:
        return "used_up"
    return "live"


class _DiscountIn(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=DiscountKind.values)
    value = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    max_discount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True
    )
    min_subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, default=ZERO
    )
    categories = serializers.ListField(child=serializers.SlugField(), required=False, default=list)
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)


class StaffCouponIn(_DiscountIn):
    code = serializers.RegexField(r"^[A-Za-z0-9_-]{3,40}$", max_length=40)
    description = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    usage_limit = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    per_customer_limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=1)


class PromotionIn(_DiscountIn):
    name = serializers.CharField(max_length=80)
    label_en = serializers.CharField(max_length=80)
    label_ur = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


def _check(data: dict[str, Any]) -> dict[str, Any]:
    if data["kind"] == DiscountKind.PERCENT and data["value"] > 90:
        raise ApiProblem(400, "value", "A percentage discount can be at most 90%.")
    start, end = data.get("starts_at"), data.get("ends_at")
    if start and end and end <= start:
        raise ApiProblem(400, "ends_at", "The end has to be after the start.")
    slugs = sorted(set(data["categories"]))
    known = set(Category.objects.filter(slug__in=slugs).values_list("slug", flat=True))
    unknown = [s for s in slugs if s not in known]
    if unknown:
        raise ApiProblem(400, "categories", f"No category called “{unknown[0]}”.")
    data["categories"] = slugs
    return data


def _common(d: Coupon | Promotion) -> dict[str, Any]:
    return {
        "id": d.pk,
        "kind": d.kind,
        "value": d.value,
        "max_discount": d.max_discount,
        "min_subtotal": d.min_subtotal,
        "categories": d.categories,
        "starts_at": d.starts_at,
        "ends_at": d.ends_at,
        "is_active": d.is_active,
        "state": state(d),
        "created_by": d.created_by,
        "created_at": d.created_at,
    }


def _audit_shape(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v if isinstance(v, (bool, list, type(None))) else str(v) for k, v in value.items()}


# --- Coupons -------------------------------------------------------------------------------------------------


class CouponOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    code = serializers.CharField()
    description = serializers.CharField()
    kind = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_discount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    min_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    categories = serializers.ListField(child=serializers.CharField())
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    is_active = serializers.BooleanField()
    state = serializers.CharField()
    usage_limit = serializers.IntegerField(allow_null=True)
    per_customer_limit = serializers.IntegerField()
    times_used = serializers.IntegerField()
    discount_given = serializers.DecimalField(max_digits=14, decimal_places=2)
    order_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    created_by = serializers.CharField()
    created_at = serializers.DateTimeField()


def coupon_out(c: Coupon) -> dict[str, Any]:
    totals = c.redemptions.aggregate(discount=Sum("amount"), value=Sum("order__total"), n=Count("id"))
    return dict(
        CouponOut(
            {
                **_common(c),
                "code": c.code,
                "description": c.description,
                "usage_limit": c.usage_limit,
                "per_customer_limit": c.per_customer_limit,
                "times_used": c.times_used,
                "discount_given": totals["discount"] or ZERO,
                "order_value": totals["value"] or ZERO,
            }
        ).data
    )


def _save_coupon(coupon: Coupon | None, request: Request, actor: Actor) -> Coupon:
    data = _check(dict(_valid(StaffCouponIn(data=request.data))))
    code = data.pop("code").upper()
    clash = Coupon.objects.filter(code=code)
    if coupon is not None:
        clash = clash.exclude(pk=coupon.pk)
        if coupon.code != code and coupon.times_used > 0:
            raise ApiProblem(400, "code", "This code has been used, so it can't be renamed. Create a new one.")
        if data.get("usage_limit") is not None and data["usage_limit"] < coupon.times_used:
            raise ApiProblem(400, "usage_limit", f"It has already been used {coupon.times_used} times.")
    if clash.exists():
        raise ApiProblem(400, "code", "Another coupon already uses that code.")
    before = _audit_shape(coupon_out(coupon)) if coupon else None
    if coupon is None:
        coupon = Coupon(created_by=actor.label)
    coupon.code = code
    for key, value in data.items():
        setattr(coupon, key, value)
    coupon.description = coupon.description.strip()
    coupon.save()
    record(
        "coupon.save",
        actor,
        target_type="coupon",
        target_id=coupon.pk,
        before=before,
        after=_audit_shape({"code": code, **data}),
        request=request,
    )
    return coupon


def _valid(serializer: serializers.Serializer[Any]) -> dict[str, Any]:
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class CouponsView(_PromoView):
    @extend_schema(tags=TAG, operation_id="staff_coupons", responses={200: CouponOut(many=True)})
    def get(self, request: Request) -> Response:
        return Response([coupon_out(c) for c in Coupon.objects.all()])

    @extend_schema(tags=TAG, operation_id="staff_coupon_create", request=StaffCouponIn, responses={201: CouponOut})
    def post(self, request: Request) -> Response:
        return Response(coupon_out(_save_coupon(None, request, self.actor())), status=201)


class CouponView(_PromoView):
    @extend_schema(tags=TAG, operation_id="staff_coupon_update", request=StaffCouponIn, responses={200: CouponOut})
    def put(self, request: Request, coupon_id: str) -> Response:
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if coupon is None:
            raise ApiProblem(404, "not-found", "No such coupon.")
        return Response(coupon_out(_save_coupon(coupon, request, self.actor())))


# --- Automatic promotions ------------------------------------------------------------------------------------


class PromotionOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    label_en = serializers.CharField()
    label_ur = serializers.CharField()
    kind = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_discount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    min_subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    categories = serializers.ListField(child=serializers.CharField())
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    is_active = serializers.BooleanField()
    state = serializers.CharField()
    created_by = serializers.CharField()
    created_at = serializers.DateTimeField()


def promotion_out(p: Promotion) -> dict[str, Any]:
    return dict(PromotionOut({**_common(p), "name": p.name, "label_en": p.label_en, "label_ur": p.label_ur}).data)


def _save_promotion(promo: Promotion | None, request: Request, actor: Actor) -> Promotion:
    data = _check(dict(_valid(PromotionIn(data=request.data))))
    if data.get("starts_at") is None or data.get("ends_at") is None:
        raise ApiProblem(400, "ends_at", "An automatic promotion needs a start and an end, so it can't run forever.")
    before = _audit_shape(promotion_out(promo)) if promo else None
    if promo is None:
        promo = Promotion(created_by=actor.label)
    for key, value in data.items():
        setattr(promo, key, value.strip() if isinstance(value, str) else value)
    promo.save()
    record(
        "promotion.save",
        actor,
        target_type="promotion",
        target_id=promo.pk,
        before=before,
        after=_audit_shape(data),
        request=request,
    )
    return promo


class PromotionsView(_PromoView):
    @extend_schema(tags=TAG, operation_id="staff_promotions", responses={200: PromotionOut(many=True)})
    def get(self, request: Request) -> Response:
        return Response([promotion_out(p) for p in Promotion.objects.all()])

    @extend_schema(tags=TAG, operation_id="staff_promotion_create", request=PromotionIn, responses={201: PromotionOut})
    def post(self, request: Request) -> Response:
        return Response(promotion_out(_save_promotion(None, request, self.actor())), status=201)


class PromotionView(_PromoView):
    @extend_schema(tags=TAG, operation_id="staff_promotion_update", request=PromotionIn, responses={200: PromotionOut})
    def put(self, request: Request, promotion_id: str) -> Response:
        promo = Promotion.objects.filter(pk=promotion_id).first()
        if promo is None:
            raise ApiProblem(404, "not-found", "No such promotion.")
        return Response(promotion_out(_save_promotion(promo, request, self.actor())))
