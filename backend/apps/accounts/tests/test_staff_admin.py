from datetime import timedelta
from typing import Any

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import totp
from apps.accounts.models import Account, AccountStatus, AccountToken
from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import PASSWORD, STAFF, last_mail_to, link_token, make_staff, sign_in
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db
NEW_PASSWORD = "a long and unusual passphrase"


def invite(client: APIClient, email: str = "new@aurevon.test", role: str = "support"):
    return client.post(f"{STAFF}/accounts", {"email": email, "full_name": "New Person", "role": role}, format="json")


def enroll(email: str) -> tuple[APIClient, dict[str, Any]]:
    token = link_token(last_mail_to(email))
    client = APIClient()
    pending = client.post(f"{STAFF}/auth/enroll/start", {"token": token}, format="json")
    assert pending.status_code == 200, pending.content
    assert pending.json()["qr_svg"].startswith("<svg")
    code = totp.code_at(pending.json()["secret"], totp.current_step())
    r = client.post(
        f"{STAFF}/auth/enroll/complete", {"token": token, "password": NEW_PASSWORD, "code": code}, format="json"
    )
    assert r.status_code == 200, r.content
    client.credentials(HTTP_X_CSRF_TOKEN=r.json()["session"]["csrf_token"])
    return client, r.json()


def test_owner_invites_and_the_person_enrols_with_an_authenticator(owner_client):
    r = invite(owner_client)
    assert r.status_code == 201 and r.json()["status"] == "invited"
    assert "48 hours" in last_mail_to("new@aurevon.test")
    client, body = enroll("new@aurevon.test")
    assert len(body["recovery_codes"]) == 10
    assert body["session"]["account"]["status"] == "active"
    assert client.get(f"{STAFF}/auth/session").status_code == 200
    assert AuditLog.objects.filter(action="staff.enrolled").exists()


def test_invite_link_works_once_and_expires_after_48_hours(owner_client):
    invite(owner_client)
    token = link_token(last_mail_to("new@aurevon.test"))
    row = AccountToken.objects.get(purpose="staff_invite")
    assert timedelta(hours=47, minutes=59) < row.expires_at - timezone.now() <= timedelta(hours=48)
    AccountToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    r = APIClient().post(f"{STAFF}/auth/enroll/start", {"token": token}, format="json")
    assert r.status_code == 400 and r.json()["type"].endswith("invalid-link")


def test_only_owners_invite(db):
    admin = make_staff(RoleCode.STORE_ADMIN)
    assert invite(sign_in(admin)).status_code == 403


def test_suspension_ends_every_session_on_the_next_request(owner_client, db):
    support = make_staff(RoleCode.SUPPORT, "s@aurevon.test")
    support_client = sign_in(support)
    r = owner_client.post(
        f"{STAFF}/accounts/{support.account.pk}/suspend", {"reason": "Left the company"}, format="json"
    )
    assert r.status_code == 200 and r.json()["status"] == "suspended" and r.json()["active_sessions"] == 0
    assert support_client.get(f"{STAFF}/auth/session").status_code == 401
    assert "suspended" in last_mail_to("s@aurevon.test")
    log = AuditLog.objects.get(action="staff.suspended")
    assert log.after is not None
    assert log.after["sessions_revoked"] == 1 and log.actor_label == "owner@aurevon.test"


def test_store_admin_can_suspend_staff_but_not_owners_or_admins(owner, db):
    admin = make_staff(RoleCode.STORE_ADMIN, "admin@aurevon.test")
    other_admin = make_staff(RoleCode.STORE_ADMIN, "admin2@aurevon.test")
    support = make_staff(RoleCode.SUPPORT, "s@aurevon.test")
    client = sign_in(admin)
    reason = {"reason": "Test"}
    assert client.post(f"{STAFF}/accounts/{owner.account.pk}/suspend", reason, format="json").status_code == 403
    assert client.post(f"{STAFF}/accounts/{other_admin.account.pk}/suspend", reason, format="json").status_code == 403
    assert client.post(f"{STAFF}/accounts/{owner.account.pk}/sessions/revoke").status_code == 403
    assert client.post(f"{STAFF}/accounts/{support.account.pk}/suspend", reason, format="json").status_code == 200
    # only an Owner reactivates
    assert client.post(f"{STAFF}/accounts/{support.account.pk}/reactivate").status_code == 403
    owner_client = sign_in(owner)
    r = owner_client.post(f"{STAFF}/accounts/{support.account.pk}/reactivate")
    assert r.status_code == 200 and r.json()["status"] == "active"


def test_nobody_suspends_themselves(owner_client, owner):
    r = owner_client.post(f"{STAFF}/accounts/{owner.account.pk}/suspend", {"reason": "x"}, format="json")
    assert r.status_code == 403


def test_the_last_owner_cannot_be_suspended_demoted_or_deactivated(owner, owner2):
    client = sign_in(owner)
    target = owner2.account.pk
    assert client.post(f"{STAFF}/accounts/{target}/suspend", {"reason": "x"}, format="json").status_code == 200
    # owner is now the only active Owner; owner2 (suspended) can't act, and nobody can remove owner
    assert Account.objects.get(pk=target).status == AccountStatus.SUSPENDED
    admin = make_staff(RoleCode.STORE_ADMIN)
    r = sign_in(admin).post(f"{STAFF}/accounts/{owner.account.pk}/suspend", {"reason": "x"}, format="json")
    assert r.status_code == 403
    client.post(f"{STAFF}/accounts/{target}/reactivate")
    r = sign_in(owner2).put(f"{STAFF}/accounts/{owner.account.pk}/role", {"role": "support"}, format="json")
    assert r.status_code == 200  # two Owners: allowed
    r = client.put(f"{STAFF}/accounts/{target}/role", {"role": "support"}, format="json")
    assert r.status_code == 403  # owner is no longer an Owner


