"""Platform tasks."""

from celery import shared_task


@shared_task(name="common.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    """Round-trip check for the worker; used by monitoring and tests."""
    return "pong"
