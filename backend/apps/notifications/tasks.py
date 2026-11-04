from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def render(template: str, context: dict[str, Any]) -> tuple[str, str]:
    """Templates live in templates/email/<name>.txt; the first line is `Subject: ...`."""
    text = render_to_string(f"email/{template}.txt", {**context, "site_name": "AureVon"})
    first, _, body = text.partition("\n")
    if not first.startswith("Subject: "):
        raise ValueError(f"email/{template}.txt must start with a Subject line")
    return first.removeprefix("Subject: ").strip(), body.lstrip("\n")


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=5)  # type: ignore[untyped-decorator]
def send_templated_email(to: list[str], template: str, context: dict[str, Any]) -> None:
    subject, body = render(template, context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to)
