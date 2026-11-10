"""Contact form and support tickets (MTS §8; M12).

Public: POST /contact (rate-limited, with a hidden honeypot field) opens a ticket and emails the customer a private
link; /support/ticket reads and replies through that link's token. Signed-in customers' tickets are linked to their
account (/me/tickets).

Staff: /staff/tickets — `tickets.view` reads; `tickets.handle` replies, adds internal notes, assigns and closes.
/staff/support/summary gives the support dashboard its counts (tickets, returns, refunds waiting).
"""

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import CustomerAPIView, StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor
from apps.cart.api.views import CartAPIView
from apps.customers.validators import normalize_phone
from apps.payments.models import Refund, RefundState
from apps.returns.models import ReturnRequest, ReturnStatus
from common.api import LOCALES
from common.exceptions import ApiProblem
from common.security import Limit, client_ip, hit

from .. import services
from ..models import MessageKind, Ticket, TicketCategory, TicketStatus

TAG = ["support"]
STAFF_TAG = ["staff support"]
PER_ADDRESS = Limit(count=5, window=3600)
PER_TICKET = Limit(count=20, window=3600)


class MessageOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=MessageKind.values)
    author = serializers.CharField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()


class TicketOut(serializers.Serializer[Any]):
    number = serializers.CharField()
    category = serializers.ChoiceField(choices=TicketCategory.values)
    subject = serializers.CharField()
    status = serializers.ChoiceField(choices=TicketStatus.values)
    order_number = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    messages = MessageOut(many=True)


