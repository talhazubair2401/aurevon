"""Automated tests. Runs against a real PostgreSQL, never SQLite (MTS §13)."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")
os.environ.setdefault("DATABASE_URL", "postgres://aurevon:aurevon@localhost:5432/aurevon")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from .base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver", "localhost"]
API_SCHEMA_PUBLIC = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only; tests never ship
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "aurevon-tests"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SITE_URL = "https://aurevon.test"
