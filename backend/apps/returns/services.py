"""Returns and exchanges (MTS §11): requested within the return window, decided by staff, received, inspected
into sellable, quarantine or damaged stock, then refunded or exchanged. The window is a store setting pending
P-14 (provisional default in the settings registry)."""

from datetime import timedelta

from django.utils import timezone

from apps.cms.services import get_value
from apps.orders.models import Order, OrderStatus


def window_days() -> int:
    return int(get_value("returns.window_days"))


def returnable(order: Order) -> bool:
    if order.status != OrderStatus.DELIVERED or order.delivered_at is None:
        return False
    days = window_days()
    if days <= 0 or timezone.now() > order.delivered_at + timedelta(days=days):
        return False
    return any(i.quantity > i.returned_quantity for i in order.items.all())
