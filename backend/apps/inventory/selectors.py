"""Availability reads: sellable on hand minus reserved (MTS §6). Quarantine and damaged stock never count."""

from collections.abc import Iterable
from typing import Any

from django.db.models import F, Sum

from .models import InventoryItem, LocationKind


def available(variant_ids: Iterable[Any]) -> dict[Any, int]:
    ids = list(variant_ids)
    rows = (
        InventoryItem.objects.filter(variant_id__in=ids, location__kind=LocationKind.SELLABLE)
        .values("variant_id")
        .annotate(n=Sum(F("on_hand") - F("reserved")))
    )
    counts = {r["variant_id"]: int(r["n"] or 0) for r in rows}
    return {v: max(counts.get(v, 0), 0) for v in ids}
