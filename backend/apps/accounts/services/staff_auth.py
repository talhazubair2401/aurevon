"""Staff sign-in (password, then authenticator code), lockout, re-confirmation, enrollment and password reset.

Responses never reveal whether an account exists: unknown emails, wrong passwords, suspended accounts and
locked accounts look the same from outside (decision 0003, 3.4)."""

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.audit.services import Actor, record
from common import security
from common.exceptions import ApiProblem

from .. import policy
from ..models import Account, AccountStatus, AccountType, StaffSession, TokenPurpose, normalize_email
from . import mfa, notify, passwords, sessions, tokens

_CHALLENGE_PREFIX = "staff-mfa-challenge:"


def actor_of(account: Account) -> Actor:
    return Actor(account.pk, account.email)


def _ip_guard(request: HttpRequest) -> None:
    ip = security.client_ip(request) or "unknown"
    if security.hit("staff-auth-ip", ip, policy.STAFF_AUTH_PER_IP) > policy.STAFF_AUTH_PER_IP.count:
        raise ApiProblem(
            429, "rate-limited", "Too many attempts. Try again later.", security.retry_after(policy.STAFF_AUTH_PER_IP)
        )


def _lock_guard(email_key: str) -> None:
    remaining = security.lock_remaining("staff-login", email_key)
    if remaining:
        raise ApiProblem(429, "temporarily-locked", "Too many attempts. Try again later.", remaining)


