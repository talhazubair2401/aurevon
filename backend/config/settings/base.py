"""Settings shared by every environment. Secrets and hosts come only from the environment (MTS §5)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    # Django admin is deliberately not installed: no business operation depends on it (MTS v2.1 R-06).
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "common",
    "apps.audit",
    "apps.notifications",
    "apps.cms",
    "apps.catalog",
    "apps.inventory",
    "apps.accounts",
    "apps.customers",
    "apps.localization",
    "apps.shipping",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.sandbox",
    "apps.promotions",
    "apps.returns",
]

# Customer and staff identities (MTS v2.1 A-22). Sign-in is handled by AureVon's own realm services, never
# by django.contrib.auth backends, so no backend is configured and `authenticate()` can't log anyone in.
AUTH_USER_MODEL = "accounts.Account"
AUTHENTICATION_BACKENDS: list[str] = []
# The sign-in name is unique per (email, account type), not alone — on purpose (MTS §6).
SILENCED_SYSTEM_CHECKS = ["auth.W004"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "common.middleware.RequestIDMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL")

# Rate limits, lockouts and sign-in challenges live in Redis, shared by every API process.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

# Number of trusted reverse-proxy hops in front of the API (CDN, proxy). Decides which X-Forwarded-For entry is real.
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT", default=0)

# Public base URL used in emailed links.
# Demo catalogue (manage.py seed_demo_catalog) may run only where this is true: local and review stacks.
ALLOW_DEMO_DATA = env.bool("ALLOW_DEMO_DATA", default=False)

SITE_URL = env("SITE_URL", default="http://localhost:8080").rstrip("/")
# Publishing CMS content refreshes the storefront's data cache at once (decision 0005: "cache refreshed on publish").
# The worker calls the storefront's internal endpoint with this shared secret; unset, pages refresh within a minute.
STOREFRONT_INTERNAL_URL = env("STOREFRONT_INTERNAL_URL", default="").rstrip("/")
STOREFRONT_REVALIDATE_SECRET = env("STOREFRONT_REVALIDATE_SECRET", default="")
# Product images and other media (MTS §14 object storage). Served publicly under /media/ through the proxy or CDN.
MEDIA_STORAGE = env("MEDIA_STORAGE", default="local")  # "s3" (MinIO locally, P-10 provider) or "local"
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))
MEDIA_URL = "/media/"
MEDIA_BUCKET = env("MEDIA_BUCKET", default="aurevon-media")
MEDIA_PRIVATE_ROOT = env("MEDIA_PRIVATE_ROOT", default=str(BASE_DIR / "media-private"))
MEDIA_PRIVATE_BUCKET = env("MEDIA_PRIVATE_BUCKET", default="aurevon-private")
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", default="")
S3_SECRET_KEY = env("S3_SECRET_KEY", default="")
S3_REGION = env("S3_REGION", default="")
# Uploads are read into memory to be checked and re-encoded; product photos stay well under this.
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024
# 3D (M6; decision 0007). Shoppers never see 3D until V-01, V-02 and V-03 pass (MTS §17): this stays False in
# every environment until then. It is the only switch; the storefront shows a viewer only when the API sends a model.
THREED_FOR_SHOPPERS = env.bool("THREED_FOR_SHOPPERS", default=False)
# The model pipeline (packages/asset-pipeline), run by the worker with Node.js.
ASSET_PIPELINE = env("ASSET_PIPELINE", default=str(BASE_DIR.parent / "packages" / "asset-pipeline" / "src" / "cli.mjs"))
ASSET_PIPELINE_TIMEOUT_SECONDS = 300
THREED_PREVIEW_SECONDS = 600  # staff preview links for drafts
DISPLAY_TIME_ZONE = "Asia/Karachi"  # times shown to people (MTS §5); storage stays UTC

# Encrypts authenticator secrets at rest. Required in production; derived from SECRET_KEY elsewhere.
MFA_ENCRYPTION_KEY = env("MFA_ENCRYPTION_KEY", default="")

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="AureVon <no-reply@aurevon.pk>")

# Argon2 first (MTS §9); the others only verify older hashes.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ur", "Urdu")]
TIME_ZONE = "UTC"  # stored in UTC, shown in local time (MTS §5)
USE_I18N = True
USE_TZ = True

STATIC_URL = "/api/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    # Default deny: every endpoint must declare who may call it (MTS §9).
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.problem_details_handler",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "AureVon API",
    "DESCRIPTION": "AureVon storefront and staff API. MTS v2.1 §8.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "PageKindEnum": ["content", "policy"],
        "ContentFieldKindEnum": ["text", "textarea", "href"],
        "ThreeDStatusEnum": ["processing", "failed", "draft", "approved", "retired"],
        "StatusEnum": ["draft", "published", "archived"],
        "LocaleEnum": ["en", "ur"],
        "PaymentMethodEnum": ["card", "cod"],
    },
}

# Payments (MTS §10). The online provider is pending P-06; the sandbox simulates one end to end and must never
# be enabled in production (config/settings/production.py refuses it).
PAYMENTS_ONLINE_PROVIDER = env("PAYMENTS_ONLINE_PROVIDER", default="sandbox")
PAYMENTS_SANDBOX_ENABLED = env.bool("PAYMENTS_SANDBOX_ENABLED", default=False)
PAYMENTS_SANDBOX_SECRET = env("PAYMENTS_SANDBOX_SECRET", default="sandbox-only-not-a-secret")  # nosec B105

# Whether /api/v1/schema/ is reachable. Off in production; the schema is generated in CI instead.
API_SCHEMA_PUBLIC = False

CELERY_BROKER_URL = REDIS_URL
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    # Owner recoveries whose 24-hour wait has ended (decision 0003, 4.3).
    "release-due-staff-recoveries": {"task": "accounts.release_due_recoveries", "schedule": 60.0},
    # Payment status checks for pending payments, and expiry of unpaid reservations (MTS §10, §11).
    "check-pending-payments": {"task": "payments.check_pending", "schedule": 60.0},
    "expire-unpaid-orders": {"task": "orders.expire_unpaid", "schedule": 60.0},
    "retry-refunds": {"task": "payments.retry_refunds", "schedule": 300.0},
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "common.logging.RequestIDFilter"}},
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            "rename_fields": {"asctime": "time", "levelname": "level", "name": "logger"},
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json", "filters": ["request_id"]}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
