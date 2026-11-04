"""The one way to write the audit log. Other apps call `record`; they never touch the model."""

import uuid
from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest

from common.request_context import request_id_var
from common.security import client_ip, user_agent

from .models import AuditLog


@dataclass(frozen=True)
class Actor:
    """Who did it. `id` is None for the system or a break-glass operator."""

    id: uuid.UUID | None
    label: str


SYSTEM = Actor(None, "system")


def record(
    action: str,
    actor: Actor,
    *,
    target_type: str = "",
    target_id: str | uuid.UUID = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        actor_id=actor.id,
        actor_label=actor.label[:254],
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        before=before,
        after=after,
        ip=client_ip(request) if request is not None else None,
        user_agent=user_agent(request) if request is not None else "",
        request_id=request_id_var.get() or "",
    )
