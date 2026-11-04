"""Server-side sessions for the two realms (MTS §9, decision 0003 section 3).

Each realm has its own table, cookie and CSRF token. The cookie carries a random token; the row stores
only its hash, so a database leak exposes no usable session. Every request re-reads the row, so
revocation and suspension apply on the very next request."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from common.security import client_ip, new_token, token_hash, user_agent

from .. import policy
from ..models import Account, AccountStatus, AccountType, CustomerSession, SessionBase, StaffSession

STAFF_COOKIE = "__Secure-av_staff"
STAFF_COOKIE_PATH = "/api/v1/staff/"
CUSTOMER_COOKIE = "__Host-av_session"
CUSTOMER_COOKIE_PATH = "/"

# Writes to last_seen_at are throttled; idle timeouts are measured in minutes, not seconds.
_TOUCH_INTERVAL = timedelta(seconds=60)


class RevokeReason:
    SIGN_OUT = "sign_out"
    USER = "revoked_by_user"
    ADMIN = "revoked_by_admin"
    SUSPENDED = "account_suspended"
    DEACTIVATED = "account_deactivated"
    PASSWORD_CHANGED = "password_changed"  # noqa: S105  # nosec B105
    MFA_CHANGED = "mfa_changed"
    RECOVERY = "account_recovery"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Realm[S: SessionBase]:
    name: str
    model: type[S]
    account_type: str
    cookie: str
    cookie_path: str
    same_site: Literal["Lax", "Strict"]


STAFF: Realm[StaffSession] = Realm("staff", StaffSession, AccountType.STAFF, STAFF_COOKIE, STAFF_COOKIE_PATH, "Strict")
CUSTOMER: Realm[CustomerSession] = Realm(
    "customer", CustomerSession, AccountType.CUSTOMER, CUSTOMER_COOKIE, CUSTOMER_COOKIE_PATH, "Lax"
)


@dataclass
class IssuedSession[S: SessionBase]:
    session: S
    token: str  # goes into the cookie only; never stored


def create_staff_session(
    account: Account, request: HttpRequest, *, reenrollment: bool = False
) -> IssuedSession[StaffSession]:
    if account.account_type != AccountType.STAFF:
        raise ValueError("Staff sessions are only for staff accounts")
    now = timezone.now()
    token = new_token()
    session = StaffSession.objects.create(
        account=account,
        token_hash=token_hash(token),
        csrf_token=new_token(24),
        last_seen_at=now,
        idle_timeout_seconds=int(policy.STAFF_IDLE_TIMEOUT.total_seconds()),
        expires_at=now + policy.STAFF_ABSOLUTE_LIFETIME,
        ip=client_ip(request),
        user_agent=user_agent(request),
        # Signing in with the second factor counts as a fresh confirmation.
        stepped_up_at=None if reenrollment else now,
        mfa_reenrollment_required=reenrollment,
    )
    Account.objects.filter(pk=account.pk).update(last_login=now)
    return IssuedSession(session, token)


def create_customer_session(
    account: Account, request: HttpRequest, *, remember: bool
) -> IssuedSession[CustomerSession]:
    if account.account_type != AccountType.CUSTOMER:
        raise ValueError("Customer sessions are only for customer accounts")
    now = timezone.now()
    token = new_token()
    if remember:
        idle, absolute = policy.CUSTOMER_REMEMBER_IDLE, policy.CUSTOMER_REMEMBER_ABSOLUTE
    else:
        idle = absolute = policy.CUSTOMER_BROWSER_SESSION_CAP
    session = CustomerSession.objects.create(
        account=account,
        token_hash=token_hash(token),
        csrf_token=new_token(24),
        last_seen_at=now,
        idle_timeout_seconds=int(idle.total_seconds()),
        expires_at=now + absolute,
        ip=client_ip(request),
        user_agent=user_agent(request),
        persistent=remember,
    )
    Account.objects.filter(pk=account.pk).update(last_login=now)
    return IssuedSession(session, token)


def is_live(session: SessionBase, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return (
        session.revoked_at is None
        and session.expires_at > now
        and session.last_seen_at + timedelta(seconds=session.idle_timeout_seconds) > now
    )


def resolve[S: SessionBase](realm: Realm[S], token: str | None) -> S | None:
    """The live session for a cookie token, with its account active and of the realm's type; else None."""
    if not token:
        return None
    session = realm.model.objects.select_related("account").filter(token_hash=token_hash(token)).first()  # type: ignore[attr-defined]
    if session is None:
        return None
    account: Account = session.account
    if account.account_type != realm.account_type or account.status != AccountStatus.ACTIVE:
        return None
    now = timezone.now()
    if not is_live(session, now):
        return None
    if now - session.last_seen_at >= _TOUCH_INTERVAL:
        realm.model.objects.filter(pk=session.pk).update(last_seen_at=now)  # type: ignore[attr-defined]
        session.last_seen_at = now
    return session  # type: ignore[no-any-return]


def live_sessions[S: SessionBase](realm: Realm[S], account: Account) -> list[S]:
    now = timezone.now()
    rows: QuerySet[S] = realm.model.objects.filter(  # type: ignore[attr-defined]
        account=account, revoked_at__isnull=True, expires_at__gt=now
    ).order_by("-last_seen_at")
    return [s for s in rows if is_live(s, now)]


def revoke[S: SessionBase](realm: Realm[S], session: S, reason: str) -> None:
    realm.model.objects.filter(pk=session.pk, revoked_at__isnull=True).update(  # type: ignore[attr-defined]
        revoked_at=timezone.now(), revoked_reason=reason
    )


@transaction.atomic
def revoke_all[S: SessionBase](
    realm: Realm[S], account: Account, reason: str, *, except_session: S | None = None
) -> int:
    rows = realm.model.objects.filter(account=account, revoked_at__isnull=True)  # type: ignore[attr-defined]
    if except_session is not None:
        rows = rows.exclude(pk=except_session.pk)
    return int(rows.update(revoked_at=timezone.now(), revoked_reason=reason))


def set_cookie[S: SessionBase](response: HttpResponse, realm: Realm[S], issued: IssuedSession[S]) -> None:
    session = issued.session
    persistent = isinstance(session, StaffSession) or getattr(session, "persistent", False)
    max_age = None
    if persistent:
        # Staff: the cookie lives as long as the session's absolute limit (12 h); the server enforces idling.
        max_age = int((session.expires_at - timezone.now()).total_seconds())
        if isinstance(session, CustomerSession):
            max_age = min(max_age, session.idle_timeout_seconds)
    response.set_cookie(
        realm.cookie,
        issued.token,
        max_age=max_age,
        path=realm.cookie_path,
        secure=True,
        httponly=True,
        samesite=realm.same_site,
    )


def refresh_customer_cookie(response: HttpResponse, session: CustomerSession, token: str) -> None:
    """'Remember me' is rolling: each visit extends the cookie, never past the absolute limit."""
    if not session.persistent:
        return
    remaining = int((session.expires_at - timezone.now()).total_seconds())
    response.set_cookie(
        CUSTOMER.cookie,
        token,
        max_age=max(0, min(remaining, session.idle_timeout_seconds)),
        path=CUSTOMER.cookie_path,
        secure=True,
        httponly=True,
        samesite="Lax",
    )


def clear_cookie[S: SessionBase](response: HttpResponse, realm: Realm[S]) -> None:
    response.delete_cookie(realm.cookie, path=realm.cookie_path, samesite=realm.same_site)
