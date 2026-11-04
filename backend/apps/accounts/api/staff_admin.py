"""/api/v1/staff/accounts/... and /staff/roles — staff administration (MTS §8 Staff: administration)."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from common.exceptions import ApiProblem

from ..models import Account, AccountType, Role, StaffProfile
from ..permissions import Perm
from ..services import recovery, sessions, staff_admin
from . import presenters
from . import serializers as s
from .base import SIGNED_IN, StaffAPIView

TAG = ["staff administration"]


def _valid(serializer_class: type[Any], request: Request) -> dict[str, Any]:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def _target(account_id: str) -> Account:
    account = Account.objects.filter(pk=account_id, account_type=AccountType.STAFF).first()
    if account is None:
        raise ApiProblem(404, "not-found", "No such staff account.")
    return account


class RolesView(StaffAPIView):
    required_permission = Perm.STAFF_VIEW

    @extend_schema(tags=TAG, responses={200: s.RoleWithPermissionsOut(many=True)}, operation_id="staff_roles")
    def get(self, request: Request) -> Response:
        roles = Role.objects.prefetch_related("permissions").order_by("name")
        return Response(
            [
                {"code": r.code, "name": r.name, "permissions": sorted(p.permission for p in r.permissions.all())}
                for r in roles
            ]
        )


class StaffAccountsView(StaffAPIView):
    required_permission = {"GET": Perm.STAFF_VIEW, "POST": Perm.STAFF_INVITE}
    step_up = frozenset({"POST"})

    @extend_schema(tags=TAG, responses={200: s.StaffAccountSummaryOut(many=True)}, operation_id="staff_accounts_list")
    def get(self, request: Request) -> Response:
        profiles = StaffProfile.objects.select_related("account", "role").order_by("account__email")
        return Response([presenters.staff_summary(p.account, p) for p in profiles])

    @extend_schema(
        tags=TAG, request=s.InviteIn, responses={201: s.StaffAccountDetailOut}, operation_id="staff_accounts_invite"
    )
    def post(self, request: Request) -> Response:
        data = _valid(s.InviteIn, request)
        account = staff_admin.invite(self.account, data["email"], data["full_name"], data["role"], request)
        return Response(presenters.staff_detail(account), status=status.HTTP_201_CREATED)


class StaffAccountView(StaffAPIView):
    required_permission = Perm.STAFF_VIEW

    @extend_schema(tags=TAG, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_detail")
    def get(self, request: Request, account_id: str) -> Response:
        return Response(presenters.staff_detail(_target(account_id)))


class _Action(StaffAPIView):
    def done(self, target: Account) -> Response:
        target.refresh_from_db()
        return Response(presenters.staff_detail(target))


class StaffRoleView(_Action):
    required_permission = Perm.STAFF_MANAGE_ROLES
    step_up = True

    @extend_schema(
        tags=TAG, request=s.RoleChangeIn, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_role"
    )
    def put(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        staff_admin.change_role(self.account, target, _valid(s.RoleChangeIn, request)["role"], request)
        return self.done(target)


class StaffSuspendView(_Action):
    required_permission = Perm.STAFF_SUSPEND  # Owners and Store Admins: Perm.STAFF_SUSPEND_PRIVILEGED (service)
    step_up = True

    @extend_schema(
        tags=TAG, request=s.SuspendIn, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_suspend"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        staff_admin.suspend(self.account, target, _valid(s.SuspendIn, request)["reason"], request)
        return self.done(target)


class StaffReactivateView(_Action):
    required_permission = Perm.STAFF_REACTIVATE
    step_up = True

    @extend_schema(
        tags=TAG, request=None, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_reactivate"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        staff_admin.reactivate(self.account, target, request)
        return self.done(target)


class StaffDeactivateView(_Action):
    required_permission = Perm.STAFF_DEACTIVATE
    step_up = True

    @extend_schema(
        tags=TAG, request=None, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_deactivate"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        staff_admin.deactivate(self.account, target, request)
        return self.done(target)


class StaffReinviteView(_Action):
    required_permission = Perm.STAFF_INVITE

    @extend_schema(
        tags=TAG, request=None, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_reinvite"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        staff_admin.reissue_invite(self.account, target, request)
        return self.done(target)


class StaffAccountSessionsView(StaffAPIView):
    required_permission = Perm.STAFF_VIEW

    @extend_schema(tags=TAG, responses={200: s.SessionOut(many=True)}, operation_id="staff_accounts_sessions")
    def get(self, request: Request, account_id: str) -> Response:
        rows = sessions.live_sessions(sessions.STAFF, _target(account_id))
        return Response([presenters.session_row(r, self.session) for r in rows])


class StaffAccountRevokeSessionsView(StaffAPIView):
    """Containment: deliberately no re-confirmation, so a compromised account can be cut off at once."""

    required_permission = Perm.STAFF_SUSPEND

    @extend_schema(tags=TAG, request=None, responses={200: s.RevokedOut}, operation_id="staff_accounts_sessions_revoke")
    def post(self, request: Request, account_id: str) -> Response:
        return Response({"revoked": staff_admin.revoke_sessions(self.account, _target(account_id), request)})


class StaffRecoveryView(_Action):
    required_permission = Perm.STAFF_RECOVER
    step_up = True

    @extend_schema(
        tags=TAG, request=None, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_recovery_approve"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        recovery.approve(self.account, target, request)
        return self.done(target)


class StaffRecoveryResendView(_Action):
    required_permission = Perm.STAFF_RECOVER
    step_up = True

    @extend_schema(
        tags=TAG, request=None, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_recovery_resend"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        recovery.resend_link(self.account, target, request)
        return self.done(target)


class StaffRecoveryCancelView(_Action):
    """Any Owner, or the person being recovered (signed in during the wait), can cancel."""

    required_permission = SIGNED_IN

    @extend_schema(
        tags=TAG, request=None, responses={200: s.StaffAccountDetailOut}, operation_id="staff_accounts_recovery_cancel"
    )
    def post(self, request: Request, account_id: str) -> Response:
        target = _target(account_id)
        recovery.cancel_by_staff(self.account, target, request)
        return self.done(target)
