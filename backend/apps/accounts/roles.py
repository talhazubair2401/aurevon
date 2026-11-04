from typing import Any

from django.db import transaction

from .models import Role, RolePermission
from .permissions import ROLE_NAMES, ROLE_PERMISSIONS


@transaction.atomic
def sync_system_roles(**_: Any) -> None:
    """Make the six system roles in the database match `permissions.ROLE_PERMISSIONS` exactly."""
    for code, perms in ROLE_PERMISSIONS.items():
        role, _created = Role.objects.update_or_create(
            code=code.value, defaults={"name": ROLE_NAMES[code], "is_system": True}
        )
        wanted = {p.value for p in perms}
        RolePermission.objects.filter(role=role).exclude(permission__in=wanted).delete()
        existing = set(RolePermission.objects.filter(role=role).values_list("permission", flat=True))
        RolePermission.objects.bulk_create([RolePermission(role=role, permission=p) for p in sorted(wanted - existing)])
