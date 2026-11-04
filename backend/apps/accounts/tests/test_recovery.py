"""Assisted and break-glass recovery (MTS §9, decision 0003 section 4 with clarifications 1 and 3)."""

import io
from datetime import timedelta
from typing import Any

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import totp
from apps.accounts.models import StaffProfile, StaffRecoveryRequest
from apps.accounts.permissions import RoleCode
from apps.accounts.services import recovery
from apps.accounts.tests.factories import PASSWORD, STAFF, last_mail_to, link_token, make_staff, sign_in
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db
NEW_PASSWORD = "a long and unusual passphrase"


def password_works(email: str, password: str = PASSWORD) -> bool:
    r = APIClient().post(f"{STAFF}/auth/login", {"email": email, "password": password}, format="json")
    return r.status_code == 200


def complete_recovery(email: str) -> dict[str, Any]:
    token = link_token(last_mail_to(email))
    client = APIClient()
    pending = client.post(f"{STAFF}/auth/recovery/start", {"token": token}, format="json")
    assert pending.status_code == 200, pending.content
    code = totp.code_at(pending.json()["secret"], totp.current_step())
    r = client.post(
        f"{STAFF}/auth/recovery/complete", {"token": token, "password": NEW_PASSWORD, "code": code}, format="json"
    )
    assert r.status_code == 200, r.content
    body: dict[str, Any] = r.json()
    return body


def test_assisted_recovery_of_staff_proceeds_at_once(owner_client, db):
    support = make_staff(RoleCode.SUPPORT, "s@aurevon.test")
    open_session = sign_in(support)
    r = owner_client.post(f"{STAFF}/accounts/{support.account.pk}/recovery")
    assert r.status_code == 200 and r.json()["recovery"]["status"] == "released"
    assert not password_works("s@aurevon.test")  # old password stops working at once
    assert open_session.get(f"{STAFF}/auth/session").status_code == 401
    body = complete_recovery("s@aurevon.test")
    assert len(body["recovery_codes"]) == 10
    assert password_works("s@aurevon.test", NEW_PASSWORD)
    assert StaffRecoveryRequest.objects.get().status == "completed"


def test_nobody_approves_their_own_recovery_and_only_owners_approve(owner_client, owner, db):
    assert owner_client.post(f"{STAFF}/accounts/{owner.account.pk}/recovery").status_code == 403
    admin = make_staff(RoleCode.STORE_ADMIN)
    support = make_staff(RoleCode.SUPPORT)
    assert sign_in(admin).post(f"{STAFF}/accounts/{support.account.pk}/recovery").status_code == 403


def test_owner_recovery_waits_24_hours_and_notifies_every_channel(owner, owner2):
    StaffProfile.objects.filter(account=owner2.account).update(recovery_email="owner2.backup@example.test")
    client = sign_in(owner)
    r = client.post(f"{STAFF}/accounts/{owner2.account.pk}/recovery")
    assert r.status_code == 200
    req = StaffRecoveryRequest.objects.get()
    assert req.status == "waiting"
    assert timedelta(hours=23, minutes=59) < req.effective_at - timezone.now() <= timedelta(hours=24)
    # During the wait the old credentials still work, so a real Owner can sign in and cancel.
    assert password_works(owner2.account.email)
    for channel in (owner2.account.email, "owner2.backup@example.test"):
        body = last_mail_to(channel)
        assert "cancel" in body.lower() and "#token=" in body
    # Before the wait ends nothing happens.
    assert recovery.release_due() == 0
    assert password_works(owner2.account.email)


def test_cancellation_link_works_immediately_without_signing_in(owner, owner2):
    sign_in(owner).post(f"{STAFF}/accounts/{owner2.account.pk}/recovery")
    token = link_token(last_mail_to(owner2.account.email))
    r = APIClient().post(f"{STAFF}/auth/recovery/cancel", {"token": token}, format="json")
    assert r.status_code == 204
    assert StaffRecoveryRequest.objects.get().status == "cancelled"
    StaffRecoveryRequest.objects.update(effective_at=timezone.now() - timedelta(minutes=1))
    assert recovery.release_due() == 0
    assert password_works(owner2.account.email)
    assert AuditLog.objects.filter(action="staff.recovery_cancelled").exists()
    # the link is single-use
    assert APIClient().post(f"{STAFF}/auth/recovery/cancel", {"token": token}, format="json").status_code == 400


def test_the_affected_owner_can_cancel_from_the_dashboard(owner, owner2):
    sign_in(owner).post(f"{STAFF}/accounts/{owner2.account.pk}/recovery")
    client = sign_in(owner2)
    session = client.get(f"{STAFF}/auth/session").json()
    assert session["recovery_in_progress"]["status"] == "waiting"
    assert client.post(f"{STAFF}/accounts/{owner2.account.pk}/recovery/cancel").status_code == 200
    assert StaffRecoveryRequest.objects.get().status == "cancelled"


def test_after_the_wait_the_recovery_is_released_and_can_be_completed(owner, owner2):
    sign_in(owner).post(f"{STAFF}/accounts/{owner2.account.pk}/recovery")
    StaffRecoveryRequest.objects.update(effective_at=timezone.now() - timedelta(seconds=1))
    mail.outbox.clear()
    assert recovery.release_due() == 1
    assert not password_works(owner2.account.email)
    assert "30 minutes" in last_mail_to(owner2.account.email)
    complete_recovery(owner2.account.email)
    assert password_works(owner2.account.email, NEW_PASSWORD)


def test_break_glass_needs_the_sealed_code_and_works_once(owner, monkeypatch):
    out = io.StringIO()
    call_command("create_breakglass_code", stdout=out)
    code = out.getvalue().split("\n")[1].strip()

    def run(stdin_code: str) -> str:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin_code + "\n"))
        result = io.StringIO()
        call_command(
            "breakglass_recover_owner",
            email=owner.account.email,
            operator="Test Operator",
            code_stdin=True,
            stdout=result,
        )
        return result.getvalue()

    with pytest.raises(CommandError):
        run("WRONG-CODE")
    assert AuditLog.objects.filter(action="security.break_glass_failed").exists()
    assert password_works(owner.account.email)

    assert "#token=" in run(code)
    assert not password_works(owner.account.email)
    assert AuditLog.objects.filter(action="security.break_glass_used").exists()
    assert any("Break-glass" in m.subject for m in mail.outbox)
    with pytest.raises(CommandError):
        run(code)  # single-use


def test_security_status_requires_two_owners_and_a_sealed_code(owner):
    with pytest.raises(CommandError, match="second, independent Owner"):
        call_command("security_status")
    make_staff(RoleCode.OWNER, "second@aurevon.test")
    call_command("create_breakglass_code", stdout=io.StringIO())
    out = io.StringIO()
    call_command("security_status", stdout=out)
    assert "Ready" in out.getvalue()


def test_create_owner_only_bootstraps_the_first_owner(db):
    call_command("create_owner", email="First@AureVon.test", stdout=io.StringIO())
    assert "#token=" in last_mail_to("first@aurevon.test")
    with pytest.raises(CommandError):
        call_command("create_owner", email="second@aurevon.test")
