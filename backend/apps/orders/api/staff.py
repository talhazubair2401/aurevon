"""/api/v1/staff/orders, /refunds, /shipments, /alerts (MTS §8 "Staff: orders and payments").

Permissions (decision 0003): `orders.view` reads; `orders.update` moves orders (packing, dispatch, tracking,
delivered, cancel); `remittance.reconcile` records cash-on-delivery money; `refunds.request` asks for a refund;
`refunds.approve` approves, rejects, completes manual refunds and settles payment reviews. Requesting and approving
refunds asks for the authenticator code again (decision 0003, 2.5). Every change is audited by the services.
"""

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor, record
from apps.notifications.models import StaffAlert
from apps.payments import services as payments
from apps.payments.models import Payment, Refund, RefundState
from apps.shipping import services as shipping
from apps.shipping.models import Shipment, ShipmentStatus
from common.exceptions import ApiProblem
from integrations import couriers

from .. import services as orders
from ..models import Order, OrderStatus, PaymentMethod, PaymentStatus
from .views import order_payload

TAG = ["staff orders"]
PAGE = 50


def _actor(view: StaffAPIView) -> Actor:
    return Actor(view.account.pk, view.account.email)


def _body(request: Request) -> dict[str, Any]:
    if not isinstance(request.data, dict):
        raise ApiProblem(400, "invalid", "Send a JSON object.")
    return dict(request.data)


def _text(data: dict[str, Any], key: str, limit: int, *, required: str = "") -> str:
    value = data.get(key, "")
    value = value.strip() if isinstance(value, str) else ""
    if required and not value:
        raise ApiProblem(400, key, required)
    return value[:limit]


def _order(number: str) -> Order:
    order = Order.objects.filter(number=number).first()
    if order is None:
        raise ApiProblem(404, "not-found", "No such order.")
    return order


def _amount(value: Any, label: str = "amount") -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ApiProblem(400, label, "Enter an amount in PKR.") from None
    if amount <= 0:
        raise ApiProblem(400, label, "Enter an amount above zero.")
    return amount


# --- Serialisers (response shapes) ---------------------------------------------------------------------------


class OrderRowOut(serializers.Serializer[Any]):
    number = serializers.CharField()
    placed_at = serializers.DateTimeField()
    customer = serializers.CharField()
    email = serializers.CharField()
    city = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    payment_method = serializers.CharField()
    total = serializers.CharField()
    items = serializers.IntegerField()


