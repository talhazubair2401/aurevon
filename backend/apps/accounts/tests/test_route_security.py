"""M14 security review, automated: every staff route is permission-gated, and no staff route answers a signed-out
caller or a customer session. New routes are covered automatically, so a forgotten permission fails CI."""

import re
from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.api.base import StaffAPIView
from apps.accounts.api.urls import staff_urlpatterns

pytestmark = pytest.mark.django_db

# Routes a signed-out person must reach: signing in, enrolment, recovery and password reset.
PUBLIC_STAFF = re.compile(r"^(auth/|enroll|recover|password-reset|recovery)")


def _walk(patterns: list[Any], prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for p in patterns:
        if isinstance(p, URLResolver):
            out += _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            out.append((prefix + str(p.pattern), getattr(p.callback, "view_class", None)))
    return out


def _concrete(route: str) -> str:
    route = re.sub(r"<uuid:[^>]+>", "00000000-0000-0000-0000-000000000000", route)
    route = re.sub(r"<slug:[^>]+>", "x", route)
    return re.sub(r"<(str:)?[^>]+>", "x", route)


ROUTES = _walk(staff_urlpatterns)


def test_every_staff_view_declares_a_permission() -> None:
    missing = []
    for route, view in ROUTES:
        if view is None or PUBLIC_STAFF.match(route) or not issubclass(view, StaffAPIView):
            continue
        if route.startswith("me/") or route in ("me", "session"):
            continue  # the signed-in staff member's own account: authentication is the gate
        if view.required_permission is None:
            missing.append(route)
    assert missing == [], f"staff routes without required_permission: {missing}"


@pytest.mark.parametrize("route", [r for r, v in ROUTES if v is not None and not PUBLIC_STAFF.match(r)])
def test_staff_routes_refuse_signed_out_and_customer_callers(route: str) -> None:
    url = f"/api/v1/staff/{_concrete(route)}"
    anonymous = APIClient()
    customer = APIClient()
    customer.post("/api/v1/auth/register", {"email": "c@example.pk", "password": "silk and linen 2026"}, format="json")
    login = customer.post(
        "/api/v1/auth/login", {"email": "c@example.pk", "password": "silk and linen 2026"}, format="json"
    )
    customer.credentials(HTTP_X_CSRF_TOKEN=login.json().get("csrf_token", ""))
    for client in (anonymous, customer):
        for method in ("get", "post", "put", "patch", "delete"):
            status = getattr(client, method)(url, {}, format="json").status_code
            assert status in (401, 403, 404, 405), f"{method.upper()} {url} -> {status}"


def test_api_routes_are_resolvable() -> None:
    assert get_resolver().resolve("/api/v1/staff/orders")
