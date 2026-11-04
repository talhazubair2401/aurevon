"""/api/v1/staff/auth/... — staff sign-in, re-confirmation, enrollment, password reset and recovery links."""

from typing import Any, ClassVar

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from .. import policy
from ..services import recovery as recovery_service
from ..services import sessions, staff_auth
from . import presenters
from . import serializers as s
from .base import SIGNED_IN, StaffAPIView, StaffPublicAPIView

TAG = ["staff auth"]


def _valid(serializer_class: type[Any], request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def _session_response(issued: sessions.IssuedSession[Any], body: dict[str, Any]) -> Response:
    response = Response(body)
    sessions.set_cookie(response, sessions.STAFF, issued)
    return response


class StaffLoginView(StaffPublicAPIView):
    @extend_schema(
        tags=TAG, request=s.EmailPasswordIn, responses={200: s.ChallengeOut}, operation_id="staff_auth_login"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.EmailPasswordIn, request)
        challenge = staff_auth.start_sign_in(data["email"], data["password"], request)
        return Response({"challenge": challenge, "expires_in": policy.MFA_CHALLENGE_SECONDS})


class StaffMfaVerifyView(StaffPublicAPIView):
    @extend_schema(
        tags=TAG, request=s.MfaVerifyIn, responses={200: s.StaffSessionInfoOut}, operation_id="staff_auth_mfa_verify"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.MfaVerifyIn, request)
        issued = staff_auth.complete_sign_in(data["challenge"], data.get("code"), data.get("recovery_code"), request)
        return _session_response(issued, presenters.staff_session_info(issued.session))


class StaffSessionView(StaffAPIView):
    required_permission = SIGNED_IN
    allow_during_reenrollment = True

    @extend_schema(tags=TAG, responses={200: s.StaffSessionInfoOut}, operation_id="staff_auth_session")
    def get(self, request: Request) -> Response:
        return Response(presenters.staff_session_info(self.session))


class StaffLogoutView(StaffAPIView):
    required_permission = SIGNED_IN
    allow_during_reenrollment = True

    @extend_schema(tags=TAG, request=None, responses={204: None}, operation_id="staff_auth_logout")
    def post(self, request: Request) -> Response:
        staff_auth.sign_out(self.session, request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        sessions.clear_cookie(response, sessions.STAFF)
        return response


class StaffStepUpView(StaffAPIView):
    required_permission = SIGNED_IN

    @extend_schema(tags=TAG, request=s.CodeIn, responses={200: s.StepUpOut}, operation_id="staff_auth_step_up")
    def post(self, request: Request) -> Response:
        data = _valid(s.CodeIn, request)
        staff_auth.step_up(self.session, data["code"], request)
        stepped_up_at = self.session.stepped_up_at or timezone.now()
        return Response({"stepped_up_until": stepped_up_at + policy.STEP_UP_VALIDITY})


class StaffPasswordResetView(StaffPublicAPIView):
    @extend_schema(
        tags=TAG, request=s.EmailIn, responses={202: s.AcceptedOut}, operation_id="staff_auth_password_reset"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.EmailIn, request)
        staff_auth.request_password_reset(data["email"], request)
        return Response(
            {"detail": "If that is an active staff account, a reset link is on its way."},
            status=status.HTTP_202_ACCEPTED,
        )


class StaffPasswordResetConfirmView(StaffPublicAPIView):
    @extend_schema(
        tags=TAG, request=s.TokenPasswordCodeIn, responses={204: None}, operation_id="staff_auth_password_reset_confirm"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.TokenPasswordCodeIn, request)
        staff_auth.confirm_password_reset(data["token"], data["password"], data["code"], request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class _SetupStartView(StaffPublicAPIView):
    kind: ClassVar[str]

    def post(self, request: Request) -> Response:
        data = _valid(s.TokenIn, request)
        pending = staff_auth.start_setup(self.kind, data["token"], request)
        return Response(
            {
                "email": pending.device.account.email,
                "secret": pending.secret,
                "otpauth_uri": pending.uri,
                "qr_svg": pending.qr_svg,
            }
        )


class _SetupCompleteView(StaffPublicAPIView):
    kind: ClassVar[str]

    def post(self, request: Request) -> Response:
        data = _valid(s.TokenPasswordCodeIn, request)
        issued, codes = staff_auth.complete_setup(self.kind, data["token"], data["password"], data["code"], request)
        return _session_response(
            issued, {"session": presenters.staff_session_info(issued.session), "recovery_codes": codes}
        )


class StaffEnrollStartView(_SetupStartView):
    kind = "enroll"

    @extend_schema(
        tags=TAG, request=s.TokenIn, responses={200: s.PendingDeviceOut}, operation_id="staff_auth_enroll_start"
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class StaffEnrollCompleteView(_SetupCompleteView):
    kind = "enroll"

    @extend_schema(
        tags=TAG,
        request=s.TokenPasswordCodeIn,
        responses={200: s.SetupCompleteOut},
        operation_id="staff_auth_enroll_complete",
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class StaffRecoveryStartView(_SetupStartView):
    kind = "recovery"

    @extend_schema(
        tags=TAG, request=s.TokenIn, responses={200: s.PendingDeviceOut}, operation_id="staff_auth_recovery_start"
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class StaffRecoveryCompleteView(_SetupCompleteView):
    kind = "recovery"

    @extend_schema(
        tags=TAG,
        request=s.TokenPasswordCodeIn,
        responses={200: s.SetupCompleteOut},
        operation_id="staff_auth_recovery_complete",
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class StaffRecoveryCancelLinkView(StaffPublicAPIView):
    """The immediate cancellation link sent during an Owner recovery's 24-hour wait."""

    @extend_schema(
        tags=TAG,
        request=s.TokenIn,
        responses={204: None, 400: OpenApiResponse(description="Invalid or expired link")},
        operation_id="staff_auth_recovery_cancel",
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.TokenIn, request)
        recovery_service.cancel_by_link(data["token"], request)
        return Response(status=status.HTTP_204_NO_CONTENT)
