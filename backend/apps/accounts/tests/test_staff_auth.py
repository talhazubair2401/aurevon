from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import totp
from apps.accounts.models import StaffMFADevice, StaffSession
from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import PASSWORD, STAFF, make_staff, sign_in, step_up
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def login(email: str, password: str = PASSWORD, client: APIClient | None = None):
    return (client or APIClient()).post(f"{STAFF}/auth/login", {"email": email, "password": password}, format="json")


def test_sign_in_needs_password_then_authenticator_code(owner):
    client = APIClient()
    r = login(owner.account.email, client=client)
    assert r.status_code == 200 and "challenge" in r.json()
    assert client.get(f"{STAFF}/auth/session").status_code == 401  # no session after the password alone
    r = client.post(
        f"{STAFF}/auth/mfa/verify", {"challenge": r.json()["challenge"], "code": owner.code()}, format="json"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["account"]["role"]["code"] == "owner" and "staff.invite" in body["permissions"]
    assert body["session"]["idle_timeout_seconds"] == 30 * 60
    assert AuditLog.objects.filter(action="staff.sign_in", actor_id=owner.account.pk).exists()


def test_failures_look_the_same_for_unknown_and_known_accounts(owner):
    unknown = login("nobody@aurevon.test")
    wrong = login(owner.account.email, "wrong password!!")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_suspended_account_cannot_sign_in_and_gets_the_generic_answer(db):
    support = make_staff(RoleCode.SUPPORT, status="suspended")
    r = login(support.account.email)
    assert r.status_code == 401 and r.json()["type"].endswith("invalid-credentials")


def test_wrong_code_is_refused_and_a_code_cannot_be_reused(owner):
    client = APIClient()
    challenge = login(owner.account.email, client=client).json()["challenge"]
    r = client.post(f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "code": "000000"}, format="json")
    assert r.status_code == 401
    code = owner.code()
    assert (
        client.post(f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "code": code}, format="json").status_code
        == 200
    )
    challenge = login(owner.account.email).json()["challenge"]
    r = APIClient().post(f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "code": code}, format="json")
    assert r.status_code == 401  # same code, same time step: replay refused


def test_five_failures_lock_for_15_minutes_end_sessions_and_alert_owners(owner, owner2):
    open_session = sign_in(owner)
    for _ in range(5):
        login(owner.account.email, "wrong password!!")
    r = login(owner.account.email)  # correct password, still locked
    assert r.status_code == 429 and int(r["Retry-After"]) > 14 * 60
    assert open_session.get(f"{STAFF}/auth/session").status_code == 401
    assert AuditLog.objects.filter(action="staff.locked", target_id=str(owner.account.pk)).exists()
    alert = [m for m in mail.outbox if "locked" in m.subject]
    assert alert and set(alert[-1].to) == {owner.account.email, owner2.account.email}


def test_unknown_email_locks_the_same_way(db):
    for _ in range(5):
        login("ghost@aurevon.test", "wrong password!!")
    assert login("ghost@aurevon.test").status_code == 429


def test_wrong_codes_count_towards_the_lock(owner):
    challenge = login(owner.account.email).json()["challenge"]
    for _ in range(5):
        APIClient().post(f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "code": "000000"}, format="json")
    assert login(owner.account.email).status_code == 429


def test_per_address_limit(owner):
    for n in range(30):
        login(f"n{n}@aurevon.test", "wrong password!!")
    assert login(owner.account.email).status_code == 429


def test_unsafe_requests_need_the_session_csrf_token(owner):
    client = sign_in(owner)
    client.credentials()  # drop the X-CSRF-Token header
    r = client.post(f"{STAFF}/auth/logout")
    assert r.status_code == 403 and r.json()["type"].endswith("csrf-failed")


def test_idle_timeout_is_30_minutes(owner):
    client = sign_in(owner)
    StaffSession.objects.update(last_seen_at=timezone.now() - timedelta(minutes=31))
    assert client.get(f"{STAFF}/auth/session").status_code == 401


def test_absolute_limit_is_12_hours(owner):
    client = sign_in(owner)
    session = StaffSession.objects.get()
    assert session.expires_at - session.last_seen_at == timedelta(hours=12)
    StaffSession.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert client.get(f"{STAFF}/auth/session").status_code == 401


