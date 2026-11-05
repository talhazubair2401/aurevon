from celery import shared_task

from . import threed


@shared_task(acks_late=True)  # type: ignore[untyped-decorator]
def process_threed(asset_id: str) -> None:
    """Validate, measure and compress an uploaded garment model (decision 0007)."""
    threed.process(asset_id)
