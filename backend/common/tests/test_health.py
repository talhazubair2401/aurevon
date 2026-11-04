import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_live_is_ok_without_touching_dependencies(client, monkeypatch):
    monkeypatch.setattr("common.views._check_database", lambda: pytest.fail("live must not check the DB"))
    response = client.get(reverse("health-live"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-cache" in response["Cache-Control"]


def test_ready_when_database_and_redis_answer(client):
    response = client.get(reverse("health-ready"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


def test_not_ready_when_redis_is_down(client, settings):
    settings.REDIS_URL = "redis://127.0.0.1:1/0"
    response = client.get(reverse("health-ready"))
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "failed"}


def test_not_ready_when_database_is_down(client, monkeypatch):
    def broken_cursor(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("common.views.connection.cursor", broken_cursor)
    response = client.get(reverse("health-ready"))
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "failed"


def test_health_rejects_writes(client):
    assert client.post(reverse("health-live")).status_code == 405
