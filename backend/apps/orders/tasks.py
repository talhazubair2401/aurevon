from celery import shared_task

from . import services


@shared_task(name="orders.expire_unpaid")  # type: ignore[untyped-decorator]
def expire_unpaid() -> int:
    return services.expire_due()
