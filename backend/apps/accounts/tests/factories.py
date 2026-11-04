"""Test helpers: staff accounts with a real authenticator, signed in through the real API."""

import re
from dataclasses import dataclass, field

from django.core import mail
from rest_framework.test import APIClient

from apps.accounts import totp
from apps.accounts.models import (
    Account,
    AccountStatus,
    AccountType,
    Role,
    StaffMFADevice,
    StaffProfile,
)
from apps.accounts.permissions import RoleCode
from apps.accounts.services import mfa

PASSWORD = "correct horse battery staple"
STAFF = "/api/v1/staff"


@dataclass
class Staff:
    account: Account
    secret: str
    recovery_codes: list[str] = field(default_factory=list)

    def code(self) -> str:
        """A valid, not-yet-used code. Moves past the last used step so tests can sign in repeatedly."""
        device = StaffMFADevice.objects.get(account=self.account, confirmed_at__isnull=False)
        current = totp.current_step()
        if device.last_used_step >= current - 1:
            StaffMFADevice.objects.filter(pk=device.pk).update(last_used_step=current - 2)
        return totp.code_at(self.secret, current)


def make_staff(role: str = RoleCode.SUPPORT, email: str | None = None, status: str = AccountStatus.ACTIVE) -> Staff:
    email = email or f"{role}-{Account.objects.count()}@aurevon.test"
    account = Account.objects.create(email=email, account_type=AccountType.STAFF, status=status, full_name=role.title())
    account.set_password(PASSWORD)
    account.save()
    StaffProfile.objects.create(account=account, role=Role.objects.get(code=role))
    pending = mfa.start_enrollment(account)
    codes = mfa.confirm_enrollment(account, totp.code_at(pending.secret, totp.current_step())) or []
    StaffMFADevice.objects.filter(account=account).update(last_used_step=0)
    return Staff(account, pending.secret, codes)


def sign_in(staff: Staff, client: APIClient | None = None) -> APIClient:
    """Signs in through the real API and returns a client carrying the cookie and CSRF header."""
    client = client or APIClient()
    r = client.post(f"{STAFF}/auth/login", {"email": staff.account.email, "password": PASSWORD}, format="json")
    assert r.status_code == 200, r.content
    r = client.post(
        f"{STAFF}/auth/mfa/verify", {"challenge": r.json()["challenge"], "code": staff.code()}, format="json"
    )
    assert r.status_code == 200, r.content
    client.credentials(HTTP_X_CSRF_TOKEN=r.json()["csrf_token"])
    return client


def step_up(client: APIClient, staff: Staff) -> None:
    r = client.post(f"{STAFF}/auth/step-up", {"code": staff.code()}, format="json")
    assert r.status_code == 200, r.content


def link_token(message_body: str) -> str:
    match = re.search(r"#token=([A-Za-z0-9_\-]+)", message_body)
    assert match, message_body
    return match.group(1)


def last_mail_to(address: str) -> str:
    for message in reversed(mail.outbox):
        if address in message.to:
            return str(message.body)
    raise AssertionError(f"no email to {address}; outbox: {[m.to for m in mail.outbox]}")