def test_last_owner_guard_refuses_removing_the_only_active_owner(owner):
    """Through the API this is unreachable (only Owners can act on Owners, and never on themselves);
    the service guard is the second layer behind it."""
    from apps.accounts.models import StaffProfile
    from apps.accounts.services.staff_admin import _guard_last_owner
    from common.exceptions import ApiProblem

    with pytest.raises(ApiProblem) as exc:
        _guard_last_owner(StaffProfile.objects.select_related("account").get(account=owner.account))
    assert exc.value.get_codes() == "last-owner"


def test_role_change_applies_on_the_next_request(owner_client, db):
    support = make_staff(RoleCode.SUPPORT)
    client = sign_in(support)
    assert client.get(f"{STAFF}/audit-log").status_code == 403
    r = owner_client.put(f"{STAFF}/accounts/{support.account.pk}/role", {"role": "accountant"}, format="json")
    assert r.status_code == 200
    assert client.get(f"{STAFF}/audit-log").status_code == 200
    log = AuditLog.objects.get(action="staff.role_changed")
    assert log.before == {"role": "support"} and log.after == {"role": "accountant"}


def test_revoking_sessions_needs_no_step_up_for_fast_containment(owner_client, db):
    from apps.accounts.models import StaffSession

    support = make_staff(RoleCode.SUPPORT)
    sign_in(support)
    StaffSession.objects.filter(account__email="owner@aurevon.test").update(stepped_up_at=None)
    r = owner_client.post(f"{STAFF}/accounts/{support.account.pk}/sessions/revoke")
    assert r.status_code == 200 and r.json() == {"revoked": 1}


def test_staff_password_reset_needs_the_authenticator_too(owner):
    client = APIClient()
    assert client.post(f"{STAFF}/auth/password-reset", {"email": owner.account.email}, format="json").status_code == 202
    assert (
        client.post(f"{STAFF}/auth/password-reset", {"email": "ghost@aurevon.test"}, format="json").status_code == 202
    )
    token = link_token(last_mail_to(owner.account.email))
    row = AccountToken.objects.get(purpose="staff_password_reset")
    assert row.expires_at - timezone.now() <= timedelta(minutes=30)
    # email link alone is refused
    r = client.post(f"{STAFF}/auth/password-reset/confirm", {"token": token, "password": NEW_PASSWORD}, format="json")
    assert r.status_code == 400
    r = client.post(
        f"{STAFF}/auth/password-reset/confirm",
        {"token": token, "password": NEW_PASSWORD, "code": "000000"},
        format="json",
    )
    assert r.status_code == 400
    open_session = sign_in(owner)
    r = client.post(
        f"{STAFF}/auth/password-reset/confirm",
        {"token": token, "password": NEW_PASSWORD, "code": owner.code()},
        format="json",
    )
    assert r.status_code == 204
    assert open_session.get(f"{STAFF}/auth/session").status_code == 401
    r = client.post(f"{STAFF}/auth/login", {"email": owner.account.email, "password": PASSWORD}, format="json")
    assert r.status_code == 401
    assert mail.outbox[-1].subject.endswith("password was changed")


def test_audit_log_is_append_only_in_the_database(owner_client):
    from django.db import DatabaseError, transaction

    log = AuditLog.objects.first()
    assert log is not None
    with pytest.raises(DatabaseError), transaction.atomic():
        AuditLog.objects.filter(pk=log.pk).update(action="tampered")
    with pytest.raises(DatabaseError), transaction.atomic():
        AuditLog.objects.filter(pk=log.pk).delete()


def test_audit_log_access_by_role(owner_client, db):
    assert owner_client.get(f"{STAFF}/audit-log").status_code == 200
    assert sign_in(make_staff(RoleCode.ACCOUNTANT)).get(f"{STAFF}/audit-log").status_code == 200
    assert sign_in(make_staff(RoleCode.STORE_ADMIN)).get(f"{STAFF}/audit-log").status_code == 200
    assert sign_in(make_staff(RoleCode.SUPPORT)).get(f"{STAFF}/audit-log").status_code == 403
    page = owner_client.get(f"{STAFF}/audit-log?action=staff.sign_in").json()
    assert page["results"] and all(row["action"] == "staff.sign_in" for row in page["results"])


def test_settings_store_vs_security(owner_client, db):
    admin_client = sign_in(make_staff(RoleCode.STORE_ADMIN))
    r = admin_client.put(f"{STAFF}/settings/store.support_email", {"value": "help@aurevon.pk"}, format="json")
    assert r.status_code == 200
    threshold = {"value": {"amount": "25000.00", "currency": "PKR"}}
    assert (
        admin_client.put(f"{STAFF}/settings/refunds.dual_approval_threshold", threshold, format="json").status_code
        == 403
    )
    assert (
        owner_client.put(f"{STAFF}/settings/refunds.dual_approval_threshold", threshold, format="json").status_code
        == 200
    )
    bad = {"value": {"amount": "12.345", "currency": "PKR"}}
    assert owner_client.put(f"{STAFF}/settings/refunds.dual_approval_threshold", bad, format="json").status_code == 400
    listed = {row["key"]: row for row in admin_client.get(f"{STAFF}/settings").json()}
    assert listed["refunds.dual_approval_threshold"]["editable"] is False
    assert listed["refunds.dual_approval_threshold"]["value"] == {"amount": "25000.00", "currency": "PKR"}
    assert sign_in(make_staff(RoleCode.SUPPORT)).get(f"{STAFF}/settings").status_code == 403
