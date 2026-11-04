"""Platform endpoints: API index, health checks and JSON error pages."""

import logging
from typing import Any

import redis
from django.conf import settings
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import problem_response

logger = logging.getLogger(__name__)

API_NAME = "AureVon API"
API_VERSION = "v1"


class ApiIndexView(APIView):
    """Identifies the API. Public, so clients and the proxy can confirm routing."""

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="api_index",
        responses=inline_serializer(
            "ApiIndex", fields={"name": serializers.CharField(), "version": serializers.CharField()}
        ),
    )
    def get(self, request: Request) -> Response:
        return Response({"name": API_NAME, "version": API_VERSION})


@require_GET
@never_cache
def health_live(request: HttpRequest) -> JsonResponse:
    """The process is up. Never touches dependencies, so a database outage doesn't restart the app."""
    return JsonResponse({"status": "ok"})


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row: tuple[int] | None = cursor.fetchone()
            return row == (1,)
    except Exception:
        logger.exception("Readiness check failed: database")
        return False


def _check_redis() -> bool:
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        return client.ping() is True
    except Exception:
        logger.exception("Readiness check failed: redis")
        return False


@require_GET
@never_cache
def health_ready(request: HttpRequest) -> JsonResponse:
    """Ready to serve traffic: PostgreSQL and Redis both answer."""
    checks: dict[str, Any] = {"database": _check_database(), "redis": _check_redis()}
    ready = all(checks.values())
    return JsonResponse(
        {"status": "ok" if ready else "unavailable", "checks": {k: "ok" if v else "failed" for k, v in checks.items()}},
        status=200 if ready else 503,
    )


@never_cache
def api_not_found(request: HttpRequest) -> JsonResponse:
    return problem_response(404, "Not found", "No API endpoint matches this path.")


def error_400(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return problem_response(400, "Bad request")


def error_403(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return problem_response(403, "Not allowed")


def error_404(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return problem_response(404, "Not found", "No API endpoint matches this path.")


def error_500(request: HttpRequest) -> JsonResponse:
    return problem_response(500, "Server error", "Something went wrong on our side. It has been logged.")