def register_failure(email_key: str, account: Account | None, request: HttpRequest, kind: str) -> None:
    """5 failures of any kind (password or code) in 15 minutes lock sign-in for 15 minutes, end the account's
    sessions, and alert Owners (decision 0003, 2.4 and 3.4)."""
    failures = security.hit("staff-fail", email_key, policy.STAFF_FAILURE_LIMIT)
    if failures < policy.STAFF_FAILURE_LIMIT.count:
        return
    security.set_lock("staff-login", email_key, policy.STAFF_LOCK_SECONDS)
    if account is None:
        return
    with transaction.atomic():
        sessions.revoke_all(sessions.STAFF, account, "locked")
        record(
            "staff.locked",
            actor_of(account),
            target_type="account",
            target_id=account.pk,
            after={"after": kind},
            request=request,
        )
        notify.to_owners("staff_locked", email=account.email, minutes=policy.STAFF_LOCK_SECONDS // 60)


def _dummy_password_check(password: str) -> None:
    make_password(password)  # same cost as a real check, so timing doesn't reveal unknown emails


def start_sign_in(email: str, password: str, request: HttpRequest) -> str:
    """Checks the password and returns a short-lived challenge for the authenticator step."""
    _ip_guard(request)
    email_key = normalize_email(email)
    _lock_guard(email_key)
    account = Account.objects.get_for(email_key, AccountType.STAFF)
    if account is None:
        _dummy_password_check(password)
        ok = False
    else:
        ok = account.check_password(password) and account.status == AccountStatus.ACTIVE
    if not ok or account is None:
        register_failure(email_key, account, request, "password")
        raise ApiProblem(401, "invalid-credentials", "The email or password is incorrect.")
    challenge = security.new_token()
    cache.set(_CHALLENGE_PREFIX + security.token_hash(challenge), str(account.pk), policy.MFA_CHALLENGE_SECONDS)
    return challenge


def complete_sign_in(
    challenge: str, code: str | None, recovery_code: str | None, request: HttpRequest
) -> sessions.IssuedSession[StaffSession]:
    _ip_guard(request)
    key = _CHALLENGE_PREFIX + security.token_hash(challenge or "")
    account_id = cache.get(key)
    account = Account.objects.filter(pk=account_id, account_type=AccountType.STAFF).first() if account_id else None
    if account is None or account.status != AccountStatus.ACTIVE:
        raise ApiProblem(401, "sign-in-expired", "Your sign-in has expired. Enter your email and password again.")
    _lock_guard(account.email)

    if code:
        if not mfa.verify_code(account, code):
            register_failure(account.email, account, request, "code")
            raise ApiProblem(401, "invalid-code", "That code isn't right. Check your authenticator app and try again.")
        cache.delete(key)
        issued = sessions.create_staff_session(account, request)
        record("staff.sign_in", actor_of(account), target_type="account", target_id=account.pk, request=request)
        return issued

    if recovery_code:
        # Failures are recorded outside the transaction below, so a lockout is never rolled back.
        if not mfa.use_recovery_code(account, recovery_code):
            register_failure(account.email, account, request, "recovery_code")
            raise ApiProblem(401, "invalid-code", "That recovery code isn't valid.")
        cache.delete(key)
        with transaction.atomic():
            # The lost authenticator stops working; the person must enrol a new one before doing anything else.
            mfa.remove_device_only(account)
            sessions.revoke_all(sessions.STAFF, account, sessions.RevokeReason.RECOVERY)
            issued = sessions.create_staff_session(account, request, reenrollment=True)
            record(
                "staff.recovery_code_used",
                actor_of(account),
                target_type="account",
                target_id=account.pk,
                request=request,
            )
            notify.to_account(account, "staff_recovery_code_used", remaining=mfa.remaining_recovery_codes(account))
        return issued

    raise ApiProblem(400, "code-required", "Enter the code from your authenticator app or a recovery code.")


def step_up(session: StaffSession, code: str, request: HttpRequest) -> None:
    """Re-confirms the second factor; valid for 5 minutes (decision 0003, 2.5)."""
    account = session.account
    _lock_guard(account.email)
    if not mfa.verify_code(account, code):
        register_failure(account.email, account, request, "step_up")
        raise ApiProblem(401, "invalid-code", "That code isn't right.")
    now = timezone.now()
    StaffSession.objects.filter(pk=session.pk).update(stepped_up_at=now)
    session.stepped_up_at = now


def sign_out(session: StaffSession, request: HttpRequest) -> None:
    sessions.revoke(sessions.STAFF, session, sessions.RevokeReason.SIGN_OUT)
    record(
        "staff.sign_out",
        actor_of(session.account),
        target_type="account",
        target_id=session.account_id,
        request=request,
    )


# --- Enrollment (invite) and recovery completion share one flow: set a password and a new authenticator ---

_SETUP_PURPOSES = {"enroll": TokenPurpose.STAFF_INVITE, "recovery": TokenPurpose.STAFF_RECOVERY}


def start_setup(kind: str, token_value: str, request: HttpRequest) -> mfa.PendingDevice:
    _ip_guard(request)
    row = tokens.peek(token_value, _SETUP_PURPOSES[kind])
    return mfa.start_enrollment(row.account)


@transaction.atomic
def complete_setup(
    kind: str, token_value: str, password: str, code: str, request: HttpRequest
) -> tuple[sessions.IssuedSession[StaffSession], list[str]]:
    _ip_guard(request)
    row = tokens.peek(token_value, _SETUP_PURPOSES[kind])
    account = row.account
    expected_status = AccountStatus.INVITED if kind == "enroll" else AccountStatus.ACTIVE
    if account.status != expected_status:
        raise tokens.invalid_link()
    errors = passwords.validate(password, AccountType.STAFF, account)
    if errors:
        raise ApiProblem(400, "weak-password", " ".join(errors))
    codes = mfa.confirm_enrollment(account, code)
    if codes is None:
        raise ApiProblem(
            400, "invalid-code", "That code isn't right. Scan the QR code again and enter the current code."
        )
    tokens.consume(token_value, _SETUP_PURPOSES[kind])
    passwords.set_password(account, password)
    sessions.revoke_all(sessions.STAFF, account, sessions.RevokeReason.RECOVERY)
    if kind == "enroll":
        Account.objects.filter(pk=account.pk).update(status=AccountStatus.ACTIVE)
        account.status = AccountStatus.ACTIVE
        record("staff.enrolled", actor_of(account), target_type="account", target_id=account.pk, request=request)
    else:
        from . import recovery  # local import: recovery depends on this module

        recovery.mark_completed(account, request)
    issued = sessions.create_staff_session(account, request)
    return issued, codes


# --- Forgot password while still holding the authenticator ---


def request_password_reset(email: str, request: HttpRequest) -> None:
    """Always succeeds from the outside. Sends a 30-minute link only to an active staff account."""
    ip = security.client_ip(request) or "unknown"
    email_key = normalize_email(email)
    if security.hit("staff-reset-ip", ip, policy.LINK_REQUESTS_PER_IP) > policy.LINK_REQUESTS_PER_IP.count:
        return
    if (
        security.hit("staff-reset-email", email_key, policy.LINK_REQUESTS_PER_EMAIL)
        > policy.LINK_REQUESTS_PER_EMAIL.count
    ):
        return
    account = Account.objects.get_for(email_key, AccountType.STAFF)
    if account is None or account.status != AccountStatus.ACTIVE or mfa.confirmed_device(account) is None:
        return
    with transaction.atomic():
        value = tokens.issue(account, TokenPurpose.STAFF_PASSWORD_RESET, policy.PASSWORD_RESET_LIFETIME)
        record(
            "staff.password_reset_requested",
            actor_of(account),
            target_type="account",
            target_id=account.pk,
            request=request,
        )
        notify.to_account(account, "staff_password_reset", link=tokens.staff_link("reset-password", value), minutes=30)


def confirm_password_reset(token_value: str, password: str, code: str, request: HttpRequest) -> None:
    """No email-only reset for staff: the authenticator code must be passed too (A-22)."""
    _ip_guard(request)
    row = tokens.peek(token_value, TokenPurpose.STAFF_PASSWORD_RESET)
    account = row.account
    _lock_guard(account.email)
    if account.status != AccountStatus.ACTIVE:
        raise tokens.invalid_link()
    errors = passwords.validate(password, AccountType.STAFF, account)
    if errors:
        raise ApiProblem(400, "weak-password", " ".join(errors))
    if not mfa.verify_code(account, code):
        register_failure(account.email, account, request, "reset_code")
        raise ApiProblem(400, "invalid-code", "That code isn't right.")
    with transaction.atomic():
        tokens.consume(token_value, TokenPurpose.STAFF_PASSWORD_RESET)
        passwords.set_password(account, password)
        sessions.revoke_all(sessions.STAFF, account, sessions.RevokeReason.PASSWORD_CHANGED)
        record("staff.password_reset", actor_of(account), target_type="account", target_id=account.pk, request=request)
        notify.to_account(account, "staff_password_changed")
