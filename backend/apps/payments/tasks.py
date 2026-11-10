from celery import shared_task

from . import services


@shared_task(name="payments.check_pending")  # type: ignore[untyped-decorator]
def check_pending() -> int:
    return services.check_pending()


@shared_task(name="payments.retry_refunds")  # type: ignore[untyped-decorator]
def retry_refunds() -> int:
    return services.retry_due_refunds()
