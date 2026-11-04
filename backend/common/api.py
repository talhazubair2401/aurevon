"""Shared API building blocks for public (unauthenticated) endpoints."""

from typing import Any

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

LOCALES = ("en", "ur")


class PublicAPIView(APIView):
    """Read-only public endpoint: no cookies are read, so no session is ever touched (MTS §8)."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]


def request_locale(request: Request) -> str:
    locale = request.query_params.get("locale", "en")
    if locale not in LOCALES:
        raise ValidationError({"locale": f"Must be one of {', '.join(LOCALES)}."})
    return locale


def money(amount: Any, currency: str) -> dict[str, str] | None:
    """Money as a decimal string plus currency (MTS §8)."""
    if amount is None:
        return None
    return {"amount": f"{amount:.2f}", "currency": currency}
