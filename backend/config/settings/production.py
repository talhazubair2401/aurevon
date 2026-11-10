"""Production. Everything security-relevant is on by default; hosts and secrets come from the environment."""

import os

from .base import *  # noqa: F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")  # required, no default

# TLS terminates at the CDN / reverse proxy (MTS §14).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# Health checks are called by the platform over the internal network, without TLS.
SECURE_REDIRECT_EXEMPT = [r"^health/"]
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env.bool("DJANGO_HSTS_PRELOAD", default=False)  # on once the domain is stable
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# HSTS preload is switched on once the domain is stable (MTS §12); until then its check is expected to warn.
if not SECURE_HSTS_PRELOAD:
    SILENCED_SYSTEM_CHECKS = [*SILENCED_SYSTEM_CHECKS, "security.W021"]

MFA_ENCRYPTION_KEY = env("MFA_ENCRYPTION_KEY")  # required: Fernet key, see .env.example

# The payment sandbox simulates a provider and would accept fake payments: never in production.
# (Staging imports this module and re-enables the sandbox afterwards, so only real production is checked.)
if os.environ.get("DJANGO_SETTINGS_MODULE") == "config.settings.production":
    if env.bool("PAYMENTS_SANDBOX_ENABLED", default=False):
        raise RuntimeError("PAYMENTS_SANDBOX_ENABLED must not be set in production.")
    PAYMENTS_SANDBOX_ENABLED = False
