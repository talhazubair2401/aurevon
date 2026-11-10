"""M12 contact form and support tickets: public form, private ticket link, staff replies and notes, dashboard."""

import re
from typing import Any

import pytest
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import STAFF, make_staff, sign_in
from apps.notifications.models import StaffAlert
from apps.orders.tests.test_commerce import customer
from apps.support.models import Ticket

pytestmark = pytest.mark.django_db
FORM = {
    "name": "Ayesha Khan",
    "email": "Ayesha@Example.pk",
    "phone": "0300 1234567",
    "category": "delivery",
    "subject": "Where is my parcel?",
    "message": "My order hasn't arrived yet, can you check?",
    "order_number": "AV100001",
}


@pytest.fixture(autouse=True)
def fresh_limits() -> None:
    cache.clear()


def token_from(body: Any) -> str:
    m = re.search(r"#token=([A-Za-z0-9_\-]+)", str(body))
    assert m, body
    return m.group(1)


def test_contact_opens_a_ticket_and_the_private_link_shows_it() -> None:
    r = APIClient().post("/api/v1/contact", FORM, format="json")
    assert r.status_code == 201 and r.json()["number"] == "T-000001"
    t = Ticket.objects.get()
    assert t.email == "ayesha@example.pk" and t.phone == "+923001234567" and t.account is None
    assert StaffAlert.objects.filter(kind="ticket_new", resolved_at__isnull=True).exists()
    token = token_from(mail.outbox[-1].body)
    shown = APIClient().post("/api/v1/support/ticket", {"token": token}, format="json").json()
    assert shown["subject"] == "Where is my parcel?" and len(shown["messages"]) == 1
    assert APIClient().post("/api/v1/support/ticket", {"token": "nope"}, format="json").status_code == 404
    bad = {**FORM, "message": "short"}
    assert APIClient().post("/api/v1/contact", bad, format="json").status_code == 400


def test_honeypot_and_rate_limit() -> None:
    assert APIClient().post("/api/v1/contact", {**FORM, "website": "http://spam"}, format="json").status_code == 201
    assert Ticket.objects.count() == 0
    codes = [APIClient().post("/api/v1/contact", FORM, format="json").status_code for _ in range(6)]
    assert codes[:4] == [201] * 4 and codes[-1] == 429


def test_signed_in_ticket_is_linked_to_the_account() -> None:
    s = customer("ayesha@example.pk")
    assert s.c.post("/api/v1/contact", FORM, format="json").status_code == 201
    assert s.c.get("/api/v1/me/tickets").json()[0]["number"] == "T-000001"


def test_staff_reply_note_close_and_customer_reopens() -> None:
    APIClient().post("/api/v1/contact", FORM, format="json")
    old_token = token_from(mail.outbox[-1].body)
    support = sign_in(make_staff(RoleCode.SUPPORT, "help@aurevon.test"))
    listing = support.get(f"{STAFF}/tickets", {"status": "open"}).json()
    assert listing["counts"]["open"] == 1
    tid = listing["results"][0]["id"]
    url = f"{STAFF}/tickets/{tid}"
    support.post(f"{url}/messages", {"kind": "note", "body": "Courier says Tuesday"}, format="json")
    sent_before = len(mail.outbox)
    r = support.post(
        f"{url}/messages", {"kind": "staff", "body": "It arrives on Tuesday.", "close": True}, format="json"
    )
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["assigned_to_me"]
    assert len(mail.outbox) == sent_before + 1  # the note sent nothing; the reply one email
    assert "It arrives on Tuesday." in mail.outbox[-1].body
    assert not StaffAlert.objects.filter(kind="ticket_new", resolved_at__isnull=True).exists()

    token = token_from(mail.outbox[-1].body)
    assert APIClient().post("/api/v1/support/ticket", {"token": old_token}, format="json").status_code == 404
    seen = APIClient().post("/api/v1/support/ticket", {"token": token}, format="json").json()
    assert [m["kind"] for m in seen["messages"]] == ["customer", "staff"]  # no internal note
    assert seen["messages"][1]["author"] == "AureVon"
    reply = APIClient().post("/api/v1/support/ticket/reply", {"token": token, "message": "Thank you!"}, format="json")
    assert reply.json()["status"] == "open"
    staff_view = support.get(url).json()
    assert [m["kind"] for m in staff_view["messages"]] == ["customer", "note", "staff", "customer"]

    summary = support.get(f"{STAFF}/support/summary").json()
    assert summary["tickets_open"] == 1 and summary["tickets_mine"] == 1 and summary["returns_requested"] == 0
    assert summary["refunds_waiting"] == 0


def test_permissions() -> None:
    assert sign_in(make_staff(RoleCode.INVENTORY_MANAGER)).get(f"{STAFF}/tickets").status_code == 403
    APIClient().post("/api/v1/contact", FORM, format="json")
    accountant = sign_in(make_staff(RoleCode.ACCOUNTANT))
    tid = accountant.get(f"{STAFF}/tickets").json()["results"][0]["id"]
    r = accountant.post(f"{STAFF}/tickets/{tid}/messages", {"kind": "staff", "body": "x"}, format="json")
    assert r.status_code == 403  # tickets.view only
    s: Any = accountant.get(f"{STAFF}/support/summary").json()
    assert s["tickets_open"] == 1
