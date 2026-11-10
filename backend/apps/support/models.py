"""Customer support tickets (MTS §6 "Support"; M12): from the contact form or a signed-in account, answered by
staff by email, with a private link for the customer to read the thread and reply."""

import uuid

from django.db import models
from django.db.models import Q


class TicketCategory(models.TextChoices):
    ORDER = "order", "An order"
    DELIVERY = "delivery", "Delivery"
    RETURN = "return", "Returns and exchanges"
    PAYMENT = "payment", "Payment or refund"
    PRODUCT = "product", "A product or sizing"
    OTHER = "other", "Something else"


class TicketStatus(models.TextChoices):
    OPEN = "open", "Waiting for us"
    WAITING = "waiting", "Waiting for the customer"
    CLOSED = "closed", "Closed"


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=12, unique=True)  # T-000001
    category = models.CharField(max_length=10, choices=TicketCategory.choices)
    subject = models.CharField(max_length=150)
    status = models.CharField(max_length=10, choices=TicketStatus.choices, default=TicketStatus.OPEN)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    locale = models.CharField(max_length=5, default="en")
    order_number = models.CharField(max_length=20, blank=True)
    account = models.ForeignKey(
        "accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets"
    )
    assigned_to = models.ForeignKey(
        "accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets"
    )
    access_token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["status", "-updated_at"]), models.Index(fields=["access_token_hash"])]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=TicketStatus.values), name="ticket_status_valid"),
            models.CheckConstraint(condition=Q(category__in=TicketCategory.values), name="ticket_category_valid"),
        ]

    def __str__(self) -> str:
        return self.number


class MessageKind(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff reply"
    NOTE = "note", "Internal note"  # never shown to or emailed to the customer


class TicketMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    kind = models.CharField(max_length=10, choices=MessageKind.choices)
    author = models.CharField(max_length=254)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.CheckConstraint(condition=Q(kind__in=MessageKind.values), name="ticket_message_kind")]

    def __str__(self) -> str:
        return f"{self.ticket_id}:{self.kind}"
