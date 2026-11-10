"""Staging: production settings with provider sandboxes (MTS §14)."""

from .production import *  # noqa: F403
from .production import env

# Simulated payment provider for development and tests (never production).
PAYMENTS_SANDBOX_ENABLED = env.bool("PAYMENTS_SANDBOX_ENABLED", default=True)
