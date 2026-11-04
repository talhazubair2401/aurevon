"""Who may do what. Permissions are read from the database on every request, so a role change
applies on the next request (MTS §9). Nothing consults Django's `is_superuser`."""

from datetime import datetime

from django.utils import timezone

from .. import policy
from ..models import Account, AccountStatus, AccountType, RolePermission, StaffProfile, StaffSession
from ..permissions import PRIVILEGED_ROLES, Perm, RoleCode


def role_of(account: Account) -> str | None:
    if account.account_type != AccountType.STAFF:
        return None
    return StaffProfile.objects.filter(account=account).values_list("role_id", flat=True).first()


def permissions_for(account: Account) -> frozenset[str]:
    if account.account_type != AccountType.STAFF or account.status != AccountStatus.ACTIVE:
        return frozenset()
    rows = RolePermission.objects.filter(role__members__account=account).values_list("permission", flat=True)
    return frozenset(rows)


def has_perm(account: Account, perm: Perm) -> bool:
    return perm.value in permissions_for(account)


def stepped_up(session: StaffSession, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    return session.stepped_up_at is not None and now - session.stepped_up_at <= policy.STEP_UP_VALIDITY


def is_privileged(account: Account) -> bool:
    return role_of(account) in PRIVILEGED_ROLES


def active_owner_count() -> int:
    return StaffProfile.objects.filter(role_id=RoleCode.OWNER, account__status=AccountStatus.ACTIVE).count()


def is_owner(account: Account) -> bool:
    return role_of(account) == RoleCode.OWNER
