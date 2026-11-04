"""/api/v1/staff/me/... — a staff member's own sessions, password, authenticator and recovery settings."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from common.exceptions import ApiProblem

from ..services import access, mfa, sessions, staff_self
from . import presenters
from . import serializers as s
from .base import SIGNED_IN, StaffAPIView

TAG = ["staff me"]


def _valid(serializer_class: type[Any], request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class MySessionsView(StaffAPIView):
    required_permission = SIGNED_IN

    @extend_schema(tags=TAG, responses={200: s.SessionOut(many=True)}, operation_id="staff_me_sessions")
    def get(self, request: Request) -> Response:
        rows = sessions.live_sessions(sessions.STAFF, self.account)
        return Response([presenters.session_row(r, self.session) for r in rows])


class MySessionView(StaffAPIView):
    required_permission = SIGNED_IN

    @extend_schema(tags=TAG, responses={204: None}, operation_id="staff_me_session_revoke")
    def delete(self, request: Request, session_id: str) -> Response:
        staff_self.revoke_own_session(self.session, session_id, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyPasswordView(StaffAPIView):
    required_permission = SIGNED_IN
    step_up = True

    @extend_schema(tags=TAG, request=s.ChangePasswordIn, responses={204: None}, operation_id="staff_me_password")
    def post(self, request: Request) -> Response:
        data = _valid(s.ChangePasswordIn, request)
        staff_self.change_password(self.session, data["current_password"], data["new_password"], request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class _NewAuthenticatorBase(StaffAPIView):
    """Replacing the authenticator needs a fresh confirmation, except right after a recovery-code sign-in,
    when setting up a new one is the only thing the session may do."""

    required_permission = SIGNED_IN
    allow_during_reenrollment = True

    def _check(self) -> None:
        if not self.session.mfa_reenrollment_required and not access.stepped_up(self.session):
            raise ApiProblem(403, "step-up-required", "Confirm with your authenticator code to continue.")


class MyMfaStartView(_NewAuthenticatorBase):
    @extend_schema(tags=TAG, request=None, responses={200: s.PendingDeviceOut}, operation_id="staff_me_mfa_start")
    def post(self, request: Request) -> Response:
        self._check()
        pending = mfa.start_enrollment(self.account)
        return Response(
            {
                "email": self.account.email,
                "secret": pending.secret,
                "otpauth_uri": pending.uri,
                "qr_svg": pending.qr_svg,
            }
        )


class MyMfaConfirmView(_NewAuthenticatorBase):
    @extend_schema(tags=TAG, request=s.CodeIn, responses={200: s.RecoveryCodesOut}, operation_id="staff_me_mfa_confirm")
    def post(self, request: Request) -> Response:
        self._check()
        data = _valid(s.CodeIn, request)
        codes = staff_self.confirm_new_authenticator(self.session, data["code"], request)
        return Response({"recovery_codes": codes})


class MyRecoveryCodesView(StaffAPIView):
    required_permission = SIGNED_IN
    step_up = True

    @extend_schema(tags=TAG, request=None, responses={200: s.RecoveryCodesOut}, operation_id="staff_me_recovery_codes")
    def post(self, request: Request) -> Response:
        return Response({"recovery_codes": staff_self.regenerate_recovery_codes(self.session, request)})


class MyRecoveryEmailView(StaffAPIView):
    required_permission = SIGNED_IN
    step_up = frozenset({"PUT"})

    @extend_schema(tags=TAG, responses={200: s.RecoveryEmailOut}, operation_id="staff_me_recovery_email_get")
    def get(self, request: Request) -> Response:
        from ..models import StaffProfile

        return Response({"recovery_email": StaffProfile.objects.get(account=self.account).recovery_email})

    @extend_schema(
        tags=TAG,
        request=s.RecoveryEmailIn,
        responses={200: s.RecoveryEmailOut},
        operation_id="staff_me_recovery_email_set",
    )
    def put(self, request: Request) -> Response:
        data = _valid(s.RecoveryEmailIn, request)
        return Response(
            {"recovery_email": staff_self.set_recovery_email(self.session, data["recovery_email"], request)}
        )
