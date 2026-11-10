"""/api/v1/orders/{number}/payment-attempts, /payment-status and /webhooks/payments/{provider} (MTS §8)."""

from typing import Any

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.cart.api.views import CartAPIView
from apps.orders.api.views import find_order

from .. import services
from ..models import Payment, PaymentState


class AttemptOut(serializers.Serializer[Any]):
    redirect_url = serializers.URLField()


class StatusOut(serializers.Serializer[Any]):
    order_status = serializers.CharField()
    payment_status = serializers.CharField()
    attempt = serializers.CharField(allow_null=True, help_text="created | pending | succeeded | not_paid …")


class PaymentAttemptView(CartAPIView):
    @extend_schema(tags=["payments"], request=None, responses={201: AttemptOut}, operation_id="payment_attempt_start")
    def post(self, request: Request, number: str) -> Response:
        order = find_order(request, number)
        return_url = f"{settings.SITE_URL}/{order.locale}/checkout/return?order={order.number}"
        payment = services.start_attempt(order, return_url)
        return Response({"redirect_url": payment.redirect_url}, status=201)


class PaymentStatusView(CartAPIView):
    @extend_schema(tags=["payments"], responses={200: StatusOut}, operation_id="payment_status")
    def get(self, request: Request, number: str) -> Response:
        """The shopper's return page: triggers an immediate provider check of a pending payment (A-23)."""
        order = find_order(request, number)
        latest = Payment.objects.filter(order=order).order_by("-created_at").first()
        if latest is not None and latest.state == PaymentState.PENDING:
            services.check(latest, "return page")
            latest.refresh_from_db()
        order.refresh_from_db()
        return Response(
            {
                "order_status": order.status,
                "payment_status": order.payment_status,
                "attempt": latest.state if latest else None,
            }
        )


@extend_schema(exclude=True)
@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def payment_webhook(request: Request, provider: str) -> Response:
    """Provider callbacks: signature checked, each event stored once, then applied (A-23)."""
    body = request.body
    services.receive_webhook(provider, body, dict(request.headers))
    return Response({"received": True})