class OrderListOut(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    results = OrderRowOut(many=True)
    counts = serializers.DictField(child=serializers.IntegerField())


class StaffOrderOut(serializers.Serializer[Any]):
    order = serializers.JSONField()
    account_email = serializers.CharField(allow_null=True)
    history = serializers.JSONField()
    payments = serializers.JSONField()
    refunds = serializers.JSONField()
    shipments = serializers.JSONField()
    alerts = serializers.JSONField()
    next_statuses = serializers.ListField(child=serializers.CharField())
    can_cancel = serializers.BooleanField()
    can_dispatch = serializers.BooleanField()
    cod_actions = serializers.ListField(child=serializers.CharField())
    refundable = serializers.CharField()
    returns = serializers.JSONField()


class RefundRowOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    order = serializers.CharField()
    amount = serializers.CharField()
    reason = serializers.CharField()
    state = serializers.CharField()
    source = serializers.CharField()  # type: ignore[assignment]
    requested_by = serializers.CharField()
    approved_by = serializers.CharField()
    second_approved_by = serializers.CharField()
    decision_note = serializers.CharField()
    manual_reference = serializers.CharField()
    last_error = serializers.CharField()
    attempts = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


class AlertOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    severity = serializers.CharField()
    message = serializers.CharField()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    created_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    resolved_by = serializers.CharField()


class CourierOut(serializers.Serializer[Any]):
    code = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    books_automatically = serializers.BooleanField()


# --- Presenters ----------------------------------------------------------------------------------------------


def _row(o: Order) -> dict[str, Any]:
    address = o.shipping_address or {}
    return {
        "number": o.number,
        "placed_at": o.placed_at,
        "customer": str(address.get("name", "")),
        "email": o.email,
        "city": str(address.get("city", "")),
        "status": o.status,
        "payment_status": o.payment_status,
        "payment_method": o.payment_method,
        "total": f"{o.total:.2f}",
        "items": sum(i.quantity for i in o.items.all()),
    }


def refund_out(r: Refund) -> dict[str, Any]:
    return {
        "id": r.pk,
        "order": r.order.number,
        "amount": f"{r.amount:.2f}",
        "reason": r.reason,
        "state": r.state,
        "source": r.source,
        "requested_by": r.requested_by,
        "approved_by": r.approved_by,
        "second_approved_by": r.second_approved_by,
        "decision_note": r.decision_note,
        "manual_reference": r.manual_reference,
        "last_error": r.last_error,
        "attempts": r.attempts,
        "created_at": r.created_at,
        "completed_at": r.completed_at,
    }


def alert_out(a: StaffAlert) -> dict[str, Any]:
    return {
        "id": a.pk,
        "kind": a.kind,
        "severity": a.severity,
        "message": a.message,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "created_at": a.created_at,
        "resolved_at": a.resolved_at,
        "resolved_by": a.resolved_by,
    }


def staff_order(order: Order) -> dict[str, Any]:
    order = (
        Order.objects.select_related("account")
        .prefetch_related("items", "history", "shipments__events", "payments", "refunds")
        .get(pk=order.pk)
    )
    _, refundable = payments._refundable(order)
    cod_actions: list[str] = []
    if order.payment_method == PaymentMethod.COD:
        if order.payment_status == PaymentStatus.COD_REMITTANCE_PENDING:
            cod_actions.append("received")
        if PaymentStatus.COD_RECONCILED in orders.COD_NEXT.get(order.payment_status, set()):
            cod_actions.append("reconciled")
    nxt_status = sorted(
        s
        for s in orders.TRANSITIONS[order.status]
        if s not in (OrderStatus.DISPATCHED, OrderStatus.CANCELLED)
        and not (s == OrderStatus.CONFIRMED and order.status == OrderStatus.AWAITING_PAYMENT)
    )
    from apps.returns.models import ReturnRequest

    return {
        "order": order_payload(order),
        "account_email": order.account.email if order.account else None,
        "history": [
            {
                "kind": h.kind,
                "from": h.from_status,
                "to": h.to_status,
                "actor": h.actor_label,
                "reason": h.reason,
                "at": h.created_at,
            }
            for h in order.history.all()
        ],
        "payments": [
            {
                "id": str(p.pk),
                "provider": p.provider,
                "state": p.state,
                "amount": f"{p.amount:.2f}",
                "provider_ref": p.provider_ref,
                "failure_reason": p.failure_reason,
                "needs_review": p.needs_review,
                "review_note": p.review_note,
                "refunded_amount": f"{p.refunded_amount:.2f}",
                "created_at": p.created_at.isoformat(),
                "succeeded_at": p.succeeded_at.isoformat() if p.succeeded_at else None,
            }
            for p in order.payments.all()
        ],
        "refunds": [refund_out(r) for r in order.refunds.all()],
        "shipments": [
            {
                "id": str(s.pk),
                "courier": s.courier,
                "tracking_number": s.tracking_number,
                "tracking_url": s.tracking_url,
                "status": s.status,
                "cod_amount": f"{s.cod_amount:.2f}",
                "booked_at": s.booked_at.isoformat(),
                "next": sorted(shipping.SHIPMENT_NEXT[s.status]),
                "events": [
                    {
                        "status": e.status,
                        "description": e.description,
                        "location": e.location,
                        "at": e.occurred_at.isoformat(),
                        "source": e.source,
                    }
                    for e in s.events.all()
                ],
            }
            for s in order.shipments.all()
        ],
        "alerts": [
            alert_out(a)
            for a in StaffAlert.objects.filter(target_type="order", target_id=order.number, resolved_at__isnull=True)
        ],
        "next_statuses": nxt_status,
        "can_cancel": order.status in orders.BEFORE_DISPATCH,
        "can_dispatch": order.status == OrderStatus.PACKING,
        "cod_actions": cod_actions,
        "refundable": f"{refundable:.2f}",
        "returns": [
            {"id": str(r.pk), "number": r.number, "kind": r.kind, "status": r.status}
            for r in ReturnRequest.objects.filter(order=order)
        ],
    }


# --- Orders --------------------------------------------------------------------------------------------------


class OrdersView(StaffAPIView):
    required_permission = Perm.ORDERS_VIEW

    @extend_schema(
        tags=TAG,
        operation_id="staff_orders",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("payment_status", str),
            OpenApiParameter("payment_method", str),
            OpenApiParameter("q", str),
            OpenApiParameter("date_from", OpenApiTypes.DATE),
            OpenApiParameter("date_to", OpenApiTypes.DATE),
            OpenApiParameter("offset", int),
        ],
        responses={200: OrderListOut},
    )
    def get(self, request: Request) -> Response:
        qs = Order.objects.prefetch_related("items")
        p = request.query_params
        if p.get("status") in OrderStatus.values:
            qs = qs.filter(status=p["status"])
        if p.get("payment_status") in PaymentStatus.values:
            qs = qs.filter(payment_status=p["payment_status"])
        if p.get("payment_method") in PaymentMethod.values:
            qs = qs.filter(payment_method=p["payment_method"])
        q = (p.get("q") or "").strip()[:80]
        if q:
            qs = qs.filter(
                Q(number__iexact=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(shipping_address__name__icontains=q)
                | Q(shipments__tracking_number__iexact=q)
            ).distinct()
        for key, op in (("date_from", "gte"), ("date_to", "lte")):
            raw = p.get(key)
            if raw:
                try:
                    day = datetime.strptime(raw, "%Y-%m-%d").date()
                except ValueError:
                    raise ApiProblem(400, key, "Use a date such as 2026-11-10.") from None
                edge = time.min if op == "gte" else time.max
                qs = qs.filter(**{f"placed_at__{op}": timezone.make_aware(datetime.combine(day, edge))})
        try:
            offset = max(int(p.get("offset", "0")), 0)
        except ValueError:
            offset = 0
        counts = {s: Order.objects.filter(status=s).count() for s in OrderStatus.values}
        return Response(
            {"count": qs.count(), "results": [_row(o) for o in qs[offset : offset + PAGE]], "counts": counts}
        )


class OrderView(StaffAPIView):
    required_permission = Perm.ORDERS_VIEW

    @extend_schema(tags=TAG, operation_id="staff_order", responses={200: StaffOrderOut})
    def get(self, request: Request, number: str) -> Response:
        return Response(staff_order(_order(number)))


class OrderStatusView(StaffAPIView):
    """Packing, back to confirmed, delivered, undelivered or returned. Dispatch and cancel have their own actions."""

    required_permission = Perm.ORDERS_UPDATE

    @extend_schema(
        tags=TAG, operation_id="staff_order_status", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, number: str) -> Response:
        data = _body(request)
        to = data.get("to")
        if to not in OrderStatus.values:
            raise ApiProblem(400, "to", "Choose the new status.")
        order = orders.advance(_order(number).pk, str(to), _actor(self), _text(data, "reason", 200), request)
        return Response(staff_order(order))


class OrderCancelView(StaffAPIView):
    required_permission = Perm.ORDERS_UPDATE

    @extend_schema(
        tags=TAG, operation_id="staff_order_cancel", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, number: str) -> Response:
        reason = _text(_body(request), "reason", 200, required="Say why the order is cancelled.")
        orders.cancel(_order(number).pk, _actor(self), reason, request)
        return Response(staff_order(_order(number)))


class OrderDispatchView(StaffAPIView):
    required_permission = Perm.ORDERS_UPDATE

    @extend_schema(
        tags=TAG, operation_id="staff_order_dispatch", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, number: str) -> Response:
        data = _body(request)
        shipping.dispatch(
            _order(number).pk,
            _text(data, "courier", 30) or "manual",
            _text(data, "tracking_number", 60),
            _text(data, "tracking_url", 200),
            _actor(self),
            request,
        )
        return Response(staff_order(_order(number)))


class OrderCodView(StaffAPIView):
    required_permission = Perm.REMITTANCE_RECONCILE

    @extend_schema(
        tags=TAG, operation_id="staff_order_cod", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, number: str) -> Response:
        data = _body(request)
        orders.cod_remittance(
            _order(number).pk,
            str(data.get("action", "")),
            _actor(self),
            amount=data.get("amount"),
            reference=_text(data, "reference", 60),
            note=_text(data, "note", 200),
            request=request,
        )
        return Response(staff_order(_order(number)))


class OrderRefundsView(StaffAPIView):
    required_permission = Perm.REFUNDS_REQUEST
    step_up = True

    @extend_schema(
        tags=TAG, operation_id="staff_order_refund", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, number: str) -> Response:
        data = _body(request)
        payments.request_refund(
            _order(number),
            _amount(data.get("amount")),
            _text(data, "reason", 300, required="Say why the customer is refunded."),
            _actor(self),
            request=request,
        )
        return Response(staff_order(_order(number)))


class ShipmentEventsView(StaffAPIView):
    required_permission = Perm.ORDERS_UPDATE

    @extend_schema(
        tags=TAG, operation_id="staff_shipment_event", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, shipment_id: str) -> Response:
        data = _body(request)
        shipment = Shipment.objects.filter(pk=shipment_id).select_related("order").first()
        if shipment is None:
            raise ApiProblem(404, "not-found", "No such shipment.")
        status = str(data.get("status", ""))
        if status not in ShipmentStatus.values:
            raise ApiProblem(400, "status", "Choose the tracking status.")
        shipping.add_event(
            shipment.pk,
            status,
            _actor(self),
            description=_text(data, "description", 200),
            location=_text(data, "location", 80),
            request=request,
        )
        return Response(staff_order(shipment.order))


class CouriersView(StaffAPIView):
    required_permission = Perm.ORDERS_VIEW

    @extend_schema(tags=TAG, operation_id="staff_couriers", responses={200: CourierOut(many=True)})
    def get(self, request: Request) -> Response:
        return Response(
            [
                {"code": c.code, "label": c.label, "books_automatically": c.books_automatically}
                for c in couriers.COURIERS.values()
            ]
        )


# --- Refunds and payment reviews -----------------------------------------------------------------------------


class RefundsView(StaffAPIView):
    required_permission = Perm.ORDERS_VIEW

    @extend_schema(
        tags=TAG,
        operation_id="staff_refunds",
        parameters=[OpenApiParameter("state", str)],
        responses={200: RefundRowOut(many=True)},
    )
    def get(self, request: Request) -> Response:
        qs = Refund.objects.select_related("order").order_by("-created_at")
        state = request.query_params.get("state")
        if state in RefundState.values:
            qs = qs.filter(state=state)
        return Response([refund_out(r) for r in qs[:200]])


def _refund(refund_id: str) -> Refund:
    refund = Refund.objects.select_related("order").filter(pk=refund_id).first()
    if refund is None:
        raise ApiProblem(404, "not-found", "No such refund.")
    return refund


class RefundApproveView(StaffAPIView):
    required_permission = Perm.REFUNDS_APPROVE
    step_up = True

    @extend_schema(tags=TAG, operation_id="staff_refund_approve", request=None, responses={200: RefundRowOut})
    def post(self, request: Request, refund_id: str) -> Response:
        payments.approve_refund(_refund(refund_id).pk, _actor(self), request)
        return Response(refund_out(_refund(refund_id)))


class RefundRejectView(StaffAPIView):
    required_permission = Perm.REFUNDS_APPROVE

    @extend_schema(
        tags=TAG, operation_id="staff_refund_reject", request=OpenApiTypes.OBJECT, responses={200: RefundRowOut}
    )
    def post(self, request: Request, refund_id: str) -> Response:
        note = _text(_body(request), "note", 300, required="Say why the refund is rejected.")
        payments.reject_refund(_refund(refund_id).pk, _actor(self), note, request)
        return Response(refund_out(_refund(refund_id)))


class RefundManualView(StaffAPIView):
    """A refund the provider couldn't make, paid by bank transfer and recorded here."""

    required_permission = Perm.REFUNDS_APPROVE
    step_up = True

    @extend_schema(
        tags=TAG, operation_id="staff_refund_manual", request=OpenApiTypes.OBJECT, responses={200: RefundRowOut}
    )
    def post(self, request: Request, refund_id: str) -> Response:
        reference = _text(_body(request), "reference", 120, required="Enter the bank transfer reference.")
        payments.complete_manual(_refund(refund_id).pk, reference, _actor(self), request)
        return Response(refund_out(_refund(refund_id)))


class PaymentReviewView(StaffAPIView):
    required_permission = Perm.REFUNDS_APPROVE

    @extend_schema(
        tags=TAG, operation_id="staff_payment_resolve", request=OpenApiTypes.OBJECT, responses={200: StaffOrderOut}
    )
    def post(self, request: Request, payment_id: str) -> Response:
        payment = Payment.objects.select_related("order").filter(pk=payment_id).first()
        if payment is None:
            raise ApiProblem(404, "not-found", "No such payment.")
        note = _text(_body(request), "note", 300, required="Say how the payment was settled.")
        payments.resolve_review(payment.pk, _actor(self), note, request)
        return Response(staff_order(payment.order))


# --- Alerts --------------------------------------------------------------------------------------------------


class AlertsView(StaffAPIView):
    required_permission = Perm.ORDERS_VIEW

    @extend_schema(
        tags=TAG,
        operation_id="staff_alerts",
        parameters=[OpenApiParameter("resolved", bool)],
        responses={200: AlertOut(many=True)},
    )
    def get(self, request: Request) -> Response:
        resolved = request.query_params.get("resolved") in ("1", "true")
        qs = StaffAlert.objects.filter(resolved_at__isnull=not resolved)
        # Inventory alerts are for people who look after stock; everything else is order and payment work.
        if not access.has_perm(self.account, Perm.INVENTORY_VIEW):
            qs = qs.exclude(kind__startswith="stock_")
        return Response([alert_out(a) for a in qs[:200]])


class AlertResolveView(StaffAPIView):
    required_permission = Perm.ORDERS_UPDATE

    @extend_schema(tags=TAG, operation_id="staff_alert_resolve", request=None, responses={200: AlertOut})
    def post(self, request: Request, alert_id: str) -> Response:
        alert = StaffAlert.objects.filter(pk=alert_id).first()
        if alert is None:
            raise ApiProblem(404, "not-found", "No such alert.")
        if alert.resolved_at is None:
            alert.resolved_at = timezone.now()
            alert.resolved_by = self.account.email
            alert.save(update_fields=["resolved_at", "resolved_by"])
            record(
                "alert.resolve",
                _actor(self),
                target_type="alert",
                target_id=alert.pk,
                after={"kind": alert.kind},
                request=request,
            )
        return Response(alert_out(alert))
