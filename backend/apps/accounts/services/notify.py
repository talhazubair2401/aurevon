"""Security notifications to staff. Every suspension, revocation and recovery event is emailed to the account
(MTS §9); suspensions, recoveries and lockouts also go to every active Owner (MTS §14, decision 0003)."""

from typing import Any

from django.utils import timezone

from apps.notifications.services import send_email

from ..models import Account, AccountStatus, StaffProfile
from ..permissions import RoleCode


def owner_emails(exclude: Account | None = None) -> list[str]:
    rows = StaffProfile.objects.filter(role_id=RoleCode.OWNER, account__status=AccountStatus.ACTIVE)
    if exclude is not None:
        rows = rows.exclude(account=exclude)
    return list(rows.values_list("account__email", flat=True))


def recovery_channels(account: Account) -> list[str]:
    """Every registered channel for recovery notices: the sign-in email and the optional recovery email.
    SMS joins this list once an SMS provider is chosen (P-08)."""
    channels = [account.email]
    profile = StaffProfile.objects.filter(account=account).first()
    if profile and profile.recovery_email:
        channels.append(profile.recovery_email)
    return channels


def to_account(account: Account, template: str, **context: Any) -> None:
    send_email([account.email], template, {"account_email": account.email, "at": timezone.now().isoformat(), **context})


def to_owners(template: str, *, exclude: Account | None = None, **context: Any) -> None:
    send_email(owner_emails(exclude), template, {"at": timezone.now().isoformat(), **context})
