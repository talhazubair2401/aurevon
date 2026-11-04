"""Transactional email. Messages are queued only after the surrounding transaction commits (MTS §5),
so a rolled-back change never sends anything. The full outbox and delivery tracking arrive with M8."""

from typing import Any

from django.db import transaction

from .tasks import send_templated_email


def send_email(to: list[str], template: str, context: dict[str, Any]) -> None:
    recipients = sorted({address for address in to if address})
    if not recipients:
        return
    transaction.on_commit(lambda: send_templated_email.delay(recipients, template, context), robust=True)
