"""Single-use link tokens. Links put the token in the URL fragment (#token=...), so it never reaches
server logs or Referer headers; the page sends it to the API in the request body."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.exceptions import ApiProblem
from common.security import new_token, token_hash

from ..models import Account, AccountToken, StaffRecoveryRequest


def invalid_link() -> ApiProblem:
    return ApiProblem(400, "invalid-link", "This link is invalid or has expired. Ask for a new one.")


def issue(
    account: Account,
    purpose: str,
    lifetime: timedelta,
    *,
    created_by: Account | None = None,
    recovery_request: StaffRecoveryRequest | None = None,
    supersede: bool = True,
) -> str:
    """Creates a token and returns its value (never stored). Earlier unused tokens of the same purpose stop working."""
    if supersede:
        AccountToken.objects.filter(
            account=account, purpose=purpose, used_at__isnull=True, cancelled_at__isnull=True
        ).update(cancelled_at=timezone.now())
    value = new_token()
    AccountToken.objects.create(
        account=account,
        purpose=purpose,
        token_hash=token_hash(value),
        expires_at=timezone.now() + lifetime,
        created_by=created_by,
        recovery_request=recovery_request,
    )
    return value


def peek(value: str, purpose: str) -> AccountToken:
    """The valid token for a value, without using it up. Raises invalid_link() otherwise."""
    row = (
        AccountToken.objects.select_related("account")
        .filter(token_hash=token_hash(value or ""), purpose=purpose)
        .first()
    )
    if row is None or row.used_at or row.cancelled_at or row.expires_at <= timezone.now():
        raise invalid_link()
    return row


@transaction.atomic
def consume(value: str, purpose: str) -> AccountToken:
    row = peek(value, purpose)
    locked = AccountToken.objects.select_for_update().get(pk=row.pk)
    if locked.used_at or locked.cancelled_at:
        raise invalid_link()
    locked.used_at = timezone.now()
    locked.save(update_fields=["used_at"])
    row.used_at = locked.used_at
    return row


def cancel_open(account: Account, purposes: list[str]) -> None:
    AccountToken.objects.filter(
        account=account, purpose__in=purposes, used_at__isnull=True, cancelled_at__isnull=True
    ).update(cancelled_at=timezone.now())


def staff_link(path: str, value: str) -> str:
    return f"{settings.SITE_URL}/staff/{path}#token={value}"


def storefront_link(path: str, value: str) -> str:
    return f"{settings.SITE_URL}/{path}#token={value}"
