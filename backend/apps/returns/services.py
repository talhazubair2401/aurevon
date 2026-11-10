"""Returns and exchanges (MTS §11; M12): requested within the return window, decided by staff, received, inspected
into sellable, quarantine or damaged stock, then refunded or exchanged. The window is a store setting pending
P-14 (provisional default in the settings registry).

Flow: requested -> approved | rejected; approved -> received -> inspected -> completed. The customer can cancel
while it is still `requested`. Completing a refund return raises a refund request that goes through the normal
approval rules (decision 0003); completing an exchange creates a no-charge replacement order that is fulfilled
like any other order.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.catalog.models import ProductStatus, ProductVariant
from apps.cms.services import get_value
from apps.inventory import services as stock
from apps.notifications.services import alert, send_email
from apps.orders import services as orders
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus
from common.exceptions import ApiProblem
from common.security import new_token, token_hash

from .models import InspectionOutcome, ReturnItem, ReturnKind, ReturnRequest, ReturnStatus

S = ReturnStatus
REASONS = {
    "size": "Size or fit",
    "quality": "Quality problem",
    "not_as_described": "Not as described",
    "wrong_item": "Wrong item sent",
    "changed_mind": "Changed my mind",
    "other": "Other",
}
OPEN = [S.REQUESTED, S.APPROVED, S.RECEIVED, S.INSPECTED]


def window_days() -> int:
    return int(get_value("returns.window_days"))


def _in_window(order: Order) -> bool:
    if order.status != OrderStatus.DELIVERED or order.delivered_at is None:
        return False
    days = window_days()
    return days > 0 and timezone.now() <= order.delivered_at + timedelta(days=days)


def open_quantity(item: OrderItem) -> int:
    """Units of this line already in an open return request (not yet back in stock)."""
    total = ReturnItem.objects.filter(order_item=item, request__status__in=OPEN).aggregate(n=Sum("quantity"))["n"]
    return int(total or 0)


def available_to_return(item: OrderItem) -> int:
    return max(item.quantity - item.returned_quantity - open_quantity(item), 0)


def returnable(order: Order) -> bool:
    return _in_window(order) and any(available_to_return(i) > 0 for i in order.items.all())


def return_by(order: Order) -> Any:
    return order.delivered_at + timedelta(days=window_days()) if order.delivered_at else None


def _number(order: Order) -> str:
    n = ReturnRequest.objects.filter(order=order).count() + 1
    return f"R-{order.number}-{n}"


def _customer_email(r: ReturnRequest, template: str, **extra: Any) -> None:
    send_email(
        [r.order.email],
        template,
        {"number": r.number, "order": r.order.number, "link": orders._link(r.order), **extra},
    )


@transaction.atomic
def create(
    order_id: Any,
    kind: str,
    reason: str,
    details: str,
    lines: list[dict[str, Any]],
    actor_label: str,
) -> ReturnRequest:
    """`lines`: [{"sku": str, "quantity": int, "exchange_sku": str (exchanges only)}]."""
    order = orders.lock(order_id)
    if kind not in ReturnKind.values:
        raise ApiProblem(400, "kind", "Choose a refund or an exchange.")
    if reason not in REASONS:
        raise ApiProblem(400, "reason", "Choose a reason.")
    if not _in_window(order):
        raise ApiProblem(409, "return-window", "This order can no longer be returned.")
    if not lines:
        raise ApiProblem(400, "lines", "Choose at least one item to return.")
    items = {i.sku: i for i in order.items.all()}
    picked: list[tuple[OrderItem, int, str]] = []
    for line in lines:
        item = items.get(str(line.get("sku", "")))
        quantity = line.get("quantity")
        if item is None:
            raise ApiProblem(400, "lines", "That item isn't part of this order.")
        if not isinstance(quantity, int) or quantity < 1 or quantity > available_to_return(item):
            raise ApiProblem(400, "lines", f"You can return up to {available_to_return(item)} of {item.name}.")
        exchange_sku = ""
        if kind == ReturnKind.EXCHANGE:
            exchange_sku = str(line.get("exchange_sku", "")).strip()
            wanted = ProductVariant.objects.filter(
                sku=exchange_sku,
                is_active=True,
                product__slug=item.product_slug,
                product__status=ProductStatus.PUBLISHED,
            ).first()
            if wanted is None or wanted.sku == item.sku:
                raise ApiProblem(400, "exchange_sku", f"Choose a different size or colour of {item.name}.")
        picked.append((item, quantity, exchange_sku))
    if len({i.pk for i, _, _ in picked}) != len(picked):
        raise ApiProblem(400, "lines", "List each item once.")
    r = ReturnRequest.objects.create(
        number=_number(order), order=order, kind=kind, reason=reason, details=details.strip()[:1000]
    )
    for item, quantity, exchange_sku in picked:
        ReturnItem.objects.create(request=r, order_item=item, quantity=quantity, exchange_sku=exchange_sku)
    orders.history(order, order.status, actor_label, f"Return {r.number} requested ({kind})", kind="return")
    alert(
        "return_requested",
        f"Return {r.number} requested for order {order.number} ({REASONS[reason].lower()}).",
        severity="info",
        target_type="return",
        target_id=r.pk,
    )
    _customer_email(r, "return_requested", kind=r.get_kind_display().lower())
    return r


def _lock(return_id: Any) -> ReturnRequest:
    r = ReturnRequest.objects.select_for_update().select_related("order").filter(pk=return_id).first()
    if r is None:
        raise ApiProblem(404, "not-found", "No such return.")
    return r


def _require(r: ReturnRequest, *allowed: str) -> None:
    if r.status not in allowed:
        raise ApiProblem(409, "invalid-transition", f"This return is {r.get_status_display().lower()}.")


def _audit(r: ReturnRequest, action: str, actor: Actor, request: Any, **after: Any) -> None:
    record(f"return.{action}", actor, target_type="return", target_id=r.number, after=after or None, request=request)
    orders.history(r.order, r.order.status, actor.label, f"Return {r.number}: {action}", kind="return")


def _resolve_alert(r: ReturnRequest, actor_label: str) -> None:
    from apps.notifications.models import StaffAlert

    StaffAlert.objects.filter(kind="return_requested", target_id=str(r.pk), resolved_at__isnull=True).update(
        resolved_at=timezone.now(), resolved_by=actor_label
    )


@transaction.atomic
def cancel_by_customer(return_id: Any, actor_label: str) -> ReturnRequest:
    r = _lock(return_id)
    _require(r, S.REQUESTED)
    r.status = S.CANCELLED
    r.save(update_fields=["status", "updated_at"])
    orders.history(r.order, r.order.status, actor_label, f"Return {r.number} cancelled by the customer", kind="return")
    _resolve_alert(r, actor_label)
    return r


@transaction.atomic
def decide(return_id: Any, approve: bool, note: str, actor: Actor, request: Any = None) -> ReturnRequest:
    r = _lock(return_id)
    _require(r, S.REQUESTED)
    if not approve and not note.strip():
        raise ApiProblem(400, "note", "Tell the customer why the return can't be accepted.")
    r.status = S.APPROVED if approve else S.REJECTED
    r.decision_note = note.strip()[:300]
    r.decided_by = actor.label
    r.save(update_fields=["status", "decision_note", "decided_by", "updated_at"])
    _audit(r, "approve" if approve else "reject", actor, request, note=r.decision_note)
    _resolve_alert(r, actor.label)
    instructions = str(get_value("returns.instructions") or "") if approve else ""
    _customer_email(
        r, "return_approved" if approve else "return_rejected", note=r.decision_note, instructions=instructions
    )
    return r


@transaction.atomic
def receive(return_id: Any, actor: Actor, request: Any = None) -> ReturnRequest:
    r = _lock(return_id)
    _require(r, S.APPROVED)
    r.status = S.RECEIVED
    r.save(update_fields=["status", "updated_at"])
    _audit(r, "receive", actor, request)
    return r


@transaction.atomic
def inspect(return_id: Any, outcomes: dict[str, dict[str, str]], actor: Actor, request: Any = None) -> ReturnRequest:
    """`outcomes`: {return_item_id: {"outcome": sellable|quarantine|damaged, "note": str}} for every item.
    Units go into the matching stock location and count as returned on the order line."""
    r = _lock(return_id)
    _require(r, S.RECEIVED)
    items = list(r.items.select_related("order_item"))
    if {str(i.pk) for i in items} != set(outcomes):
        raise ApiProblem(400, "outcomes", "Record an outcome for every returned item.")
    for i in items:
        o = outcomes[str(i.pk)]
        outcome = o.get("outcome", "")
        if outcome not in InspectionOutcome.values:
            raise ApiProblem(400, "outcomes", "Each item is sellable, needs a second check, or is damaged.")
        if outcome != InspectionOutcome.SELLABLE and not str(o.get("note", "")).strip():
            raise ApiProblem(400, "outcomes", "Add a note for items that aren't going back on sale.")
    for i in items:
        o = outcomes[str(i.pk)]
        i.outcome = o["outcome"]
        i.inspection_note = str(o.get("note", "")).strip()[:300]
        i.save(update_fields=["outcome", "inspection_note"])
        stock.place_returned(i.order_item.variant_id, i.quantity, i.outcome, r.number, actor.label)
        line = OrderItem.objects.select_for_update().get(pk=i.order_item_id)
        line.returned_quantity += i.quantity
        line.save(update_fields=["returned_quantity"])
    r.status = S.INSPECTED
    r.refund_amount = suggested_refund(r) if r.kind == ReturnKind.REFUND else None
    r.save(update_fields=["status", "refund_amount", "updated_at"])
    _audit(r, "inspect", actor, request, outcomes={str(i.order_item.sku): i.outcome for i in items})
    order = r.order
    if order.status == OrderStatus.DELIVERED and all(x.returned_quantity >= x.quantity for x in order.items.all()):
        orders.advance(order.pk, OrderStatus.RETURNED, actor, f"Everything came back (return {r.number})")
    return r


def suggested_refund(r: ReturnRequest) -> Decimal:
    """What the returned units cost, less their share of any order discount. Delivery isn't refunded by default."""
    order = r.order
    goods = sum((i.order_item.unit_price * i.quantity for i in r.items.select_related("order_item")), Decimal("0"))
    if order.discount and order.subtotal:
        goods -= (goods * order.discount / order.subtotal).quantize(Decimal("0.01"))
    return max(goods.quantize(Decimal("0.01")), Decimal("0.00"))


