"""DRF authentication for the two realms. Each class accepts only its own cookie, only on its own URL space,
so a customer session is ignored on /api/v1/staff/ and a staff session is ignored everywhere else (A-22)."""

from typing import Any

from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request

from common.exceptions import ApiProblem
from common.security import constant_time_equal

from .models import Account, CustomerSession, StaffSession
from .services import sessions

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_HEADER = "HTTP_X_CSRF_TOKEN"
STAFF_PREFIX = "/api/v1/staff/"


def _check_csrf(request: Request, expected: str) -> None:
    if request.method in SAFE_METHODS:
        return
    supplied = str(request.META.get(CSRF_HEADER, ""))
    if not supplied or not constant_time_equal(supplied, expected):
        raise ApiProblem(403, "csrf-failed", "The request is missing a valid X-CSRF-Token header.")


class StaffSessionAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[Account, StaffSession] | None:
        if not request.path.startswith(STAFF_PREFIX):
            return None
        session = sessions.resolve(sessions.STAFF, request.COOKIES.get(sessions.STAFF_COOKIE))
        if session is None:
            return None
        _check_csrf(request, session.csrf_token)
        return session.account, session

    def authenticate_header(self, request: Any) -> str:
        return 'Session realm="staff"'


class CustomerSessionAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[Account, CustomerSession] | None:
        if request.path.startswith(STAFF_PREFIX):
            return None
        token = request.COOKIES.get(sessions.CUSTOMER_COOKIE)
        session = sessions.resolve(sessions.CUSTOMER, token)
        if session is None:
            return None
        _check_csrf(request, session.csrf_token)
        request._customer_token = token  # type: ignore[attr-defined]  # for the rolling "remember me" cookie
        return session.account, session

    def authenticate_header(self, request: Any) -> str:
        return 'Session realm="customer"'
