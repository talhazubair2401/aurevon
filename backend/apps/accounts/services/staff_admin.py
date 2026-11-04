"""Staff account administration. Rules are enforced here as well as in the API (MTS §9 "two layers")."""

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.http import HttpRequest

from apps.audit.services import record
from common.exceptions import ApiProblem

from .. import policy
from ..models import Account, AccountStatus, AccountType, Role, StaffProfile, TokenPurpose, normalize_email
from ..permissions import PRIVILEGED_ROLES, Perm, RoleCode
from . import access, notify, sessions, tokens
from .staff_auth import actor_of


def _require(actor: Account, perm: Perm) -> None:
    if not access.has_perm(actor, perm):
        raise ApiProblem(403, "permission-denied", "Your role doesn't allow this action.")


def _staff(target: Account) -> StaffProfile:
    profile = StaffProfile.objects.select_related("account", "role").filter(account=target).first()
    if profile is None or target.account_type != AccountType.STAFF:
        raise ApiProblem(404, "not-found", "No such staff account.")
    return profile


def _require_target_control(actor: Account, target: Account, profile: StaffProfile) -> None:
    """Store Admins may act on other staff, never on Owners or Store Admins (decision 0003, 1.3)."""
    if actor.pk == target.pk:
        raise ApiProblem(403, "not-on-self", "You can't do this to your own account.")
    perm = Perm.STAFF_SUSPEND_PRIVILEGED if profile.role_id in PRIVILEGED_ROLES else Perm.STAFF_SUSPEND
    _require(actor, perm)


def _guard_last_owner(profile: StaffProfile) -> None:
    if (
        profile.role_id == RoleCode.OWNER
        and profile.account.status == AccountStatus.ACTIVE
        and access.active_owner_count() <= 1
    ):
        raise ApiProblem(409, "last-owner", "This is the only active Owner. Add another Owner first.")


@transaction.atomic
def invite(actor: Account, email: str, full_name: str, role_code: str, request: HttpRequest) -> Account:
    _require(actor, Perm.STAFF_INVITE)
    role = Role.objects.filter(code=role_code).first()
    if role is None:
        raise ApiProblem(400, "unknown-role", "Choose one of the listed roles.")
    try:
        with transaction.atomic():
            account = Account.objects.create(
                email=normalize_email(email),
                account_type=AccountType.STAFF,
                status=AccountStatus.INVITED,
                full_name=full_name.strip(),
                password=make_password(None),  # unusable until enrollment
            )
    except IntegrityError as exc:
        raise ApiProblem(409, "already-exists", "A staff account with this email already exists.") from exc
    StaffProfile.objects.create(account=account, role=role, invited_by=actor)
    _send_invite(actor, account, role.name)
    record(
        "staff.invited",
        actor_of(actor),
        target_type="account",
        target_id=account.pk,
        after={"email": account.email, "role": role.code},
        request=request,
    )
    return account


def _send_invite(actor: Account, account: Account, role_name: str) -> None:
    value = tokens.issue(account, TokenPurpose.STAFF_INVITE, policy.STAFF_INVITE_LIFETIME, created_by=actor)
    notify.to_account(
        account,
        "staff_invite",
        link=tokens.staff_link("enroll", value),
        role=role_name,
        invited_by=actor.email,
        hours=48,
    )


@transaction.atomic
def reissue_invite(actor: Account, target: Account, request: HttpRequest) -> None:
    _require(actor, Perm.STAFF_INVITE)
    profile = _staff(target)
    if target.status != AccountStatus.INVITED:
        raise ApiProblem(409, "not-invited", "This account has already been set up.")
    _send_invite(actor, target, profile.role.name)
    record("staff.invite_reissued", actor_of(actor), target_type="account", target_id=target.pk, request=request)


