"""Base views for the two realms. Every staff endpoint subclasses StaffAPIView and must declare the
permission it needs; a missing declaration refuses every request (default deny, MTS §9)."""

from typing import Any, ClassVar

from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import ApiProblem

from ..authentication import CustomerSessionAuthentication, StaffSessionAuthentication
from ..models import Account, CustomerSession, StaffSession
from ..permissions import Perm
from ..services import access, sessions


class _Signed:
    """Marker: any signed-in staff member (their own sessions, password, authenticator)."""


SIGNED_IN = _Signed()
PermissionSpec = Perm | _Signed | dict[str, Perm | _Signed]


class StaffAccess(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        session = request.auth
        if not isinstance(session, StaffSession) or not isinstance(request.user, Account):
            return False  # -> 401
        if session.mfa_reenrollment_required and not getattr(view, "allow_during_reenrollment", False):
            raise ApiProblem(403, "mfa-reenrollment-required", "Set up a new authenticator app before continuing.")
        spec: PermissionSpec | None = getattr(view, "required_permission", None)
        if isinstance(spec, dict):
            spec = spec.get(str(request.method))
        if spec is None:
            raise ApiProblem(403, "permission-denied", "This action is not available.")
        if isinstance(spec, Perm) and not access.has_perm(request.user, spec):
            raise ApiProblem(403, "permission-denied", "Your role doesn't allow this action.")
        step_up: bool | frozenset[str] = getattr(view, "step_up", False)
        needs_step_up = step_up if isinstance(step_up, bool) else request.method in step_up
        if needs_step_up and not access.stepped_up(session):
            raise ApiProblem(403, "step-up-required", "Confirm with your authenticator code to continue.")
        return True


class StaffAPIView(APIView):
    authentication_classes = [StaffSessionAuthentication]
    permission_classes = [StaffAccess]
    required_permission: ClassVar[PermissionSpec | None] = None
    step_up: ClassVar[bool | frozenset[str]] = False
    allow_during_reenrollment: ClassVar[bool] = False

    @property
    def account(self) -> Account:
        user = self.request.user
        if not isinstance(user, Account):
            raise ApiProblem(401, "not-signed-in", "Sign in to continue.")
        return user

    @property
    def session(self) -> StaffSession:
        auth = self.request.auth
        if not isinstance(auth, StaffSession):
            raise ApiProblem(401, "not-signed-in", "Sign in to continue.")
        return auth


class StaffPublicAPIView(APIView):
    """Staff sign-in, enrollment and recovery steps: reachable without a session, always rate-limited."""

    authentication_classes = []
    permission_classes = [AllowAny]


class IsCustomer(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        return isinstance(request.auth, CustomerSession) and isinstance(request.user, Account)


class CustomerAPIView(APIView):
    authentication_classes = [CustomerSessionAuthentication]
    permission_classes = [IsCustomer]

    @property
    def account(self) -> Account:
        user = self.request.user
        if not isinstance(user, Account):
            raise ApiProblem(401, "not-signed-in", "Sign in to continue.")
        return user

    @property
    def session(self) -> CustomerSession:
        auth = self.request.auth
        if not isinstance(auth, CustomerSession):
            raise ApiProblem(401, "not-signed-in", "Sign in to continue.")
        return auth

    def finalize_response(self, request: Request, response: Response, *args: Any, **kwargs: Any) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        token = getattr(request, "_customer_token", None)
        session = request.auth
        if token and isinstance(session, CustomerSession) and session.revoked_at is None:
            sessions.refresh_customer_cookie(response, session, token)
        return response


class CustomerPublicAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
