from celery import shared_task

from . import services


@shared_task(name="cart.send_reminders")  # type: ignore[untyped-decorator]
def send_reminders() -> int:
    return services.send_reminders()
