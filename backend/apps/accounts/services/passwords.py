"""Password rules (decision 0003, 3.5): length by realm, common and leaked passwords blocked, no
composition rules, no forced rotation. Django's common-password list is drawn from breached-password
corpora; it is checked offline, so no password ever leaves the server."""

from typing import Any

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.utils import timezone

from .. import policy
from ..models import Account, AccountType


def validate(password: str, account_type: str, account: Account | None = None) -> list[str]:
    minimum = policy.STAFF_PASSWORD_MIN if account_type == AccountType.STAFF else policy.CUSTOMER_PASSWORD_MIN
    errors: list[str] = []
    if len(password) > policy.PASSWORD_MAX:
        errors.append(f"Use at most {policy.PASSWORD_MAX} characters.")
    validators: list[Any] = [
        password_validation.MinimumLengthValidator(min_length=minimum),
        password_validation.CommonPasswordValidator(),
        password_validation.NumericPasswordValidator(),
    ]
    if account is not None:
        validators.append(password_validation.UserAttributeSimilarityValidator(user_attributes=("email", "full_name")))
    try:
        password_validation.validate_password(password, user=account, password_validators=validators)
    except ValidationError as exc:
        errors.extend(str(m) for m in exc.messages)
    return errors


def set_password(account: Account, password: str) -> None:
    account.set_password(password)
    account.password_changed_at = timezone.now()
    account.save(update_fields=["password", "password_changed_at"])
