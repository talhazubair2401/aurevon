"""Returns and exchanges (MTS §8, §11; M12).

Customer: /orders/<number>/returns — whoever can open the order (its account, or the guest's order cookie) can see
what is returnable and request a return or exchange, and cancel a request staff haven't decided yet.

Staff: /staff/returns — `returns.view` reads; `returns.decide` approves, rejects, receives, inspects and completes.
Completing a refund return raises a refund request, so it also needs `refunds.request` and the authenticator code
again (decision 0003, 2.5); the refund itself is then approved under the normal rules.
"""

from decimal import Decimal
from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor
from apps.cart.api.views import CartAPIView
from apps.catalog.models import ProductStatus, ProductVariant
from apps.inventory import selectors as stock
from apps.orders.api.views import find_order
from common.exceptions import ApiProblem

from .. import services
from ..models import ReturnKind, ReturnRequest, ReturnStatus

TAG = ["returns"]
STAFF_TAG = ["staff returns"]


class ReturnItemOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    quantity = serializers.IntegerField()
    exchange_sku = serializers.CharField()
    exchange_label = serializers.CharField()
    outcome = serializers.CharField()
    inspection_note = serializers.CharField()


class ReturnOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    number = serializers.CharField()
    order = serializers.CharField()
    kind = serializers.ChoiceField(choices=ReturnKind.values)
    status = serializers.ChoiceField(choices=ReturnStatus.values)
    reason = serializers.CharField()
    reason_label = serializers.CharField()
    details = serializers.CharField()
    decision_note = serializers.CharField()
    refund_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    exchange_order = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    items = ReturnItemOut(many=True)


def _variant_label(sku: str) -> str:
    v = ProductVariant.objects.select_related("colour").filter(sku=sku).first()
    return f"{v.size} · {v.colour.name_en}" if v else sku


def return_out(r: ReturnRequest) -> dict[str, Any]:
    return dict(
        ReturnOut(
            {
                "id": r.pk,
                "number": r.number,
                "order": r.order.number,
                "kind": r.kind,
                "status": r.status,
                "reason": r.reason,
                "reason_label": services.REASONS.get(r.reason, r.reason),
                "details": r.details,
                "decision_note": r.decision_note,
                "refund_amount": r.refund_amount,
                "exchange_order": r.exchange_order.number if r.exchange_order else None,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "items": [
                    {
                        "id": i.pk,
                        "sku": i.order_item.sku,
                        "name": i.order_item.name,
                        "size": i.order_item.size,
                        "colour": i.order_item.colour,
                        "quantity": i.quantity,
                        "exchange_sku": i.exchange_sku,
                        "exchange_label": _variant_label(i.exchange_sku) if i.exchange_sku else "",
                        "outcome": i.outcome,
                        "inspection_note": i.inspection_note,
                    }
                    for i in r.items.select_related("order_item")
                ],
            }
        ).data
    )


# --- Customer --------------------------------------------------------------------------------------------------


class ExchangeOptionOut(serializers.Serializer[Any]):
    sku = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    in_stock = serializers.BooleanField()


class ReturnableItemOut(serializers.Serializer[Any]):
    sku = serializers.CharField()
    name = serializers.CharField()
    size = serializers.CharField()
    colour = serializers.CharField()
    image_url = serializers.CharField()
    quantity = serializers.IntegerField()
    available = serializers.IntegerField()
    exchange_options = ExchangeOptionOut(many=True)


class ReasonOut(serializers.Serializer[Any]):
    code = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]


class OrderReturnsOut(serializers.Serializer[Any]):
    can_return = serializers.BooleanField()
    window_days = serializers.IntegerField()
    return_by = serializers.DateTimeField(allow_null=True)
    reasons = ReasonOut(many=True)
    items = ReturnableItemOut(many=True)
    requests = ReturnOut(many=True)


class ReturnLineIn(serializers.Serializer[Any]):
    sku = serializers.CharField(max_length=40)
    quantity = serializers.IntegerField(min_value=1, max_value=100)
    exchange_sku = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")


class ReturnRequestIn(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=ReturnKind.values)
    reason = serializers.ChoiceField(choices=list(services.REASONS))
    details = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    lines = ReturnLineIn(many=True)


def _exchange_options(product_slug: str, current_sku: str) -> list[dict[str, Any]]:
    variants = list(
        ProductVariant.objects.select_related("colour")
        .filter(product__slug=product_slug, is_active=True, product__status=ProductStatus.PUBLISHED)
        .exclude(sku=current_sku)
        .order_by("colour__name_en", "position", "size")
    )
    avail = stock.available([v.pk for v in variants])
    return [
        {"sku": v.sku, "size": v.size, "colour": v.colour.name_en, "in_stock": avail.get(v.pk, 0) > 0} for v in variants
    ]


def order_returns(order: Any) -> dict[str, Any]:
    can = services.returnable(order)
    return dict(
        OrderReturnsOut(
            {
                "can_return": can,
                "window_days": services.window_days(),
                "return_by": services.return_by(order),
                "reasons": [{"code": k, "label": v} for k, v in services.REASONS.items()],
                "items": [
                    {
                        "sku": i.sku,
                        "name": i.name,
                        "size": i.size,
                        "colour": i.colour,
                        "image_url": i.image_url,
                        "quantity": i.quantity,
                        "available": services.available_to_return(i) if can else 0,
                        "exchange_options": _exchange_options(i.product_slug, i.sku) if can else [],
                    }
                    for i in order.items.all()
                ],
                "requests": [return_out(r) for r in order.returns.all()],
            }
        ).data
    )


def _who(view: CartAPIView, order: Any) -> str:
    return view.customer.email if view.customer is not None else f"guest {order.email}"