@transaction.atomic
def change_role(actor: Account, target: Account, role_code: str, request: HttpRequest) -> None:
    _require(actor, Perm.STAFF_MANAGE_ROLES)
    if actor.pk == target.pk:
        raise ApiProblem(403, "not-on-self", "Another Owner must change your role.")
    profile = _staff(target)
    role = Role.objects.filter(code=role_code).first()
    if role is None:
        raise ApiProblem(400, "unknown-role", "Choose one of the listed roles.")
    if profile.role_id == role.code:
        return
    if role.code != RoleCode.OWNER:
        _guard_last_owner(profile)
    before = profile.role_id
    StaffProfile.objects.filter(pk=profile.pk).update(role=role)
    record(
        "staff.role_changed",
        actor_of(actor),
        target_type="account",
        target_id=target.pk,
        before={"role": before},
        after={"role": role.code},
        request=request,
    )
    notify.to_account(target, "staff_role_changed", role=role.name)


@transaction.atomic
def suspend(actor: Account, target: Account, reason: str, request: HttpRequest) -> None:
    profile = _staff(target)
    _require_target_control(actor, target, profile)
    if target.status not in (AccountStatus.ACTIVE, AccountStatus.INVITED):
        raise ApiProblem(409, "not-active", "This account is not active.")
    _guard_last_owner(profile)
    before = target.status
    Account.objects.filter(pk=target.pk).update(status=AccountStatus.SUSPENDED)
    revoked = sessions.revoke_all(sessions.STAFF, target, sessions.RevokeReason.SUSPENDED)  # same transaction
    tokens.cancel_open(target, [TokenPurpose.STAFF_INVITE, TokenPurpose.STAFF_PASSWORD_RESET])
    record(
        "staff.suspended",
        actor_of(actor),
        target_type="account",
        target_id=target.pk,
        before={"status": before},
        after={"status": "suspended", "reason": reason, "sessions_revoked": revoked},
        request=request,
    )
    notify.to_account(target, "staff_suspended", reason=reason)
    notify.to_owners("staff_suspended_owner_notice", email=target.email, by=actor.email, reason=reason)


@transaction.atomic
def reactivate(actor: Account, target: Account, request: HttpRequest) -> None:
    _require(actor, Perm.STAFF_REACTIVATE)
    _staff(target)
    if target.status not in (AccountStatus.SUSPENDED, AccountStatus.DEACTIVATED):
        raise ApiProblem(409, "not-suspended", "This account is not suspended or deactivated.")
    from . import mfa  # avoid a module cycle at import time

    new_status = (
        AccountStatus.ACTIVE if target.has_usable_password() and mfa.confirmed_device(target) else AccountStatus.INVITED
    )
    before = target.status
    Account.objects.filter(pk=target.pk).update(status=new_status)
    record(
        "staff.reactivated",
        actor_of(actor),
        target_type="account",
        target_id=target.pk,
        before={"status": before},
        after={"status": new_status},
        request=request,
    )
    notify.to_account(target, "staff_reactivated")


@transaction.atomic
def deactivate(actor: Account, target: Account, request: HttpRequest) -> None:
    """For leavers. Only an Owner may reverse it."""
    _require(actor, Perm.STAFF_DEACTIVATE)
    if actor.pk == target.pk:
        raise ApiProblem(403, "not-on-self", "You can't deactivate your own account.")
    profile = _staff(target)
    if target.status == AccountStatus.DEACTIVATED:
        return
    _guard_last_owner(profile)
    before = target.status
    Account.objects.filter(pk=target.pk).update(status=AccountStatus.DEACTIVATED)
    sessions.revoke_all(sessions.STAFF, target, sessions.RevokeReason.DEACTIVATED)
    tokens.cancel_open(target, [TokenPurpose.STAFF_INVITE, TokenPurpose.STAFF_PASSWORD_RESET])
    record(
        "staff.deactivated",
        actor_of(actor),
        target_type="account",
        target_id=target.pk,
        before={"status": before},
        after={"status": "deactivated"},
        request=request,
    )
    notify.to_account(target, "staff_deactivated")


@transaction.atomic
def revoke_sessions(actor: Account, target: Account, request: HttpRequest) -> int:
    profile = _staff(target)
    _require_target_control(actor, target, profile)
    count = sessions.revoke_all(sessions.STAFF, target, sessions.RevokeReason.ADMIN)
    record(
        "staff.sessions_revoked",
        actor_of(actor),
        target_type="account",
        target_id=target.pk,
        after={"sessions_revoked": count},
        request=request,
    )
    notify.to_account(target, "staff_sessions_revoked", by=actor.email)
    return count