def ticket_out(t: Ticket, *, staff: bool = False) -> dict[str, Any]:
    messages = t.messages.all() if staff else t.messages.exclude(kind=MessageKind.NOTE)
    return {
        "number": t.number,
        "category": t.category,
        "subject": t.subject,
        "status": t.status,
        "order_number": t.order_number,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "messages": [
            {
                "id": m.pk,
                "kind": m.kind,
                # Customers see "AureVon" for staff replies, not the staff member's email address.
                "author": m.author if staff or m.kind == MessageKind.CUSTOMER else "AureVon",
                "body": m.body,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }


# --- Public and customer -----------------------------------------------------------------------------------------


class ContactIn(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    category = serializers.ChoiceField(choices=TicketCategory.values)
    subject = serializers.CharField(max_length=150)
    message = serializers.CharField(max_length=4000, min_length=10)
    order_number = serializers.RegexField(r"^(AV\d{6,})?$", required=False, allow_blank=True, default="")
    locale = serializers.ChoiceField(choices=LOCALES, default="en")
    website = serializers.CharField(required=False, allow_blank=True, default="")  # honeypot: people leave it empty

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value) if value.strip() else ""


class ContactOut(serializers.Serializer[Any]):
    number = serializers.CharField()


class ContactView(CartAPIView):
    """Uses the cart view's session handling so a signed-in customer's ticket is linked to their account."""

    @extend_schema(tags=TAG, request=ContactIn, responses={201: ContactOut}, operation_id="contact")
    def post(self, request: Request) -> Response:
        if hit("contact", client_ip(request) or "unknown", PER_ADDRESS) > PER_ADDRESS.count:
            raise ApiProblem(429, "rate-limited", "Too many messages. Please try again later.")
        s = ContactIn(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if d["website"]:
            return Response({"number": "T-000000"}, status=201)  # a bot: looks accepted, stores nothing
        ticket = services.open_ticket(
            name=d["name"],
            email=d["email"],
            phone=d["phone"],
            category=d["category"],
            subject=d["subject"],
            body=d["message"],
            order_number=d["order_number"],
            locale=d["locale"],
            account=self.customer,
        )
        return Response({"number": ticket.number}, status=201)


class SupportTokenIn(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=200)


class TicketReplyIn(SupportTokenIn):
    message = serializers.CharField(max_length=4000)


class TicketByTokenView(CartAPIView):
    """POST (not GET) so the token travels in the body, never in a URL or log."""

    @extend_schema(tags=TAG, request=SupportTokenIn, responses={200: TicketOut}, operation_id="support_ticket_open")
    def post(self, request: Request) -> Response:
        s = SupportTokenIn(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(ticket_out(services.by_token(s.validated_data["token"])))


class TicketReplyView(CartAPIView):
    @extend_schema(tags=TAG, request=TicketReplyIn, responses={200: TicketOut}, operation_id="support_ticket_reply")
    def post(self, request: Request) -> Response:
        s = TicketReplyIn(data=request.data)
        s.is_valid(raise_exception=True)
        ticket = services.by_token(s.validated_data["token"])
        if hit("ticket-reply", str(ticket.pk), PER_TICKET) > PER_TICKET.count:
            raise ApiProblem(429, "rate-limited", "Too many messages. Please try again later.")
        return Response(ticket_out(services.customer_reply(ticket, s.validated_data["message"])))


class MyTicketRowOut(serializers.Serializer[Any]):
    number = serializers.CharField()
    subject = serializers.CharField()
    status = serializers.CharField()
    updated_at = serializers.DateTimeField()


class MyTicketsView(CustomerAPIView):
    @extend_schema(tags=["customer account"], responses={200: MyTicketRowOut(many=True)}, operation_id="me_tickets")
    def get(self, request: Request) -> Response:
        rows = Ticket.objects.filter(account=self.account)[:50]
        return Response(
            [{"number": t.number, "subject": t.subject, "status": t.status, "updated_at": t.updated_at} for t in rows]
        )


# --- Staff ---------------------------------------------------------------------------------------------------


class _SupportView(StaffAPIView):
    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)


class StaffTicketRowOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    number = serializers.CharField()
    subject = serializers.CharField()
    category = serializers.CharField()
    status = serializers.CharField()
    name = serializers.CharField()
    email = serializers.CharField()
    order_number = serializers.CharField()
    assigned_to = serializers.CharField(allow_null=True)
    messages = serializers.IntegerField()
    updated_at = serializers.DateTimeField()


class StaffTicketListOut(serializers.Serializer[Any]):
    results = StaffTicketRowOut(many=True)
    counts = serializers.DictField(child=serializers.IntegerField())


class StaffTicketOut(TicketOut):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    locale = serializers.CharField()
    has_account = serializers.BooleanField()
    assigned_to = serializers.CharField(allow_null=True)
    assigned_to_me = serializers.BooleanField()


def _row(t: Ticket) -> dict[str, Any]:
    return {
        "id": t.pk,
        "number": t.number,
        "subject": t.subject,
        "category": t.category,
        "status": t.status,
        "name": t.name,
        "email": t.email,
        "order_number": t.order_number,
        "assigned_to": t.assigned_to.email if t.assigned_to else None,
        "messages": t.messages.count(),
        "updated_at": t.updated_at,
    }


class TicketsView(_SupportView):
    required_permission = Perm.TICKETS_VIEW

    @extend_schema(
        tags=STAFF_TAG,
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR),
            OpenApiParameter("mine", OpenApiTypes.BOOL),
            OpenApiParameter("q", OpenApiTypes.STR),
        ],
        responses={200: StaffTicketListOut},
        operation_id="staff_tickets",
    )
    def get(self, request: Request) -> Response:
        from django.db.models import Q

        qs = Ticket.objects.select_related("assigned_to")
        counts = {s: qs.filter(status=s).count() for s in TicketStatus.values}
        status = request.query_params.get("status", "")
        if status:
            qs = qs.filter(status=status)
        if request.query_params.get("mine") in ("1", "true"):
            qs = qs.filter(assigned_to=self.account)
        q = request.query_params.get("q", "").strip()[:80]
        if q:
            qs = qs.filter(
                Q(number__iexact=q)
                | Q(email__icontains=q)
                | Q(name__icontains=q)
                | Q(subject__icontains=q)
                | Q(order_number__iexact=q)
            )
        return Response({"results": [_row(t) for t in qs[:200]], "counts": counts})


def _ticket(ticket_id: str) -> Ticket:
    t = Ticket.objects.select_related("assigned_to").filter(pk=ticket_id).first()
    if t is None:
        raise ApiProblem(404, "not-found", "No such ticket.")
    return t


def staff_ticket(view: _SupportView, t: Ticket) -> dict[str, Any]:
    return {
        **ticket_out(t, staff=True),
        "id": t.pk,
        "name": t.name,
        "email": t.email,
        "phone": t.phone,
        "locale": t.locale,
        "has_account": t.account_id is not None,
        "assigned_to": t.assigned_to.email if t.assigned_to else None,
        "assigned_to_me": t.assigned_to_id == view.account.pk,
    }


class TicketUpdateIn(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=TicketStatus.values, required=False)
    assign = serializers.ChoiceField(choices=["me", "nobody"], required=False)


class TicketView(_SupportView):
    required_permission = {"GET": Perm.TICKETS_VIEW, "PATCH": Perm.TICKETS_HANDLE}

    @extend_schema(tags=STAFF_TAG, responses={200: StaffTicketOut}, operation_id="staff_ticket")
    def get(self, request: Request, ticket_id: str) -> Response:
        return Response(staff_ticket(self, _ticket(ticket_id)))

    @extend_schema(
        tags=STAFF_TAG, request=TicketUpdateIn, responses={200: StaffTicketOut}, operation_id="staff_ticket_update"
    )
    def patch(self, request: Request, ticket_id: str) -> Response:
        s = TicketUpdateIn(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        assign: Any = ...
        if "assign" in d:
            assign = self.account.pk if d["assign"] == "me" else None
        services.set_state(
            _ticket(ticket_id).pk, status=d.get("status"), assign=assign, actor=self.actor(), request=request
        )
        return Response(staff_ticket(self, _ticket(ticket_id)))


class TicketMessageIn(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=[MessageKind.STAFF.value, MessageKind.NOTE.value])
    body = serializers.CharField(max_length=4000)
    close = serializers.BooleanField(required=False, default=False)


class TicketMessagesView(_SupportView):
    required_permission = Perm.TICKETS_HANDLE

    @extend_schema(
        tags=STAFF_TAG, request=TicketMessageIn, responses={200: StaffTicketOut}, operation_id="staff_ticket_message"
    )
    def post(self, request: Request, ticket_id: str) -> Response:
        s = TicketMessageIn(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        services.staff_message(
            _ticket(ticket_id).pk, d["kind"], d["body"], self.actor(), close=d["close"], request=request
        )
        return Response(staff_ticket(self, _ticket(ticket_id)))


class SupportSummaryOut(serializers.Serializer[Any]):
    tickets_open = serializers.IntegerField(allow_null=True)
    tickets_mine = serializers.IntegerField(allow_null=True)
    tickets_waiting = serializers.IntegerField(allow_null=True)
    returns_requested = serializers.IntegerField(allow_null=True)
    returns_to_receive = serializers.IntegerField(allow_null=True)
    returns_to_inspect = serializers.IntegerField(allow_null=True)
    returns_to_complete = serializers.IntegerField(allow_null=True)
    refunds_waiting = serializers.IntegerField(allow_null=True)


class SupportSummaryView(_SupportView):
    """Counts for the support dashboard; each figure is null when the role can't see that area."""

    required_permission = Perm.TICKETS_VIEW  # every role with returns.view also has tickets.view

    @extend_schema(tags=STAFF_TAG, responses={200: SupportSummaryOut}, operation_id="staff_support_summary")
    def get(self, request: Request) -> Response:
        a = self.account
        tickets = True
        returns = access.has_perm(a, Perm.RETURNS_VIEW)
        refunds = access.has_perm(a, Perm.ORDERS_VIEW)
        t, r = Ticket.objects, ReturnRequest.objects

        def count(ok: bool, qs: Any) -> int | None:
            return qs.count() if ok else None

        return Response(
            {
                "tickets_open": count(tickets, t.filter(status=TicketStatus.OPEN)),
                "tickets_mine": count(tickets, t.filter(assigned_to=a).exclude(status=TicketStatus.CLOSED)),
                "tickets_waiting": count(tickets, t.filter(status=TicketStatus.WAITING)),
                "returns_requested": count(returns, r.filter(status=ReturnStatus.REQUESTED)),
                "returns_to_receive": count(returns, r.filter(status=ReturnStatus.APPROVED)),
                "returns_to_inspect": count(returns, r.filter(status=ReturnStatus.RECEIVED)),
                "returns_to_complete": count(returns, r.filter(status=ReturnStatus.INSPECTED)),
                "refunds_waiting": count(refunds, Refund.objects.filter(state=RefundState.REQUESTED)),
            }
        )
