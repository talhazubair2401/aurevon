"""Stock writes (MTS §6: only through inventory services, row locked, movement recorded in the same transaction)."""

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.audit.services import Actor, record

from .models import (
    MAIN_WAREHOUSE,
    InventoryItem,
    MovementReason,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
    ReservationStatus,
    StockLocation,
    StockMovement,
    StockReservation,
    Supplier,
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
    check_low_stock(
        StockReservation.objects.filter(order_id=order_id, status=ReservationStatus.COMMITTED).values_list(
            "item__variant_id", flat=True
        )
    )


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


# --- Staff stock management (M9) -------------------------------------------------------------------------------

STAFF_REASONS = {
    MovementReason.ADJUSTMENT,  # counted stock differs
    MovementReason.DAMAGED,
    MovementReason.WRITE_OFF,
    MovementReason.RECEIPT,
}


class StockError(ValueError):
    """A readable reason, shown to staff as-is."""


def item_for(variant_id: Any, location: str) -> InventoryItem:
    if not StockLocation.objects.filter(code=location).exists():
        raise StockError("Unknown stock location.")
    item, _ = InventoryItem.objects.get_or_create(variant_id=variant_id, location_id=location)
    return InventoryItem.objects.select_for_update().get(pk=item.pk)


@transaction.atomic
def adjust(
    variant_id: Any, location: str, delta: int, reason: str, note: str, actor: Actor, request: Any = None
) -> InventoryItem:
    """A counted correction, a write-off or a manual receipt. Never below what is reserved for orders."""
    if reason not in STAFF_REASONS:
        raise StockError("Choose why the stock changes.")
    if delta == 0:
        raise StockError("Enter how many units to add or remove.")
    if not note.strip():
        raise StockError("Add a note explaining the change.")
    item = item_for(variant_id, location)
    if item.on_hand + delta < item.reserved:
        raise StockError(f"Only {item.on_hand - item.reserved} units can be removed: the rest are held for orders.")
    before = item.on_hand
    item.on_hand += delta
    item.save(update_fields=["on_hand", "updated_at"])
    _move(item, delta, reason, "", actor.label, note.strip()[:200])
    record(
        "stock.adjust",
        actor,
        target_type="variant",
        target_id=item.variant.sku,
        before={"location": location, "on_hand": before},
        after={"location": location, "on_hand": item.on_hand, "reason": reason, "note": note},
        request=request,
    )
    check_low_stock([item.variant_id])
    return item


TRANSFER_REASON = {
    ("main", "quarantine"): MovementReason.QUARANTINE,
    ("quarantine", "main"): MovementReason.RELEASE,
    ("quarantine", "damaged"): MovementReason.DAMAGED,
    ("main", "damaged"): MovementReason.DAMAGED,
}


@transaction.atomic
def transfer(
    variant_id: Any, source: str, target: str, quantity: int, note: str, actor: Actor, request: Any = None
) -> None:
    """Between sellable, quarantine and damaged stock (MTS §11): released after a second check, or written down."""
    reason = TRANSFER_REASON.get((source, target))
    if reason is None:
        raise StockError("That move isn't possible.")
    if quantity < 1:
        raise StockError("Move at least one unit.")
    src = item_for(variant_id, source)
    if src.on_hand - src.reserved < quantity:
        raise StockError(f"Only {src.on_hand - src.reserved} units are available to move.")
    dst = item_for(variant_id, target)
    src.on_hand -= quantity
    dst.on_hand += quantity
    src.save(update_fields=["on_hand", "updated_at"])
    dst.save(update_fields=["on_hand", "updated_at"])
    text = note.strip()[:200]
    _move(src, -quantity, reason, "", actor.label, text)
    _move(dst, quantity, reason, "", actor.label, text)
    record(
        "stock.transfer",
        actor,
        target_type="variant",
        target_id=src.variant.sku,
        after={"from": source, "to": target, "quantity": quantity, "note": note},
        request=request,
    )
    check_low_stock([variant_id])


@transaction.atomic
def set_reorder_level(variant_id: Any, level: int, actor: Actor, request: Any = None) -> InventoryItem:
    if level < 0 or level > 100_000:
        raise StockError("Use a reorder level between 0 and 100,000 (0 turns the alert off).")
    item = item_for(variant_id, MAIN_WAREHOUSE)
    before = item.reorder_level
    item.reorder_level = level
    item.save(update_fields=["reorder_level", "updated_at"])
    record(
        "stock.reorder_level",
        actor,
        target_type="variant",
        target_id=item.variant.sku,
        before={"reorder_level": before},
        after={"reorder_level": level},
        request=request,
    )
    check_low_stock([variant_id])
    return item


def check_low_stock(variant_ids: Iterable[Any]) -> None:
    """Raises a low-stock alert when sellable stock falls to the reorder level; resolves it when stock is back."""
    from apps.notifications.models import StaffAlert
    from apps.notifications.services import alert

    for item in InventoryItem.objects.filter(
        variant_id__in=list(variant_ids), location_id=MAIN_WAREHOUSE
    ).select_related("variant"):
        key = f"stock_low:{item.variant.sku}"
        available = item.on_hand - item.reserved
        if item.reorder_level and available <= item.reorder_level:
            alert(
                "stock_low",
                f"{item.variant.sku} is low: {available} available (reorder level {item.reorder_level}).",
                target_type="variant",
                target_id=item.variant.sku,
                dedupe_key=key,
            )
        else:
            StaffAlert.objects.filter(dedupe_key=key, resolved_at__isnull=True).update(
                resolved_at=timezone.now(), resolved_by="system (stock back above the reorder level)"
            )


@transaction.atomic
def place_returned(variant_id: Any, quantity: int, outcome: str, reference: str, actor_label: str) -> None:
    """A returned item after inspection (MTS §11): back to sellable, into quarantine, or damaged."""
    location = {"sellable": MAIN_WAREHOUSE, "quarantine": "quarantine", "damaged": "damaged"}[outcome]
    reason = {
        "sellable": MovementReason.RETURN,
        "quarantine": MovementReason.QUARANTINE,
        "damaged": MovementReason.DAMAGED,
    }[outcome]
    item = item_for(variant_id, location)
    item.on_hand += quantity
    item.save(update_fields=["on_hand", "updated_at"])
    _move(item, quantity, reason, reference, actor_label)
    if outcome == "sellable":
        check_low_stock([variant_id])


# --- Suppliers and purchase orders (M9) -----------------------------------------------------------------------


def _po_number() -> str:
    last = PurchaseOrder.objects.select_for_update().order_by("-number").values_list("number", flat=True).first()
    n = int(last.split("-")[1]) + 1 if last else 1
    return f"PO-{n:06d}"


def _lines(raw: Any) -> list[tuple[Any, int, Decimal]]:
    from apps.catalog.models import ProductVariant

    if not isinstance(raw, list) or not raw or len(raw) > 200:
        raise StockError("Add between 1 and 200 lines.")
    lines: list[tuple[Any, int, Decimal]] = []
    seen: set[str] = set()
    for n, line in enumerate(raw, start=1):
        if not isinstance(line, dict):
            raise StockError(f"Line {n}: invalid.")
        sku = str(line.get("sku", "")).strip().upper()
        variant = ProductVariant.objects.filter(sku=sku).first()
        if variant is None:
            raise StockError(f"Line {n}: unknown SKU {sku or '(empty)'}.")
        if sku in seen:
            raise StockError(f"Line {n}: {sku} appears twice.")
        seen.add(sku)
        try:
            qty = int(line.get("quantity", 0))
            cost = Decimal(str(line.get("unit_cost", "0") or "0")).quantize(Decimal("0.01"))
        except (ValueError, InvalidOperation):
            raise StockError(f"Line {n}: enter a whole quantity and a cost in PKR.") from None
        if qty < 1 or qty > 100_000 or cost < 0:
            raise StockError(f"Line {n}: quantity 1 to 100,000 and a cost of zero or more.")
        lines.append((variant.pk, qty, cost))
    return lines


@transaction.atomic
def create_purchase_order(
    supplier_id: Any, raw_lines: Any, expected_on: Any, note: str, actor: Actor, request: Any = None
) -> PurchaseOrder:
    supplier = Supplier.objects.filter(pk=supplier_id, is_active=True).first()
    if supplier is None:
        raise StockError("Choose an active supplier.")
    lines = _lines(raw_lines)
    po = PurchaseOrder.objects.create(
        number=_po_number(), supplier=supplier, expected_on=expected_on, note=note.strip()[:500], created_by=actor.label
    )
    PurchaseOrderLine.objects.bulk_create(
        PurchaseOrderLine(purchase_order=po, variant_id=v, quantity_ordered=q, unit_cost=c) for v, q, c in lines
    )
    record(
        "po.create",
        actor,
        target_type="purchase_order",
        target_id=po.number,
        after={"lines": len(lines)},
        request=request,
    )
    return po


@transaction.atomic
def update_purchase_order(
    po: PurchaseOrder, raw_lines: Any, expected_on: Any, note: str, actor: Actor, request: Any = None
) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise StockError("Only a draft purchase order can be edited.")
    lines = _lines(raw_lines)
    po.lines.all().delete()
    PurchaseOrderLine.objects.bulk_create(
        PurchaseOrderLine(purchase_order=po, variant_id=v, quantity_ordered=q, unit_cost=c) for v, q, c in lines
    )
    po.expected_on, po.note = expected_on, note.strip()[:500]
    po.save(update_fields=["expected_on", "note", "updated_at"])
    record(
        "po.update",
        actor,
        target_type="purchase_order",
        target_id=po.number,
        after={"lines": len(lines)},
        request=request,
    )
    return po


@transaction.atomic
def send_purchase_order(po: PurchaseOrder, actor: Actor, request: Any = None) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise StockError("This purchase order has already been sent.")
    po.status, po.sent_at = PurchaseOrderStatus.SENT, timezone.now()
    po.save(update_fields=["status", "sent_at", "updated_at"])
    record("po.send", actor, target_type="purchase_order", target_id=po.number, request=request)
    return po


@transaction.atomic
def cancel_purchase_order(po: PurchaseOrder, actor: Actor, request: Any = None) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status not in (PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.SENT):
        raise StockError("A purchase order with received stock can't be cancelled.")
    po.status = PurchaseOrderStatus.CANCELLED
    po.save(update_fields=["status", "updated_at"])
    record("po.cancel", actor, target_type="purchase_order", target_id=po.number, request=request)
    return po


@transaction.atomic
def receive_purchase_order(po: PurchaseOrder, raw: Any, actor: Actor, request: Any = None) -> PurchaseOrder:
    """Goods arrive (possibly in parts): sellable stock goes up with a Receipt movement per line."""
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status not in (PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTLY_RECEIVED):
        raise StockError("Send the purchase order before receiving against it.")
    if not isinstance(raw, list) or not raw:
        raise StockError("Enter what arrived.")
    lines = {str(line.pk): line for line in po.lines.select_for_update().select_related("variant")}
    received: dict[str, int] = {}
    for entry in raw:
        line = lines.get(str(entry.get("line_id"))) if isinstance(entry, dict) else None
        if line is None:
            raise StockError("Unknown purchase order line.")
        try:
            qty = int(entry.get("quantity", 0))
        except ValueError:
            raise StockError("Enter whole quantities.") from None
        if qty < 0 or line.quantity_received + qty > line.quantity_ordered:
            raise StockError(
                f"{line.variant.sku}: at most {line.quantity_ordered - line.quantity_received} more can be received."
            )
        if qty:
            received[line.variant.sku] = qty
            line.quantity_received += qty
            line.save(update_fields=["quantity_received"])
            item = item_for(line.variant_id, MAIN_WAREHOUSE)
            item.on_hand += qty
            item.save(update_fields=["on_hand", "updated_at"])
            _move(item, qty, MovementReason.RECEIPT, po.number, actor.label)
    if not received:
        raise StockError("Enter at least one received quantity.")
    done = all(line.quantity_received == line.quantity_ordered for line in lines.values())
    po.status = PurchaseOrderStatus.RECEIVED if done else PurchaseOrderStatus.PARTLY_RECEIVED
    po.save(update_fields=["status", "updated_at"])
    record(
        "po.receive",
        actor,
        target_type="purchase_order",
        target_id=po.number,
        after={"received": received},
        request=request,
    )
    check_low_stock([line.variant_id for line in lines.values()])
    return po
