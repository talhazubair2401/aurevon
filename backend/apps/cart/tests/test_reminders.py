"""M11 consent-based messages: preferences, abandoned-bag reminders, one-click unsubscribe, order-update SMS."""

import re
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.cart import services as cart
from apps.cart.models import Cart
from apps.notifications.models import ConsentRecord
from apps.orders.tests.test_commerce import customer, sku_with_stock

pytestmark = pytest.mark.django_db
EMAIL = "ayesha@example.pk"


@pytest.fixture(autouse=True)
def demo(settings: Any) -> None:
    settings.ALLOW_DEMO_DATA = True
    call_command("seed_demo_catalog", stdout=open("/dev/null", "w"))  # noqa: SIM115


def verified_customer() -> Any:
    shopper = customer(EMAIL)
    Account.objects.filter(email=EMAIL).update(email_verified_at=timezone.now())
    return shopper


def age_bag(hours: float) -> None:
    Cart.objects.filter(account__email=EMAIL).update(updated_at=timezone.now() - timedelta(hours=hours))


def test_preferences_need_a_verified_email_and_a_phone_for_sms() -> None:
    shopper = customer(EMAIL)
    prefs = shopper.c.get("/api/v1/me/preferences").json()
    assert prefs == {
        "newsletter": "none",
        "cart_reminders": False,
        "sms_updates": False,
        "email_verified": False,
        "has_phone": False,
    }
    assert shopper.c.put("/api/v1/me/preferences", {"cart_reminders": True}, format="json").status_code == 400
    Account.objects.filter(email=EMAIL).update(email_verified_at=timezone.now())
    assert shopper.c.put("/api/v1/me/preferences", {"sms_updates": True}, format="json").status_code == 400
    shopper.c.patch("/api/v1/me", {"phone": "0300 1234567"}, format="json")
    r = shopper.c.put(
        "/api/v1/me/preferences", {"cart_reminders": True, "sms_updates": True, "newsletter": True}, format="json"
    )
    assert r.status_code == 200
    assert r.json()["cart_reminders"] and r.json()["sms_updates"] and r.json()["newsletter"] == "pending"
    record = ConsentRecord.objects.get(email=EMAIL, purpose="cart_reminders")
    assert record.status == "confirmed" and record.wording_version and record.source == "account"
    r = shopper.c.put("/api/v1/me/preferences", {"cart_reminders": False}, format="json")
    assert r.json()["cart_reminders"] is False
    assert APIClient().get("/api/v1/me/preferences").status_code in (401, 403)


def test_reminder_goes_once_only_to_consenting_customers_and_unsubscribe_stops_it() -> None:
    shopper = verified_customer()
    shopper.add(sku_with_stock(5))
    age_bag(30)
    assert cart.send_reminders() == 0  # no consent, no email
    shopper.c.put("/api/v1/me/preferences", {"cart_reminders": True}, format="json")
    age_bag(2)
    assert cart.send_reminders() == 0  # too soon
    age_bag(30)
    mail.outbox.clear()
    assert cart.send_reminders() == 1
    message = mail.outbox[-1]
    assert message.to == [EMAIL] and "bag is waiting" in message.subject and "/en/cart" in message.body
    assert cart.send_reminders() == 0  # once per bag change

    shopper.add(sku_with_stock(5, skip=1))  # changing the bag restarts the clock
    age_bag(30)
    assert cart.send_reminders() == 1

    token = re.search(r"unsubscribe#token=(\S+)", str(message.body))
    assert token
    r = APIClient().post("/api/v1/unsubscribe", {"token": token.group(1)}, format="json")
    assert r.status_code == 200 and r.json()["purpose"] == "cart_reminders"
    assert APIClient().post("/api/v1/unsubscribe", {"token": "forged"}, format="json").status_code == 400
    Cart.objects.update(reminded_at=None)
    age_bag(30)
    assert cart.send_reminders() == 0
    assert shopper.c.get("/api/v1/me/preferences").json()["cart_reminders"] is False


def test_no_reminder_after_ordering_or_for_stale_bags() -> None:
    shopper = verified_customer()
    shopper.c.put("/api/v1/me/preferences", {"cart_reminders": True}, format="json")
    shopper.add(sku_with_stock(5))
    age_bag(24 * 10)
    assert cart.send_reminders() == 0  # older than the 7-day window
    age_bag(30)
    assert shopper.place().status_code == 201  # placing the order empties the bag
    assert cart.send_reminders() == 0


def test_dispatch_sms_only_with_consent() -> None:
    from apps.notifications import services as notifications

    with mock.patch("apps.notifications.tasks.send_sms.delay") as delay:
        assert notifications.send_sms("+923001234567", "hi", consent_email=EMAIL) is False
        notifications.set_preference(EMAIL, "sms_updates", True, locale="en", source="test")
        with_consent = notifications.send_sms("+923001234567", "hi", consent_email=EMAIL)
    assert with_consent is True
    from integrations import sms

    assert sms.provider().send("+923001234567", "hi").provider == "log"
    assert delay.call_count in (0, 1)  # queued on commit; the test transaction never commits
