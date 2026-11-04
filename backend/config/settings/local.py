"""Local development (Docker Compose or a developer machine)."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "api"])
API_SCHEMA_PUBLIC = True
