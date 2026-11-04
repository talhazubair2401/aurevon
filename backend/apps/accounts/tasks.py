from celery import shared_task

from .services import recovery


@shared_task(name="accounts.release_due_recoveries")  # type: ignore[untyped-decorator]
def release_due_recoveries() -> int:
    """Proceeds with Owner recoveries whose 24-hour wait has ended (decision 0003, 4.3)."""
    return recovery.release_due()
