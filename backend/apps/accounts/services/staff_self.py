"""What a signed-in staff member can do to their own account."""

from django.db import transaction
from django.http import HttpRequest

from apps.audit.services import record
from apps.notifications.services import send_email
from common.exceptions import ApiProblem

from ..models import AccountType, StaffProfile, StaffSession, normalize_email
from . import mfa, notify, passwords, sessions
from .staff_auth import actor_of


@transaction.atomic
def change_password(session: StaffSession, current: str, new: str, request: HttpRequest) -> None:
    account = session.account
    if not account.check_password(current):
        raise ApiProblem(400, "invalid-password", "Your current password is incorrect.")
    errors = passwords.validate(new, AccountType.STAFF, account)
    if errors:
        raise ApiProblem(400, "weak-password", " ".join(errors))
    passwords.set_password(account, new)
    sessions.revoke_all(sessions.STAFF, account, sessions.RevokeReason.PASSWORD_CHANGED, except_session=session)
    record("staff.password_changed", actor_of(account), target_type="account", target_id=account.pk, request=request)
    notify.to_account(account, "staff_password_changed")


@transaction.atomic
def confirm_new_authenticator(session: StaffSession, code: str, request: HttpRequest) -> list[str]:
    account = session.account
    codes = mfa.confirm_enrollment(account, code)
    if codes is None:
        raise ApiProblem(
            400, "invalid-code", "That code isn't right. Scan the QR code again and enter the current code."
        )
    sessions.revoke_all(sessions.STAFF, account, sessions.RevokeReason.MFA_CHANGED, except_session=session)
    if session.mfa_reenrollment_required:
        StaffSession.objects.filter(pk=session.pk).update(mfa_reenrollment_required=False)
        session.mfa_reenrollment_required = False
    record("staff.mfa_replaced", actor_of(account), target_type="account", target_id=account.pk, request=request)
    notify.to_account(account, "staff_mfa_replaced")
    return codes


@transaction.atomic
def regenerate_recovery_codes(session: StaffSession, request: HttpRequest) -> list[str]:
    account = session.account
    codes = mfa.issue_recovery_codes(account)
    record(
        "staff.recovery_codes_regenerated",
        actor_of(account),
        target_type="account",
        target_id=account.pk,
        request=request,
    )
    notify.to_account(account, "staff_recovery_codes_regenerated")
    return codes


@transaction.atomic
def set_recovery_email(session: StaffSession, email: str, request: HttpRequest) -> str:
    account = session.account
    value = normalize_email(email) if email else ""
    if value and value == account.email:
        raise ApiProblem(400, "same-as-sign-in", "Use a different address from your sign-in email.")
    profile = StaffProfile.objects.get(account=account)
    before = profile.recovery_email
    profile.recovery_email = value
    profile.save(update_fields=["recovery_email"])
    record(
        "staff.recovery_email_changed",
        actor_of(account),
        target_type="account",
        target_id=account.pk,
        before={"recovery_email": before},
        after={"recovery_email": value},
        request=request,
    )
    notify.to_account(account, "staff_recovery_email_changed", recovery_email=value or "(removed)")
    if before:
        send_email(
            [before],
            "staff_recovery_email_changed",
            {"account_email": account.email, "recovery_email": value or "(removed)"},
        )
    return value


def revoke_own_session(session: StaffSession, session_id: str, request: HttpRequest) -> None:
    target = StaffSession.objects.filter(pk=session_id, account=session.account, revoked_at__isnull=True).first()
    if target is None:
        raise ApiProblem(404, "not-found", "No such session.")
    sessions.revoke(sessions.STAFF, target, sessions.RevokeReason.USER)
    record(
        "staff.session_revoked", actor_of(session.account), target_type="session", target_id=target.pk, request=request
    )