class OrderReturnsView(CartAPIView):
    @extend_schema(tags=TAG, responses={200: OrderReturnsOut}, operation_id="order_returns")
    def get(self, request: Request, number: str) -> Response:
        return Response(order_returns(find_order(request, number)))

    @extend_schema(
        tags=TAG, request=ReturnRequestIn, responses={201: OrderReturnsOut}, operation_id="order_return_create"
    )
    def post(self, request: Request, number: str) -> Response:
        order = find_order(request, number)
        s = ReturnRequestIn(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        services.create(
            order.pk, d["kind"], d["reason"], d["details"], [dict(x) for x in d["lines"]], _who(self, order)
        )
        order.refresh_from_db()
        return Response(order_returns(order), status=201)


class OrderReturnCancelView(CartAPIView):
    @extend_schema(tags=TAG, request=None, responses={200: OrderReturnsOut}, operation_id="order_return_cancel")
    def post(self, request: Request, number: str, return_number: str) -> Response:
        order = find_order(request, number)
        r = ReturnRequest.objects.filter(order=order, number=return_number).first()
        if r is None:
            raise ApiProblem(404, "not-found", "No such return.")
        services.cancel_by_customer(r.pk, _who(self, order))
        return Response(order_returns(order))


# --- Staff -----------------------------------------------------------------------------------------------------


class _ReturnsView(StaffAPIView):
    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)


class StaffReturnRowOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    number = serializers.CharField()
    order = serializers.CharField()
    customer = serializers.CharField()
    kind = serializers.CharField()
    status = serializers.CharField()
    reason_label = serializers.CharField()
    units = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class StaffReturnListOut(serializers.Serializer[Any]):
    results = StaffReturnRowOut(many=True)
    counts = serializers.DictField(child=serializers.IntegerField())


class StaffReturnOut(ReturnOut):
    customer_email = serializers.CharField()
    customer_name = serializers.CharField()
    suggested_refund = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    can_complete_refund = serializers.BooleanField()


class ReturnsView(_ReturnsView):
    required_permission = Perm.RETURNS_VIEW

    @extend_schema(
        tags=STAFF_TAG,
        parameters=[OpenApiParameter("status", OpenApiTypes.STR)],
        responses={200: StaffReturnListOut},
        operation_id="staff_returns",
    )
    def get(self, request: Request) -> Response:
        qs = ReturnRequest.objects.select_related("order").prefetch_related("items")
        status = request.query_params.get("status", "")
        counts = {s: qs.filter(status=s).count() for s in ReturnStatus.values}
        if status:
            qs = qs.filter(status=status)
        rows = [
            {
                "id": r.pk,
                "number": r.number,
                "order": r.order.number,
                "customer": r.order.shipping_address.get("full_name", "") or r.order.email,
                "kind": r.kind,
                "status": r.status,
                "reason_label": services.REASONS.get(r.reason, r.reason),
                "units": sum(i.quantity for i in r.items.all()),
                "created_at": r.created_at,
            }
            for r in qs[:200]
        ]
        return Response({"results": rows, "counts": counts})


def staff_return(view: _ReturnsView, r: ReturnRequest) -> dict[str, Any]:
    data = {
        **return_out(r),
        "customer_email": r.order.email,
        "customer_name": r.order.shipping_address.get("full_name", ""),
        "suggested_refund": services.suggested_refund(r)
        if r.kind == ReturnKind.REFUND and r.status in (ReturnStatus.INSPECTED, ReturnStatus.RECEIVED)
        else None,
        "can_complete_refund": access.has_perm(view.account, Perm.REFUNDS_REQUEST),
    }
    return dict(StaffReturnOut(data).data)


def _get(return_id: str) -> ReturnRequest:
    r = ReturnRequest.objects.select_related("order", "exchange_order").filter(pk=return_id).first()
    if r is None:
        raise ApiProblem(404, "not-found", "No such return.")
    return r


class ReturnView(_ReturnsView):
    required_permission = Perm.RETURNS_VIEW

    @extend_schema(tags=STAFF_TAG, responses={200: StaffReturnOut}, operation_id="staff_return")
    def get(self, request: Request, return_id: str) -> Response:
        return Response(staff_return(self, _get(return_id)))


class ReturnActionIn(serializers.Serializer[Any]):
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    outcomes = serializers.DictField(
        child=serializers.DictField(child=serializers.CharField(allow_blank=True)), required=False
    )
    refund_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True
    )


class ReturnActionView(_ReturnsView):
    """approve | reject | receive | inspect | complete."""

    required_permission = Perm.RETURNS_DECIDE

    @extend_schema(
        tags=STAFF_TAG, request=ReturnActionIn, responses={200: StaffReturnOut}, operation_id="staff_return_action"
    )
    def post(self, request: Request, return_id: str, action: str) -> Response:
        r = _get(return_id)
        s = ReturnActionIn(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        actor = self.actor()
        if action in ("approve", "reject"):
            services.decide(r.pk, action == "approve", d["note"], actor, request)
        elif action == "receive":
            services.receive(r.pk, actor, request)
        elif action == "inspect":
            services.inspect(r.pk, d.get("outcomes") or {}, actor, request)
        elif action == "complete":
            if r.kind == ReturnKind.REFUND:
                if not access.has_perm(self.account, Perm.REFUNDS_REQUEST):
                    raise ApiProblem(
                        403, "forbidden", "Completing a refund return needs permission to request refunds."
                    )
                if not access.stepped_up(self.session):
                    raise ApiProblem(403, "step-up-required", "Confirm it's you with your authenticator code.")
            services.complete(r.pk, actor, amount=d.get("refund_amount"), request=request)
        else:
            raise ApiProblem(404, "not-found", "Unknown action.")
        return Response(staff_return(self, _get(return_id)))
