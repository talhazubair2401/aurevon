"""Assisted and break-glass recovery for staff who lost both password and authenticator (MTS §9, D-12).

- Another authorised Owner approves (never the person themselves). For a non-Owner it proceeds at once.
- For an Owner it waits 24 hours. During the wait the old credentials keep working (so a real Owner who
  still has access can simply cancel), and every registered recovery channel gets a notice with an
  immediate cancellation link. Any Owner, or the Owner being recovered, can also cancel from the dashboard.
- When it proceeds ("release"), the old password, authenticator and recovery codes stop working, all
  sessions end, and a 30-minute single-use recovery link is emailed.
- Break-glass skips the wait but needs production server access plus the sealed emergency code."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.notifications.services import send_email
from common.exceptions import ApiProblem
from common.security import new_token

from .. import policy
from ..models import (
    Account,
    AccountStatus,
    AccountToken,
    BreakGlassCredential,
    RecoveryStatus,
    StaffRecoveryRequest,
    TokenPurpose,
)
from ..permissions import Perm, RoleCode
from . import access, mfa, notify, sessions, tokens
from .staff_auth import actor_of

BREAK_GLASS = Actor(None, "break-glass operator")
OPEN = (RecoveryStatus.WAITING, RecoveryStatus.RELEASED)


def open_request(account: Account) -> StaffRecoveryRequest | None:
    return StaffRecoveryRequest.objects.filter(account=account, status__in=OPEN).first()


@transaction.atomic
def approve(actor: Account, target: Account, request: HttpRequest) -> StaffRecoveryRequest:
    if not access.has_perm(actor, Perm.STAFF_RECOVER):
        raise ApiProblem(403, "permission-denied", "Your role doesn't allow this action.")
    if actor.pk == target.pk:
        raise ApiProblem(403, "not-on-self", "Nobody can approve their own recovery.")
    if target.status != AccountStatus.ACTIVE or not target.is_staff_account:
        raise ApiProblem(409, "not-active", "Only active staff accounts can be recovered.")
    target_is_owner = access.role_of(target) == RoleCode.OWNER
    now = timezone.now()
    effective_at = now + policy.OWNER_RECOVERY_WAIT if target_is_owner else now
    try:
        with transaction.atomic():
            req = StaffRecoveryRequest.objects.create(
                account=target, approved_by=actor, approved_by_label=actor.email, effective_at=effective_at
            )
    except IntegrityError as exc:
        raise ApiProblem(409, "recovery-open", "A recovery is already in progress for this account.") from exc
    record(
        "staff.recovery_approved",
        actor_of(actor),
        target_type="account",
        target_id=target.pk,
        after={"recovery_id": str(req.id), "effective_at": effective_at.isoformat(), "owner": target_is_owner},
        request=request,
    )
    notify.to_owners("staff_recovery_owner_notice", email=target.email, by=actor.email, effective_at=_fmt(effective_at))
    if target_is_owner:
        _send_waiting_notices(req)
    else:
        release(req, request)
    return req


def _send_waiting_notices(req: StaffRecoveryRequest) -> None:
    """One cancellation link per registered channel, valid for the whole wait (clarification 3)."""
    lifetime = req.effective_at - timezone.now()
    for channel in notify.recovery_channels(req.account):
        value = tokens.issue(
            req.account, TokenPurpose.STAFF_RECOVERY_CANCEL, lifetime, recovery_request=req, supersede=False
        )
        send_email(
            [channel],
            "staff_owner_recovery_waiting",
            {
                "account_email": req.account.email,
                "approved_by": req.approved_by_label,
                "effective_at": _fmt(req.effective_at),
                "cancel_link": tokens.staff_link("recovery/cancel", value),
            },
        )


@transaction.atomic
def release(req: StaffRecoveryRequest, request: HttpRequest | None = None, *, actor: Actor | None = None) -> str:
    """Invalidates the old credentials, ends sessions and sends a 30-minute recovery link. Returns the link."""
    req = StaffRecoveryRequest.objects.select_for_update().select_related("account").get(pk=req.pk)
    if req.status not in OPEN or req.effective_at > timezone.now():
        raise ApiProblem(409, "recovery-not-ready", "This recovery can't proceed yet.")
    account = req.account
    account.password = make_password(None)
    account.save(update_fields=["password"])
    mfa.remove_all(account)
    sessions.revoke_all(sessions.STAFF, account, sessions.RevokeReason.RECOVERY)
    tokens.cancel_open(account, [TokenPurpose.STAFF_PASSWORD_RESET, TokenPurpose.STAFF_RECOVERY_CANCEL])
    value = tokens.issue(account, TokenPurpose.STAFF_RECOVERY, policy.RECOVERY_LINK_LIFETIME, recovery_request=req)
    link = tokens.staff_link("recover", value)
    first_release = req.status == RecoveryStatus.WAITING
    req.status = RecoveryStatus.RELEASED
    req.released_at = req.released_at or timezone.now()
    req.save(update_fields=["status", "released_at"])
    record(
        "staff.recovery_released" if first_release else "staff.recovery_link_resent",
        actor or Actor(None, "system"),
        target_type="account",
        target_id=account.pk,
        after={"recovery_id": str(req.id)},
        request=request,
    )
    notify.to_account(account, "staff_recovery_link", link=link, minutes=30)
    return link


def resend_link(actor: Account, target: Account, request: HttpRequest) -> None:
    """If the 30-minute link lapsed, an Owner can send a fresh one (no new wait)."""
    if not access.has_perm(actor, Perm.STAFF_RECOVER) or actor.pk == target.pk:
        raise ApiProblem(403, "permission-denied", "Your role doesn't allow this action.")
    req = open_request(target)
    if req is None or req.status != RecoveryStatus.RELEASED:
        raise ApiProblem(409, "recovery-not-released", "There is no released recovery for this account.")
    release(req, request, actor=actor_of(actor))


def release_due() -> int:
    """Scheduled every minute: Owner recoveries whose 24-hour wait has ended."""
    due = StaffRecoveryRequest.objects.filter(status=RecoveryStatus.WAITING, effective_at__lte=timezone.now())
    count = 0
    for req in due:
        release(req)
        count += 1
    return count


@transaction.atomic
def _cancel(req: StaffRecoveryRequest, by_label: str, actor: Actor, request: HttpRequest | None) -> None:
    req = StaffRecoveryRequest.objects.select_for_update().select_related("account").get(pk=req.pk)
    if req.status not in OPEN:
        raise ApiProblem(409, "recovery-closed", "This recovery has already finished or been cancelled.")
    req.status = RecoveryStatus.CANCELLED
    req.finished_at = timezone.now()
    req.cancelled_by_label = by_label
    req.save(update_fields=["status", "finished_at", "cancelled_by_label"])
    AccountToken.objects.filter(recovery_request=req, used_at__isnull=True, cancelled_at__isnull=True).update(
        cancelled_at=timezone.now()
    )
    record(
        "staff.recovery_cancelled",
        actor,
        target_type="account",
        target_id=req.account_id,
        after={"by": by_label},
        request=request,
    )
    send_email(
        notify.recovery_channels(req.account),
        "staff_recovery_cancelled",
        {"account_email": req.account.email, "by": by_label},
    )
    notify.to_owners("staff_recovery_cancelled", account_email=req.account.email, by=by_label)


def cancel_by_link(token_value: str, request: HttpRequest) -> None:
    """The immediate cancellation link from a waiting-period notice. No sign-in needed."""
    row = tokens.consume(token_value, TokenPurpose.STAFF_RECOVERY_CANCEL)
    if row.recovery_request is None:
        raise tokens.invalid_link()
    _cancel(
        row.recovery_request,
        f"{row.account.email} (cancellation link)",
        Actor(row.account_id, row.account.email),
        request,
    )


def cancel_by_staff(actor: Account, target: Account, request: HttpRequest) -> None:
    """Any Owner, or the person being recovered, can cancel from the dashboard."""
    if actor.pk != target.pk and not access.has_perm(actor, Perm.STAFF_RECOVER):
        raise ApiProblem(403, "permission-denied", "Your role doesn't allow this action.")
    req = open_request(target)
    if req is None:
        raise ApiProblem(404, "not-found", "There is no recovery in progress for this account.")
    _cancel(req, actor.email, actor_of(actor), request)


def mark_completed(account: Account, request: HttpRequest) -> None:
    req = open_request(account)
    if req is None:
        return
    StaffRecoveryRequest.objects.filter(pk=req.pk).update(status=RecoveryStatus.COMPLETED, finished_at=timezone.now())
    record("staff.recovery_completed", actor_of(account), target_type="account", target_id=account.pk, request=request)
    notify.to_owners("staff_recovery_completed", account_email=account.email)


# --- Break-glass (D-12, 4.4) ---


def create_break_glass_code(created_by_label: str) -> str:
    """Retires any earlier code and returns a new one, shown once, to be sealed offline."""
    code = "-".join(new_token(6).upper().replace("_", "X").replace("-", "Y")[:8] for _ in range(4))
    with transaction.atomic():
        BreakGlassCredential.objects.filter(used_at__isnull=True, retired_at__isnull=True).update(
            retired_at=timezone.now()
        )
        BreakGlassCredential.objects.create(code_hash=make_password(code), created_by_label=created_by_label)
        record("security.break_glass_code_created", Actor(None, created_by_label))
    return code


def break_glass_recover(email: str, code: str, operator_label: str) -> str:
    """Recovers an Owner immediately. Needs the sealed code (single-use) and is run on the production server.
    A refused attempt is always audited: it is recorded outside the transaction that would roll back."""
    credential = BreakGlassCredential.objects.filter(used_at__isnull=True, retired_at__isnull=True).first()
    if credential is None or not check_password(code.strip(), credential.code_hash):
        record("security.break_glass_failed", Actor(None, operator_label), after={"email": email})
        raise ApiProblem(403, "break-glass-refused", "The emergency code is not valid.")
    target = Account.objects.get_for(email, "staff")
    if target is None or access.role_of(target) != RoleCode.OWNER or target.status != AccountStatus.ACTIVE:
        raise ApiProblem(404, "not-found", "No active Owner account with that email.")
    with transaction.atomic():
        locked = BreakGlassCredential.objects.select_for_update().get(pk=credential.pk)
        if locked.used_at or locked.retired_at:
            raise ApiProblem(403, "break-glass-refused", "The emergency code is not valid.")
        locked.used_at = timezone.now()
        locked.save(update_fields=["used_at"])
        existing = open_request(target)
        if existing is not None:
            existing.status = RecoveryStatus.CANCELLED
            existing.cancelled_by_label = "superseded by break-glass"
            existing.finished_at = timezone.now()
            existing.save(update_fields=["status", "cancelled_by_label", "finished_at"])
        req = StaffRecoveryRequest.objects.create(
            account=target,
            approved_by=None,
            approved_by_label=f"break-glass: {operator_label}",
            effective_at=timezone.now(),
        )
        record("security.break_glass_used", Actor(None, operator_label), target_type="account", target_id=target.pk)
        notify.to_owners("staff_break_glass_used", account_email=target.email, operator=operator_label)
        return release(req, actor=BREAK_GLASS)


def _fmt(at: datetime) -> str:
    return timezone.localtime(at, ZoneInfo(settings.DISPLAY_TIME_ZONE)).strftime("%d %b %Y, %H:%M (%Z)")
