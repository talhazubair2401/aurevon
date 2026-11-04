"""Tells the storefront to drop its cached CMS reads after a publish (decision 0005)."""

import json
import logging
import urllib.request

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 5


@shared_task(autoretry_for=(OSError,), retry_backoff=True, max_retries=5)  # type: ignore[untyped-decorator]
def refresh_storefront(tags: list[str]) -> None:
    base = settings.STOREFRONT_INTERNAL_URL
    secret = settings.STOREFRONT_REVALIDATE_SECRET
    if not base or not secret:
        logger.info("storefront refresh skipped: not configured", extra={"tags": tags})
        return
    if not base.startswith(("http://", "https://")):
        raise ValueError("STOREFRONT_INTERNAL_URL must be an http(s) URL")
    request = urllib.request.Request(  # noqa: S310  (scheme checked above; internal service URL from settings)
        f"{base}/internal/revalidate",
        data=json.dumps({"tags": tags}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310  # nosec B310
        if response.status != 200:
            raise OSError(f"storefront refresh returned {response.status}")
