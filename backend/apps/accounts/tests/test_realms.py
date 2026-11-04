"""MTS v2.1 A-22 / C-1: customer and staff authentication are strictly separate."""

import re

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.api.base import StaffAPIView, StaffPublicAPIView
from apps.accounts.models import Account, AccountType
from apps.accounts.permissions import RoleCode
from apps.accounts.services import sessions
from apps.accounts.tests.factories import PASSWORD, STAFF, make_staff, sign_in

pytestmark = pytest.mark.django_db


def _staff_routes() -> list[tuple[str, type]]:
    """Every route under /api/v1/staff/, read from the URL configuration, so new endpoints can't be missed."""
    found: list[tuple[str, type]] = []

    def walk(patterns, prefix: str) -> None:
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                route = prefix + str(p.pattern)
                view_class = getattr(p.callback, "view_class", None)
                if route.startswith("api/v1/staff/") and view_class is not None:
                    found.append((route, view_class))

    walk(get_resolver().url_patterns, "")
    assert len(found) > 30
    return found


def _concrete(route: str) -> str:
    """Fills every path parameter, so each route resolves to its view (and is refused there)."""
    route = route.replace("<str:key>", "store.support_email")
    route = re.sub(r"<uuid:\w+>", "00000000-0000-0000-0000-000000000001", route)
    return "/" + re.sub(r"<(?:slug|str):\w+>", "example", route)


def customer_client() -> APIClient:
    account = Account.objects.create(email="shopper@aurevon.test", account_type=AccountType.CUSTOMER)
    account.set_password(PASSWORD)
    account.save()
    client = APIClient()
    r = client.post("/api/v1/auth/login", {"email": account.email, "password": PASSWORD}, format="json")
    assert r.status_code == 200
    client.credentials(HTTP_X_CSRF_TOKEN=r.json()["csrf_token"])
    return client


def test_every_staff_route_is_a_staff_view_and_declares_a_permission():
    for route, view_class in _staff_routes():
        assert issubclass(view_class, StaffAPIView | StaffPublicAPIView), route
        if issubclass(view_class, StaffAPIView):
            assert view_class.required_permission is not None, f"{route} declares no permission"


def test_customer_session_is_refused_on_every_protected_staff_route():
    client = customer_client()
    # The browser would never send the staff cookie path a customer cookie... but a hostile client might.
    client.cookies[sessions.STAFF_COOKIE] = client.cookies[sessions.CUSTOMER_COOKIE].value
    for route, view_class in _staff_routes():
        if not issubclass(view_class, StaffAPIView):
            continue
        url = _concrete(route)
        for method in ("get", "post", "put", "delete"):
            if not hasattr(view_class, method):
                continue
            response = getattr(client, method)(url, {}, format="json")
            assert response.status_code == 401, (method, url, response.status_code)


def test_staff_session_is_ignored_by_customer_endpoints(owner):
    client = sign_in(owner)
    client.cookies[sessions.CUSTOMER_COOKIE] = client.cookies[sessions.STAFF_COOKIE].value
    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.get("/api/v1/me/sessions").status_code == 401


def test_staff_cannot_sign_in_as_customer_and_vice_versa(owner):
    r = APIClient().post("/api/v1/auth/login", {"email": owner.account.email, "password": PASSWORD}, format="json")
    assert r.status_code == 401
    customer_client()  # creates shopper@aurevon.test
    r = APIClient().post(f"{STAFF}/auth/login", {"email": "shopper@aurevon.test", "password": PASSWORD}, format="json")
    assert r.status_code == 401


def test_same_email_can_hold_separate_customer_and_staff_accounts(owner):
    customer = Account.objects.create(email=owner.account.email, account_type=AccountType.CUSTOMER)
    assert customer.pk != owner.account.pk


def test_account_type_can_never_change(owner):
    from django.db import DatabaseError, transaction

    with pytest.raises(DatabaseError), transaction.atomic():
        Account.objects.filter(pk=owner.account.pk).update(account_type=AccountType.CUSTOMER)


def test_staff_cookie_attributes(owner):
    client = sign_in(owner)
    cookie = client.cookies[sessions.STAFF_COOKIE]
    assert cookie["path"] == "/api/v1/staff/"
    assert cookie["samesite"] == "Strict" and cookie["secure"] and cookie["httponly"]


def test_customer_cookie_attributes():
    client = customer_client()
    cookie = client.cookies[sessions.CUSTOMER_COOKIE]
    assert cookie["path"] == "/" and cookie["samesite"] == "Lax" and cookie["secure"] and cookie["httponly"]


def test_superuser_flag_grants_nothing(db):
    support = make_staff(RoleCode.SUPPORT)
    assert not hasattr(Account, "is_superuser") and not hasattr(Account, "is_staff")
    # There is no superuser column to set, and the permission check reads only the role tables.
    client = sign_in(support)
    assert client.get(f"{STAFF}/accounts").status_code == 403
