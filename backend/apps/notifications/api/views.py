"""POST /newsletter/subscribe and /newsletter/confirm: double opt-in, rate-limited, no account needed."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from common.api import LOCALES, PublicAPIView
from common.exceptions import ApiProblem
from common.security import Limit, client_ip, hit

from .. import services

PER_ADDRESS = Limit(count=10, window=3600)


class SubscribeIn(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)
    locale = serializers.ChoiceField(choices=LOCALES, default="en")
    source = serializers.RegexField(r"^[a-z_]{1,40}$", default="storefront")  # type: ignore[assignment]
    consent = serializers.BooleanField()

    def validate_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError("Consent is required to subscribe.")
        return value


class ConfirmIn(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=200)


class NewsletterOut(serializers.Serializer[Any]):
    status = serializers.CharField()


class NewsletterSubscribeView(PublicAPIView):
    @extend_schema(
        tags=["newsletter"], operation_id="newsletter_subscribe", request=SubscribeIn, responses={202: NewsletterOut}
    )
    def post(self, request: Request) -> Response:
        if hit("newsletter", client_ip(request) or "unknown", PER_ADDRESS) > PER_ADDRESS.count:
            raise ApiProblem(429, "rate-limited", "Too many requests. Please try again later.")
        data = SubscribeIn(data=request.data)
        data.is_valid(raise_exception=True)
        services.request_newsletter(
            data.validated_data["email"], data.validated_data["locale"], data.validated_data["source"]
        )
        # Same answer whether or not the address was already subscribed.
        return Response({"status": "confirmation_sent"}, status=202)


class NewsletterConfirmView(PublicAPIView):
    @extend_schema(
        tags=["newsletter"], operation_id="newsletter_confirm", request=ConfirmIn, responses={200: NewsletterOut}
    )
    def post(self, request: Request) -> Response:
        data = ConfirmIn(data=request.data)
        data.is_valid(raise_exception=True)
        if not services.confirm_newsletter(data.validated_data["token"]):
            raise ApiProblem(400, "invalid-link", "This confirmation link is invalid or has expired.")
        return Response({"status": "confirmed"})
