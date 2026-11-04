import base64

import pytest

from apps.accounts import totp
from apps.accounts.models import Role, RolePermission
from apps.accounts.permissions import ROLE_PERMISSIONS, Perm, RoleCode
from apps.accounts.roles import sync_system_roles

# RFC 6238 Appendix B, SHA-1 secret "12345678901234567890"; 6-digit codes are the last 6 of the 8-digit values.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("unix_time", "expected"),
    [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"), (2000000000, "279037")],
)
def test_totp_matches_rfc_6238_vectors(unix_time, expected):
    assert totp.code_at(RFC_SECRET, unix_time // 30) == expected


def test_totp_accepts_one_step_of_drift_and_refuses_replay():
    now = 1_000_000_000.0
    step = totp.current_step(now)
    secret = totp.new_secret()
    assert totp.matching_step(secret, totp.code_at(secret, step - 1), 0, now) == step - 1
    assert totp.matching_step(secret, totp.code_at(secret, step + 1), 0, now) == step + 1
    assert totp.matching_step(secret, totp.code_at(secret, step - 2), 0, now) is None
    # A code whose step was already used is refused (decision 0003, 2.4).
    assert totp.matching_step(secret, totp.code_at(secret, step), step, now) is None
    assert totp.matching_step(secret, "12345", 0, now) is None


def test_totp_secret_is_encrypted_at_rest():
    secret = totp.new_secret()
    stored = totp.encrypt_secret(secret)
    assert secret not in stored
    assert totp.decrypt_secret(stored) == secret


def test_qr_code_is_inline_svg():
    svg = totp.qr_svg(totp.provisioning_uri(totp.new_secret(), "a@b.test"))
    assert svg.startswith("<svg") and "http" not in svg.split("xmlns")[0]


pytestmark = pytest.mark.django_db


def _perms(role: RoleCode) -> set[str]:
    return set(RolePermission.objects.filter(role_id=role).values_list("permission", flat=True))


def test_six_fixed_roles_exist_and_match_the_code():
    assert set(Role.objects.values_list("code", flat=True)) == {r.value for r in RoleCode}
    for role, perms in ROLE_PERMISSIONS.items():
        assert _perms(role) == {p.value for p in perms}


def test_sync_removes_permissions_added_outside_the_code():
    RolePermission.objects.create(role_id=RoleCode.SUPPORT, permission=Perm.REFUNDS_APPROVE)
    sync_system_roles()
    assert Perm.REFUNDS_APPROVE not in _perms(RoleCode.SUPPORT)


def test_owner_has_every_permission():
    assert _perms(RoleCode.OWNER) == {p.value for p in Perm}


@pytest.mark.parametrize(
    ("role", "has", "lacks"),
    [
        # Decision 0003, 1.3: Store Admin limits
        (
            RoleCode.STORE_ADMIN,
            {Perm.STAFF_SUSPEND, Perm.SETTINGS_STORE, Perm.REFUNDS_REQUEST, Perm.REPORTS_AGGREGATE, Perm.AUDIT_VIEW},
            {
                Perm.STAFF_SUSPEND_PRIVILEGED,
                Perm.STAFF_REACTIVATE,
                Perm.STAFF_INVITE,
                Perm.STAFF_MANAGE_ROLES,
                Perm.STAFF_RECOVER,
                Perm.SETTINGS_SECURITY,
                Perm.REPORTS_EXPORT_PERSONAL,
                Perm.REFUNDS_APPROVE,
            },
        ),
        # 1.4: refunds are requested by Admin and Support, approved by Accountant and Owner
        (
            RoleCode.ACCOUNTANT,
            {Perm.REFUNDS_APPROVE, Perm.REMITTANCE_RECONCILE},
            {Perm.REFUNDS_REQUEST, Perm.PRICES_EDIT},
        ),
        (RoleCode.SUPPORT, {Perm.REFUNDS_REQUEST, Perm.TICKETS_HANDLE}, {Perm.REFUNDS_APPROVE, Perm.AUDIT_VIEW}),
        (RoleCode.CONTENT_MARKETING, {Perm.CATALOG_EDIT, Perm.CMS_PUBLISH}, {Perm.CATALOG_PUBLISH, Perm.PRICES_VIEW}),
        (
            RoleCode.INVENTORY_MANAGER,
            {Perm.INVENTORY_ADJUST, Perm.CATALOG_VIEW},
            {Perm.CATALOG_EDIT, Perm.ORDERS_UPDATE},
        ),
    ],
)
def test_role_matrix_cells(role, has, lacks):
    perms = _perms(role)
    assert {p.value for p in has} <= perms
    assert not ({p.value for p in lacks} & perms)
