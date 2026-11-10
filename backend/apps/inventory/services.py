"""Stock writes (MTS §6: only through inventory services, row locked, movement recorded in the same transaction)."""

from collections.abc import Iterable
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    MAIN_WAREHOUSE,
    InventoryItem,
    MovementReason,
    ReservationStatus,
    StockLocation,
    StockMovement,
    StockReservation,
)


def main_warehouse() -> StockLocation:
    return StockLocation.objects.get(code=MAIN_WAREHOUSE)


def ensure_items(variant_ids: Iterable[Any]) -> None:
    """Every variant has a record in the Main warehouse, starting at 0 (decision 0006, #11)."""
    location = main_warehouse()
    existing = set(InventoryItem.objects.filter(location=location).values_list("variant_id", flat=True))
    InventoryItem.objects.bulk_create(
        InventoryItem(variant_id=v, location=location) for v in variant_ids if v not in existing
    )


@transaction.atomic
def receive(variant_id: Any, quantity: int, reason: str, actor_label: str = "", note: str = "") -> InventoryItem:
    """Adds stock to the Main warehouse. Adjustments and receiving screens arrive in M9."""
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    ensure_items([variant_id])
    item = InventoryItem.objects.select_for_update().get(variant_id=variant_id, location_id=MAIN_WAREHOUSE)
    item.on_hand += quantity
    item.save(update_fields=["on_hand", "updated_at"])
    StockMovement.objects.create(item=item, quantity=quantity, reason=reason, actor_label=actor_label, note=note)
    return item


# --- Reservations (MTS §11: reserve at placement, commit on payment or COD, release or restore on cancel) -----


class OutOfStock(Exception):
    """One or more lines can't be reserved. `shortages` maps variant id to the quantity still available."""

    def __init__(self, shortages: dict[Any, int]):
        super().__init__("Not enough stock.")
        self.shortages = shortages


def _move(
    item: InventoryItem, quantity: int, reason: str, reference: str, actor_label: str = "", note: str = ""
) -> None:
    StockMovement.objects.create(
        item=item, quantity=quantity, reason=reason, reference=reference, actor_label=actor_label, note=note
    )


def reserve(order_id: Any, reference: str, lines: dict[Any, int], expires_at: Any) -> None:
    """Locks every line's sellable row in variant order (no deadlocks), checks all, then reserves all.

    Must run inside the caller's transaction (the order placement). Raises OutOfStock naming every short line.
    """

    ensure_items(lines.keys())
    items = list(
        InventoryItem.objects.select_for_update()
        .filter(variant_id__in=list(lines), location_id=MAIN_WAREHOUSE)
        .order_by("variant_id")
    )
    shortages = {
        i.variant_id: max(i.on_hand - i.reserved, 0) for i in items if i.on_hand - i.reserved < lines[i.variant_id]
    }
    if shortages:
        raise OutOfStock(shortages)
    for item in items:
        quantity = lines[item.variant_id]
        InventoryItem.objects.filter(pk=item.pk).update(reserved=F("reserved") + quantity)
        StockReservation.objects.create(item=item, order_id=order_id, quantity=quantity, expires_at=expires_at)


def _active(order_id: Any) -> list[Any]:

    return list(
        StockReservation.objects.select_for_update()
        .select_related("item")
        .filter(order_id=order_id, status=ReservationStatus.ACTIVE)
        .order_by("item__variant_id")
    )


@transaction.atomic
def commit(order_id: Any, reference: str) -> None:
    """Payment confirmed or COD accepted: the reserved units leave sellable stock (a Sale movement)."""

    for r in _active(order_id):
        InventoryItem.objects.select_for_update().filter(pk=r.item_id).update(
            on_hand=F("on_hand") - r.quantity, reserved=F("reserved") - r.quantity
        )
        _move(r.item, -r.quantity, MovementReason.SALE, reference)
        r.status, r.closed_at = ReservationStatus.COMMITTED, timezone.now()
        r.save(update_fields=["status", "closed_at"])


@transaction.atomic
def release(order_id: Any, reference: str) -> int:
    """Unpaid order cancelled or expired: reserved units become available again. Returns units released."""

    released = 0
    for r in _active(order_id):
        InventoryItem.objects.select_for_update().filter(pk=r.item_id).update(reserved=F("reserved") - r.quantity)
        r.status, r.closed_at = ReservationStatus.RELEASED, timezone.now()
        r.save(update_fields=["status", "closed_at"])
        released += r.quantity
    return released


@transaction.atomic
def rereserve(order_id: Any, reference: str, expires_at: Any) -> bool:
    """A late payment for a released order (D-07 proposal): take the stock again if it is still there."""

    lines: dict[Any, int] = {}
    for r in StockReservation.objects.filter(order_id=order_id, status=ReservationStatus.RELEASED).select_related(
        "item"
    ):
        lines[r.item.variant_id] = lines.get(r.item.variant_id, 0) + r.quantity
    if not lines:
        return False
    try:
        reserve(order_id, reference, lines, expires_at)
    except OutOfStock:
        return False
    return True


@transaction.atomic
def restore(order_id: Any, reference: str, actor_label: str = "", reason: str = MovementReason.CANCELLATION) -> None:
    """Cancelled before dispatch after stock was committed: the units go straight back to sellable (A-25).
    Also used for an undelivered parcel that came back unopened (reason: return)."""

    for r in (
        StockReservation.objects.select_for_update()
        .select_related("item")
        .filter(order_id=order_id, status=ReservationStatus.COMMITTED)
    ):
        InventoryItem.objects.filter(pk=r.item_id).update(on_hand=F("on_hand") + r.quantity)
        _move(r.item, r.quantity, reason, reference, actor_label)
        r.status = ReservationStatus.RELEASED
        r.save(update_fields=["status"])
