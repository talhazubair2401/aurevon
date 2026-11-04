"""Stock writes (MTS §6: only through inventory services, row locked, movement recorded in the same transaction)."""

from collections.abc import Iterable
from typing import Any

from django.db import transaction

from .models import MAIN_WAREHOUSE, InventoryItem, StockLocation, StockMovement


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
