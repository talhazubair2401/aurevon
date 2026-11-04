"""Customer accounts and sessions (MTS §9 Customers; decision 0003, 3.2, 3.3a, 3.4, 3.5).

Responses never reveal whether an email is registered: registration and reset requests always look the
same, and sign-in failures share one message. Repeated failures earn growing delays, not a hard lockout."""

import time

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.notifications.services import send_email
from common import security
from common.exceptions import ApiProblem

from .. import policy
from ..models import Account, AccountStatus, AccountType, CustomerSession, TokenPurpose, normalize_email
from . import passwords, sessions, tokens


def _ip_guard(request: HttpRequest) -> None:
    ip = security.client_ip(request) or "unknown"
    if security.hit("customer-auth-ip", ip, policy.CUSTOMER_AUTH_PER_IP) > policy.CUSTOMER_AUTH_PER_IP.count:
        raise ApiProblem(
            429,
            "rate-limited",
            "Too many attempts. Try again later.",
            security.retry_after(policy.CUSTOMER_AUTH_PER_IP),
        )


def _failure_key(email_key: str) -> str:
    return f"cust-fail:{security.token_hash(email_key)[:32]}"


def required_delay(failures: int) -> int:
    """No delay for the first 5 failures, then 30 s, 60 s, 120 s ... capped at 15 minutes."""
    if failures < policy.CUSTOMER_FREE_FAILURES:
        return 0
    return int(min(30 * 2 ** (failures - policy.CUSTOMER_FREE_FAILURES), policy.CUSTOMER_MAX_DELAY_SECONDS))


def _delay_guard(email_key: str) -> None:
    state = cache.get(_failure_key(email_key))
    if not state:
        return
    failures, last = state
    wait = required_delay(failures) - int(time.time() - last)
    if wait > 0:
        raise ApiProblem(429, "slow-down", "Too many attempts. Wait a moment and try again.", wait)


def _record_failure(email_key: str) -> None:
    key = _failure_key(email_key)
    failures, _last = cache.get(key) or (0, 0.0)
    cache.set(key, (failures + 1, time.time()), timeout=policy.CUSTOMER_FAILURE_WINDOW.window)


def register(email: str, password: str, full_name: str, request: HttpRequest) -> None:
    """Always 'check your email'. A new account gets a verification link; an existing one gets a notice."""
    _ip_guard(request)
    email_key = normalize_email(email)
    errors = passwords.validate(password, AccountType.CUSTOMER)
    if errors:
        raise ApiProblem(400, "weak-password", " ".join(errors))
    try:
        with transaction.atomic():
            account = Account.objects.create(
                email=email_key,
                account_type=AccountType.CUSTOMER,
                full_name=full_name.strip(),
                password=make_password(password),
            )
            account.password_changed_at = timezone.now()
            account.save(update_fields=["password_changed_at"])
            value = tokens.issue(account, TokenPurpose.CUSTOMER_VERIFY_EMAIL, policy.CUSTOMER_VERIFY_LIFETIME)
            send_email([email_key], "customer_verify_email", {"link": tokens.storefront_link("account/verify", value)})
    except IntegrityError:
        send_email([email_key], "customer_already_registered", {"link": f"{settings.SITE_URL}/account/sign-in"})


def sign_in(email: str, password: str, remember: bool, request: HttpRequest) -> sessions.IssuedSession[CustomerSession]:
    _ip_guard(request)
    email_key = normalize_email(email)
    _delay_guard(email_key)
    account = Account.objects.get_for(email_key, AccountType.CUSTOMER)
    if account is None:
        make_password(password)  # equal timing for unknown emails
        ok = False
    else:
        ok = account.check_password(password) and account.status == AccountStatus.ACTIVE
    if not ok or account is None:
        _record_failure(email_key)
        raise ApiProblem(401, "invalid-credentials", "The email or password is incorrect.")
    cache.delete(_failure_key(email_key))
    return sessions.create_customer_session(account, request, remember=remember)


def verify_email(token_value: str) -> None:
    row = tokens.consume(token_value, TokenPurpose.CUSTOMER_VERIFY_EMAIL)
    Account.objects.filter(pk=row.account_id, email_verified_at__isnull=True).update(email_verified_at=timezone.now())


def request_password_reset(email: str, request: HttpRequest) -> None:
    ip = security.client_ip(request) or "unknown"
    email_key = normalize_email(email)
    if security.hit("cust-reset-ip", ip, policy.LINK_REQUESTS_PER_IP) > policy.LINK_REQUESTS_PER_IP.count:
        return
    if (
        security.hit("cust-reset-email", email_key, policy.LINK_REQUESTS_PER_EMAIL)
        > policy.LINK_REQUESTS_PER_EMAIL.count
    ):
        return
    account = Account.objects.get_for(email_key, AccountType.CUSTOMER)
    if account is None or account.status != AccountStatus.ACTIVE:
        return
    with transaction.atomic():
        value = tokens.issue(account, TokenPurpose.CUSTOMER_PASSWORD_RESET, policy.PASSWORD_RESET_LIFETIME)
        send_email(
            [account.email],
            "customer_password_reset",
            {"link": tokens.storefront_link("account/reset-password", value), "minutes": 30},
        )


@transaction.atomic
def confirm_password_reset(token_value: str, password: str, request: HttpRequest) -> None:
    """For customers an email link alone is acceptable (MTS §9). Every session ends."""
    _ip_guard(request)
    row = tokens.peek(token_value, TokenPurpose.CUSTOMER_PASSWORD_RESET)
    errors = passwords.validate(password, AccountType.CUSTOMER, row.account)
    if errors:
        raise ApiProblem(400, "weak-password", " ".join(errors))
    tokens.consume(token_value, TokenPurpose.CUSTOMER_PASSWORD_RESET)
    passwords.set_password(row.account, password)
    sessions.revoke_all(sessions.CUSTOMER, row.account, sessions.RevokeReason.PASSWORD_CHANGED)
    send_email([row.account.email], "customer_password_changed", {})


def revoke_own_session(session: CustomerSession, session_id: str) -> None:
    target = CustomerSession.objects.filter(pk=session_id, account=session.account, revoked_at__isnull=True).first()
    if target is None:
        raise ApiProblem(404, "not-found", "No such session.")
    sessions.revoke(sessions.CUSTOMER, target, sessions.RevokeReason.USER)
