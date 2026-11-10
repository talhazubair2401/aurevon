"""Support tickets (M12). Customer messages arrive by the contact form or the private ticket link; staff replies
are emailed with that link. Internal notes stay inside the staff screens."""

from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.notifications.services import alert, send_email
from common.exceptions import ApiProblem
from common.security import new_token, token_hash

from .models import MessageKind, Ticket, TicketCategory, TicketMessage, TicketStatus


def _next_number() -> str:
    last = Ticket.objects.select_for_update().order_by("-number").values_list("number", flat=True).first()
    n = int(last.split("-")[1]) + 1 if last else 1
    return f"T-{n:06d}"


def link(ticket: Ticket, token: str) -> str:
    return f"{settings.SITE_URL}/{ticket.locale}/support/ticket#token={token}"


def _rotate(ticket: Ticket) -> str:
    """Each email carries a fresh link; older links stop working, so a forwarded old email can't be used."""
    token = new_token()
    ticket.access_token_hash = token_hash(token)
    ticket.save(update_fields=["access_token_hash", "updated_at"])
    return token


@transaction.atomic
def open_ticket(
    *,
    name: str,
    email: str,
    phone: str,
    category: str,
    subject: str,
    body: str,
    order_number: str,
    locale: str,
    account: Any = None,
) -> Ticket:
    if category not in TicketCategory.values:
        raise ApiProblem(400, "category", "Choose what your message is about.")
    token = new_token()
    ticket = Ticket.objects.create(
        number=_next_number(),
        category=category,
        subject=subject.strip()[:150],
        name=name.strip()[:120],
        email=email.strip().lower(),
        phone=phone,
        locale=locale,
        order_number=order_number.strip().upper()[:20],
        account=account,
        access_token_hash=token_hash(token),
    )
    TicketMessage.objects.create(ticket=ticket, kind=MessageKind.CUSTOMER, author=ticket.email, body=body.strip())
    alert(
        "ticket_new",
        f"New message {ticket.number}: {ticket.subject}",
        severity="info",
        target_type="ticket",
        target_id=ticket.pk,
    )
    send_email(
        [ticket.email],
        "ticket_received",
        {"number": ticket.number, "subject": ticket.subject, "link": link(ticket, token)},
    )
    return ticket


def by_token(token: str) -> Ticket:
    ticket = Ticket.objects.filter(access_token_hash=token_hash(token)).first() if token else None
    if ticket is None:
        raise ApiProblem(404, "not-found", "This link isn't valid any more. Use the newest email we sent.")
    return ticket


@transaction.atomic
def customer_reply(ticket: Ticket, body: str) -> Ticket:
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    TicketMessage.objects.create(ticket=ticket, kind=MessageKind.CUSTOMER, author=ticket.email, body=body.strip())
    ticket.status = TicketStatus.OPEN
    ticket.closed_at = None
    ticket.save(update_fields=["status", "closed_at", "updated_at"])
    alert(
        "ticket_reply",
        f"{ticket.number}: the customer replied",
        severity="info",
        target_type="ticket",
        target_id=ticket.pk,
        dedupe_key=f"ticket_reply:{ticket.pk}",
    )
    return ticket


def _resolve_alerts(ticket: Ticket, actor_label: str) -> None:
    from apps.notifications.models import StaffAlert

    StaffAlert.objects.filter(
        kind__in=["ticket_new", "ticket_reply"], target_id=str(ticket.pk), resolved_at__isnull=True
    ).update(resolved_at=timezone.now(), resolved_by=actor_label)


@transaction.atomic
def staff_message(
    ticket_id: Any, kind: str, body: str, actor: Actor, *, close: bool = False, request: Any = None
) -> Ticket:
    ticket = Ticket.objects.select_for_update().filter(pk=ticket_id).first()
    if ticket is None:
        raise ApiProblem(404, "not-found", "No such ticket.")
    if kind not in (MessageKind.STAFF, MessageKind.NOTE):
        raise ApiProblem(400, "kind", "Reply to the customer or add an internal note.")
    body = body.strip()
    if not body:
        raise ApiProblem(400, "body", "Write a message.")
    TicketMessage.objects.create(ticket=ticket, kind=kind, author=actor.label, body=body[:4000])
    if kind == MessageKind.STAFF:
        ticket.status = TicketStatus.CLOSED if close else TicketStatus.WAITING
        ticket.closed_at = timezone.now() if close else None
        if ticket.assigned_to_id is None and actor.id is not None:
            ticket.assigned_to_id = actor.id
        ticket.save(update_fields=["status", "closed_at", "assigned_to", "updated_at"])
        token = _rotate(ticket)
        send_email(
            [ticket.email],
            "ticket_reply",
            {
                "number": ticket.number,
                "subject": ticket.subject,
                "body": body,
                "link": link(ticket, token),
                "closed": close,
            },
        )
        _resolve_alerts(ticket, actor.label)
    record(
        f"ticket.{kind}",
        actor,
        target_type="ticket",
        target_id=ticket.number,
        after={"close": close} if kind == MessageKind.STAFF else None,
        request=request,
    )
    return ticket


@transaction.atomic
def set_state(ticket_id: Any, *, status: str | None, assign: Any, actor: Actor, request: Any = None) -> Ticket:
    ticket = Ticket.objects.select_for_update().filter(pk=ticket_id).first()
    if ticket is None:
        raise ApiProblem(404, "not-found", "No such ticket.")
    fields = ["updated_at"]
    if status is not None:
        if status not in TicketStatus.values:
            raise ApiProblem(400, "status", "Unknown status.")
        ticket.status = status
        ticket.closed_at = timezone.now() if status == TicketStatus.CLOSED else None
        fields += ["status", "closed_at"]
        if status == TicketStatus.CLOSED:
            _resolve_alerts(ticket, actor.label)
    if assign is not ...:
        ticket.assigned_to_id = assign
        fields.append("assigned_to")
    ticket.save(update_fields=fields)
    record(
        "ticket.update",
        actor,
        target_type="ticket",
        target_id=ticket.number,
        after={"status": ticket.status, "assigned_to": str(ticket.assigned_to_id or "")},
        request=request,
    )
    return ticket
