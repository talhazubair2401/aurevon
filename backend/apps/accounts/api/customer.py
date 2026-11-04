"""/api/v1/auth/... and /api/v1/me/sessions — the customer realm. Staff accounts can't sign in here."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from ..services import customers, sessions
from . import presenters
from . import serializers as s
from .base import CustomerAPIView, CustomerPublicAPIView

TAG = ["customer auth"]


def _valid(serializer_class: type[Any], request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


CHECK_EMAIL = {"detail": "Check your email to continue."}


class RegisterView(CustomerPublicAPIView):
    @extend_schema(tags=TAG, request=s.CustomerRegisterIn, responses={202: s.AcceptedOut}, operation_id="auth_register")
    def post(self, request: Request) -> Response:
        data = _valid(s.CustomerRegisterIn, request)
        customers.register(data["email"], data["password"], data["full_name"], request)
        return Response(CHECK_EMAIL, status=status.HTTP_202_ACCEPTED)


class LoginView(CustomerPublicAPIView):
    @extend_schema(
        tags=TAG, request=s.CustomerSignInIn, responses={200: s.CustomerSessionInfoOut}, operation_id="auth_login"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.CustomerSignInIn, request)
        issued = customers.sign_in(data["email"], data["password"], data["remember"], request)
        response = Response(presenters.customer_session_info(issued.session))
        sessions.set_cookie(response, sessions.CUSTOMER, issued)
        return response


class SessionView(CustomerAPIView):
    @extend_schema(tags=TAG, responses={200: s.CustomerSessionInfoOut}, operation_id="auth_session")
    def get(self, request: Request) -> Response:
        return Response(presenters.customer_session_info(self.session))


class LogoutView(CustomerAPIView):
    @extend_schema(tags=TAG, request=None, responses={204: None}, operation_id="auth_logout")
    def post(self, request: Request) -> Response:
        sessions.revoke(sessions.CUSTOMER, self.session, sessions.RevokeReason.SIGN_OUT)
        self.session.revoked_at = self.session.last_seen_at  # stops the rolling-cookie refresh
        response = Response(status=status.HTTP_204_NO_CONTENT)
        sessions.clear_cookie(response, sessions.CUSTOMER)
        return response


class VerifyEmailView(CustomerPublicAPIView):
    @extend_schema(tags=TAG, request=s.TokenIn, responses={204: None}, operation_id="auth_verify")
    def post(self, request: Request) -> Response:
        customers.verify_email(_valid(s.TokenIn, request)["token"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(CustomerPublicAPIView):
    @extend_schema(tags=TAG, request=s.EmailIn, responses={202: s.AcceptedOut}, operation_id="auth_password_reset")
    def post(self, request: Request) -> Response:
        customers.request_password_reset(_valid(s.EmailIn, request)["email"], request)
        return Response(CHECK_EMAIL, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(CustomerPublicAPIView):
    @extend_schema(
        tags=TAG, request=s.TokenPasswordIn, responses={204: None}, operation_id="auth_password_reset_confirm"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.TokenPasswordIn, request)
        customers.confirm_password_reset(data["token"], data["password"], request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MySessionsView(CustomerAPIView):
    """Decision 0003, clarification 2: customers see and revoke their own sessions."""

    @extend_schema(tags=["customer account"], responses={200: s.SessionOut(many=True)}, operation_id="me_sessions")
    def get(self, request: Request) -> Response:
        rows = sessions.live_sessions(sessions.CUSTOMER, self.account)
        return Response([presenters.session_row(r, self.session) for r in rows])


class MySessionView(CustomerAPIView):
    @extend_schema(tags=["customer account"], responses={204: None}, operation_id="me_session_revoke")
    def delete(self, request: Request, session_id: str) -> Response:
        customers.revoke_own_session(self.session, session_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevokeOtherSessionsView(CustomerAPIView):
    @extend_schema(
        tags=["customer account"], request=None, responses={200: s.RevokedOut}, operation_id="me_sessions_revoke_others"
    )
    def post(self, request: Request) -> Response:
        count = sessions.revoke_all(
            sessions.CUSTOMER, self.account, sessions.RevokeReason.USER, except_session=self.session
        )
        return Response({"revoked": count})
