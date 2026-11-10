"""Transactional email. Messages are queued only after the surrounding transaction commits (MTS §5),
so a rolled-back change never sends anything. The full outbox and delivery tracking arrive with M8."""

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.dispatch import Signal
from django.utils import timezone

from common.security import new_token, token_hash

from .models import ConsentPurpose, ConsentRecord, ConsentStatus
from .tasks import send_templated_email

# Sent for critical alerts; the accounts app emails Owners and Store Admins (notifications never imports accounts).
critical_alert = Signal()


def send_email(to: list[str], template: str, context: dict[str, Any]) -> None:
    recipients = sorted({address for address in to if address})
    if not recipients:
        return
    transaction.on_commit(lambda: send_templated_email.delay(recipients, template, context), robust=True)


# --- Newsletter consent (double opt-in) ---------------------------------------------------------------------

NEWSLETTER_WORDING_VERSION = "2026-11-04"
CONFIRM_LINK_HOURS = 72


@transaction.atomic
def request_newsletter(email: str, locale: str, source: str) -> None:
    """Start (or restart) double opt-in. Always behaves the same, so it never reveals who is subscribed."""
    email = email.strip().lower()
    record, _ = ConsentRecord.objects.select_for_update().get_or_create(
        email=email,
        purpose=ConsentPurpose.NEWSLETTER,
        defaults={"wording_version": NEWSLETTER_WORDING_VERSION, "source": source, "locale": locale},
    )
    if record.status == ConsentStatus.CONFIRMED:
        return  # already subscribed: nothing to send, same response
    token = new_token()
    record.status = ConsentStatus.PENDING
    record.locale = locale
    record.source = source
    record.wording_version = NEWSLETTER_WORDING_VERSION
    record.confirm_token_hash = token_hash(token)
    record.confirm_expires_at = timezone.now() + timedelta(hours=CONFIRM_LINK_HOURS)
    record.withdrawn_at = None
    record.save()
    link = f"{settings.SITE_URL}/{locale}/newsletter/confirm#token={token}"
    send_email([email], "newsletter_confirm", {"link": link, "hours": CONFIRM_LINK_HOURS})


@transaction.atomic
def confirm_newsletter(token: str) -> bool:
    record = (
        ConsentRecord.objects.select_for_update()
        .filter(
            purpose=ConsentPurpose.NEWSLETTER,
            confirm_token_hash=token_hash(token),
            confirm_expires_at__gt=timezone.now(),
        )
        .first()
    )
    if record is None:
        return False
    record.status = ConsentStatus.CONFIRMED
    record.confirmed_at = timezone.now()
    record.confirm_token_hash = ""  # nosec B105  (clears a used token hash, not a password)
    record.confirm_expires_at = None
    record.save()
    return True


# --- Staff alerts (MTS §14) -----------------------------------------------------------------------------------


def alert(
    kind: str,
    message: str,
    *,
    severity: str = "warning",
    target_type: str = "",
    target_id: Any = "",
    dedupe_key: str = "",
) -> None:
    """Raises an operational alert once (an open alert with the same dedupe key isn't duplicated)."""
    from django.db import IntegrityError

    from .models import StaffAlert

    try:
        with transaction.atomic():
            StaffAlert.objects.create(
                kind=kind,
                severity=severity,
                message=message[:300],
                target_type=target_type,
                target_id=str(target_id),
                dedupe_key=dedupe_key,
            )
    except IntegrityError:
        return
    if severity == "critical":
        critical_alert.send(sender=None, kind=kind, message=message)
