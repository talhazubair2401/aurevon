"""Staff second factor: authenticator app (TOTP) and single-use recovery codes (decision 0003, section 2)."""

import base64
import hashlib
import secrets
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .. import policy, totp
from ..models import Account, StaffMFADevice, StaffRecoveryCode


@dataclass(frozen=True)
class PendingDevice:
    device: StaffMFADevice
    secret: str
    uri: str
    qr_svg: str


def start_enrollment(account: Account) -> PendingDevice:
    """A new, unconfirmed authenticator. Any earlier unconfirmed one is discarded."""
    StaffMFADevice.objects.filter(account=account, confirmed_at__isnull=True).delete()
    secret = totp.new_secret()
    device = StaffMFADevice.objects.create(account=account, secret_encrypted=totp.encrypt_secret(secret))
    uri = totp.provisioning_uri(secret, account.email)
    return PendingDevice(device, secret, uri, totp.qr_svg(uri))


def pending_device(account: Account) -> StaffMFADevice | None:
    return StaffMFADevice.objects.filter(account=account, confirmed_at__isnull=True).order_by("-created_at").first()


def confirmed_device(account: Account) -> StaffMFADevice | None:
    return StaffMFADevice.objects.filter(account=account, confirmed_at__isnull=False).first()


def _use_code(device: StaffMFADevice, code: str) -> bool:
    """Checks a code against a device, locking the row so the same code can't be used twice in parallel."""
    locked = StaffMFADevice.objects.select_for_update().get(pk=device.pk)
    step = totp.matching_step(totp.decrypt_secret(locked.secret_encrypted), code, locked.last_used_step)
    if step is None:
        return False
    locked.last_used_step = step
    locked.save(update_fields=["last_used_step"])
    return True


@transaction.atomic
def verify_code(account: Account, code: str) -> bool:
    device = confirmed_device(account)
    return device is not None and _use_code(device, code)


@transaction.atomic
def confirm_enrollment(account: Account, code: str) -> list[str] | None:
    """Confirms the pending device with a first code, replaces any old device and issues new recovery codes.
    Returns the codes (shown once) or None if the code is wrong."""
    device = pending_device(account)
    if device is None or not _use_code(device, code):
        return None
    StaffMFADevice.objects.filter(account=account, confirmed_at__isnull=False).delete()
    StaffMFADevice.objects.filter(pk=device.pk).update(confirmed_at=timezone.now())
    return issue_recovery_codes(account)


def remove_device_only(account: Account) -> None:
    StaffMFADevice.objects.filter(account=account).delete()


def remove_all(account: Account) -> None:
    StaffMFADevice.objects.filter(account=account).delete()
    StaffRecoveryCode.objects.filter(account=account).delete()


def _code_hash(account: Account, code: str) -> str:
    normalized = code.strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(f"{account.pk}:{normalized}".encode()).hexdigest()


def _new_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(10)).decode()[:12]  # 60 bits
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


@transaction.atomic
def issue_recovery_codes(account: Account) -> list[str]:
    """Replaces every earlier code (decision 0003, 2.3)."""
    StaffRecoveryCode.objects.filter(account=account).delete()
    codes = [_new_code() for _ in range(policy.RECOVERY_CODE_COUNT)]
    StaffRecoveryCode.objects.bulk_create(
        [StaffRecoveryCode(account=account, code_hash=_code_hash(account, c)) for c in codes]
    )
    return codes


@transaction.atomic
def use_recovery_code(account: Account, code: str) -> bool:
    updated = StaffRecoveryCode.objects.filter(
        account=account, code_hash=_code_hash(account, code), used_at__isnull=True
    ).update(used_at=timezone.now())
    return updated == 1


def remaining_recovery_codes(account: Account) -> int:
    return StaffRecoveryCode.objects.filter(account=account, used_at__isnull=True).count()