@transaction.atomic
def complete(return_id: Any, actor: Actor, *, amount: Decimal | None = None, request: Any = None) -> ReturnRequest:
    r = _lock(return_id)
    _require(r, S.INSPECTED)
    if r.kind == ReturnKind.REFUND:
        from apps.payments import services as payments

        value = amount if amount is not None else (r.refund_amount or suggested_refund(r))
        payments.request_refund(r.order, value, f"Return {r.number}", actor, source="return", request=request)
        r.refund_amount = value
        extra: dict[str, Any] = {"amount": f"{value:,.2f}"}
    else:
        exchange = _exchange_order(r, actor)
        r.exchange_order = exchange
        extra = {"exchange": exchange.number}
    r.status = S.COMPLETED
    r.save(update_fields=["status", "refund_amount", "exchange_order", "updated_at"])
    _audit(r, "complete", actor, request, **extra)
    _customer_email(r, "return_completed", kind=r.kind, **extra)
    return r


def _exchange_order(r: ReturnRequest, actor: Actor) -> Order:
    """A no-charge order for the replacement sizes/colours, confirmed at once and fulfilled like any other."""
    original = r.order
    wanted: list[tuple[ProductVariant, OrderItem, int]] = []
    for i in r.items.select_related("order_item"):
        v = ProductVariant.objects.select_related("product", "colour").get(sku=i.exchange_sku)
        wanted.append((v, i.order_item, i.quantity))
    exchange = Order.objects.create(
        number=orders.next_number(),
        account=original.account,
        email=original.email,
        phone=original.phone,
        locale=original.locale,
        status=OrderStatus.AWAITING_PAYMENT,
        payment_status=PaymentStatus.PAID,
        payment_method=PaymentMethod.EXCHANGE,
        subtotal=Decimal("0.00"),
        total=Decimal("0.00"),
        shipping_address=original.shipping_address,
        shipping_zone=original.shipping_zone,
        shipping_method=original.shipping_method,
        delivery_days=original.delivery_days,
        access_token_hash=token_hash(new_token()),
        customer_note=f"Exchange for return {r.number}",
    )
    for v, line, quantity in wanted:
        OrderItem.objects.create(
            order=exchange,
            variant=v,
            product_slug=v.product.slug,
            name=line.name,
            sku=v.sku,
            size=v.size,
            colour=v.colour.name_en,
            image_url=line.image_url,
            unit_price=Decimal("0.00"),
            quantity=quantity,
            line_total=Decimal("0.00"),
        )
    orders.history(exchange, OrderStatus.AWAITING_PAYMENT, actor.label, f"Exchange for return {r.number}")
    needed: dict[Any, int] = {}
    for v, _, quantity in wanted:
        needed[v.pk] = needed.get(v.pk, 0) + quantity
    try:
        stock.reserve(exchange.pk, exchange.number, needed, timezone.now() + timedelta(days=3650))
    except stock.OutOfStock as exc:
        raise ApiProblem(
            409, "out-of-stock", "The replacement isn't in stock. Refund instead, or wait for stock and try again."
        ) from exc
    stock.commit(exchange.pk, exchange.number)
    orders._move(exchange, OrderStatus.CONFIRMED, actor.label, f"Exchange for return {r.number}")
    return exchange
