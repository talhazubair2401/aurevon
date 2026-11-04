import importlib
import sys

import pytest

from common.tasks import ping


def test_celery_round_trip():
    assert ping.delay().get(timeout=5) == "pong"


TEST_FERNET_KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="  # not a secret


def test_production_settings_are_secure(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "aurevon.example")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db:5432/aurevon")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", TEST_FERNET_KEY)
    for name in ["config.settings.production", "config.settings.base"]:
        sys.modules.pop(name, None)
    prod = importlib.import_module("config.settings.production")
    assert prod.MFA_ENCRYPTION_KEY == TEST_FERNET_KEY
    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE
    assert prod.SECURE_HSTS_SECONDS >= 31536000
    assert prod.API_SCHEMA_PUBLIC is False
    assert prod.ALLOWED_HOSTS == ["aurevon.example"]
    assert prod.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")


def test_production_requires_mfa_encryption_key(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "aurevon.example")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db:5432/aurevon")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.delenv("MFA_ENCRYPTION_KEY", raising=False)
    for name in ["config.settings.production", "config.settings.base"]:
        sys.modules.pop(name, None)
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.production")


def test_production_requires_allowed_hosts(monkeypatch):
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x" * 50)
    monkeypatch.delenv("DJANGO_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db:5432/aurevon")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    for name in ["config.settings.production", "config.settings.base"]:
        sys.modules.pop(name, None)
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured):
        importlib.import_module("config.settings.production")
