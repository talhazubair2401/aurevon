from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account, AccountType, CustomerSession
from apps.accounts.services import sessions
from apps.accounts.services.customers import required_delay
from apps.accounts.tests.factories import last_mail_to, link_token

pytestmark = pytest.mark.django_db
EMAIL = "shopper@aurevon.test"
PASSWORD = "silk and linen 2026"


def register(email: str = EMAIL, password: str = PASSWORD):
    return APIClient().post("/api/v1/auth/register", {"email": email, "password": password}, format="json")


def sign_in(remember: bool = False, client: APIClient | None = None):
    client = client or APIClient()
    r = client.post("/api/v1/auth/login", {"email": EMAIL, "password": PASSWORD, "remember": remember}, format="json")
    if r.status_code == 200:
        client.credentials(HTTP_X_CSRF_TOKEN=r.json()["csrf_token"])
    return client, r


def test_registration_always_answers_the_same(db):
    first, again = register(), register()
    assert first.status_code == again.status_code == 202 and first.json() == again.json()
    assert Account.objects.filter(email=EMAIL, account_type=AccountType.CUSTOMER).count() == 1
    assert "already have an AureVon account" in last_mail_to(EMAIL)


def test_email_verification(db):
    register()
    token = link_token(str(mail.outbox[0].body))
    assert APIClient().post("/api/v1/auth/verify", {"token": token}, format="json").status_code == 204
    _, r = sign_in()
    assert r.json()["account"]["email_verified"] is True


def test_customer_password_rules(db):
    assert register(password="short1").status_code == 400
    assert register(password="password123").status_code == 400  # common password
    assert register(password="ten chars!").status_code == 202


def test_browser_session_vs_remember_me(db):
    register()
    client, _ = sign_in(remember=False)
    cookie = client.cookies[sessions.CUSTOMER_COOKIE]
    assert cookie["max-age"] == ""  # ends with the browser
    session = CustomerSession.objects.get()
    assert session.expires_at - session.last_seen_at == timedelta(hours=24)

    client, _ = sign_in(remember=True)
    cookie = client.cookies[sessions.CUSTOMER_COOKIE]
    assert int(cookie["max-age"]) == 30 * 24 * 3600
    session = CustomerSession.objects.get(persistent=True)
    assert session.expires_at - session.last_seen_at == timedelta(days=90)


def test_remember_me_is_rolling_but_never_past_90_days(db):
    register()
    client, _ = sign_in(remember=True)
    CustomerSession.objects.update(
        last_seen_at=timezone.now() - timedelta(days=29), expires_at=timezone.now() + timedelta(days=5)
    )
    r = client.get("/api/v1/auth/session")
    assert r.status_code == 200
    assert int(r.cookies[sessions.CUSTOMER_COOKIE]["max-age"]) <= 5 * 24 * 3600


def test_customers_see_and_revoke_their_sessions(db):
    register()
    phone, _ = sign_in(remember=True)
    laptop, _ = sign_in()
    tablet, _ = sign_in()
    rows = laptop.get("/api/v1/me/sessions").json()
    assert len(rows) == 3 and sum(r["current"] for r in rows) == 1
    phone_id = next(r["id"] for r in phone.get("/api/v1/me/sessions").json() if r["current"])
    assert laptop.delete(f"/api/v1/me/sessions/{phone_id}").status_code == 204
    assert phone.get("/api/v1/auth/session").status_code == 401
    assert laptop.post("/api/v1/me/sessions/revoke-others").json() == {"revoked": 1}
    assert tablet.get("/api/v1/auth/session").status_code == 401
    assert laptop.get("/api/v1/auth/session").status_code == 200


def test_a_customer_cannot_revoke_someone_elses_session(db):
    register()
    register("other@aurevon.test")
    mine, _ = sign_in()
    other = APIClient()
    r = other.post("/api/v1/auth/login", {"email": "other@aurevon.test", "password": PASSWORD}, format="json")
    other_id = r.json()["session"]["id"]
    assert mine.delete(f"/api/v1/me/sessions/{other_id}").status_code == 404


def test_growing_delays_after_five_failures_but_no_hard_lockout(db):
    register()
    for _ in range(5):
        assert (
            APIClient()
            .post("/api/v1/auth/login", {"email": EMAIL, "password": "nope nope nope"}, format="json")
            .status_code
            == 401
        )
    APIClient().post("/api/v1/auth/login", {"email": EMAIL, "password": "nope nope nope"}, format="json")
    _, r = sign_in()
    assert r.status_code == 429 and 0 < int(r["Retry-After"]) <= 60
    assert [required_delay(n) for n in (4, 5, 6, 7, 20)] == [0, 30, 60, 120, 900]


def test_password_reset_signs_out_everywhere(db):
    register()
    client, _ = sign_in(remember=True)
    APIClient().post("/api/v1/auth/password-reset", {"email": EMAIL}, format="json")
    token = link_token(last_mail_to(EMAIL))
    r = APIClient().post(
        "/api/v1/auth/password-reset/confirm", {"token": token, "password": "a new linen password"}, format="json"
    )
    assert r.status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401
    assert APIClient().post("/api/v1/auth/password-reset", {"email": "ghost@x.test"}, format="json").status_code == 202


def test_customer_logout(db):
    register()
    client, _ = sign_in()
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401