def test_sign_out_ends_the_session(owner):
    client = sign_in(owner)
    assert client.post(f"{STAFF}/auth/logout").status_code == 204
    assert client.get(f"{STAFF}/auth/session").status_code == 401


def test_high_risk_actions_need_a_fresh_code_valid_for_5_minutes(owner):
    client = sign_in(owner)
    StaffSession.objects.update(stepped_up_at=timezone.now() - timedelta(minutes=6))
    invite = {"email": "new@aurevon.test", "full_name": "New Person", "role": "support"}
    r = client.post(f"{STAFF}/accounts", invite, format="json")
    assert r.status_code == 403 and r.json()["type"].endswith("step-up-required")
    step_up(client, owner)
    assert client.post(f"{STAFF}/accounts", invite, format="json").status_code == 201


def test_sign_in_counts_as_a_fresh_confirmation(owner):
    client = sign_in(owner)
    invite = {"email": "new@aurevon.test", "full_name": "New Person", "role": "support"}
    assert client.post(f"{STAFF}/accounts", invite, format="json").status_code == 201


def test_recovery_code_sign_in_forces_a_new_authenticator(owner):
    client = APIClient()
    challenge = login(owner.account.email, client=client).json()["challenge"]
    r = client.post(
        f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "recovery_code": owner.recovery_codes[0]}, format="json"
    )
    assert r.status_code == 200 and r.json()["session"]["mfa_reenrollment_required"] is True
    client.credentials(HTTP_X_CSRF_TOKEN=r.json()["csrf_token"])
    assert not StaffMFADevice.objects.filter(account=owner.account).exists()  # the lost one stops working
    r = client.get(f"{STAFF}/accounts")
    assert r.status_code == 403 and r.json()["type"].endswith("mfa-reenrollment-required")
    pending = client.post(f"{STAFF}/me/mfa/start").json()
    code = totp.code_at(pending["secret"], totp.current_step())
    r = client.post(f"{STAFF}/me/mfa/confirm", {"code": code}, format="json")
    assert r.status_code == 200 and len(r.json()["recovery_codes"]) == 10
    assert client.get(f"{STAFF}/accounts").status_code == 200
    # the used code and the old set are gone
    challenge = login(owner.account.email).json()["challenge"]
    r = APIClient().post(
        f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "recovery_code": owner.recovery_codes[1]}, format="json"
    )
    assert r.status_code == 401


def test_a_recovery_code_works_once(owner):
    def use(code: str) -> int:
        challenge = login(owner.account.email).json()["challenge"]
        return (
            APIClient()
            .post(f"{STAFF}/auth/mfa/verify", {"challenge": challenge, "recovery_code": code}, format="json")
            .status_code
        )

    assert use(owner.recovery_codes[0]) == 200
    assert use(owner.recovery_codes[0]) == 401


def test_session_lists_and_revokes_own_sessions(owner):
    first = sign_in(owner)
    second = sign_in(owner)
    rows = first.get(f"{STAFF}/me/sessions").json()
    assert len(rows) == 2 and sum(r["current"] for r in rows) == 1
    other = next(r for r in rows if not r["current"])
    assert first.delete(f"{STAFF}/me/sessions/{other['id']}").status_code == 204
    assert second.get(f"{STAFF}/auth/session").status_code == 401
    assert first.get(f"{STAFF}/auth/session").status_code == 200


def test_password_change_ends_other_sessions(owner):
    first = sign_in(owner)
    second = sign_in(owner)
    r = first.post(
        f"{STAFF}/me/password", {"current_password": PASSWORD, "new_password": "a brand new passphrase"}, format="json"
    )
    assert r.status_code == 204
    assert second.get(f"{STAFF}/auth/session").status_code == 401
    assert first.get(f"{STAFF}/auth/session").status_code == 200


def test_staff_password_rules(owner):
    client = sign_in(owner)
    for weak in ["short pass", "password1234", "123456789012"]:
        r = client.post(f"{STAFF}/me/password", {"current_password": PASSWORD, "new_password": weak}, format="json")
        assert r.status_code == 400 and r.json()["type"].endswith("weak-password"), weak


def test_single_owner_warning_until_a_second_owner_exists(owner):
    client = sign_in(owner)
    assert "single_owner" in client.get(f"{STAFF}/auth/session").json()["security_warnings"]
    make_staff(RoleCode.OWNER, "second@aurevon.test")
    assert "single_owner" not in client.get(f"{STAFF}/auth/session").json()["security_warnings"]
