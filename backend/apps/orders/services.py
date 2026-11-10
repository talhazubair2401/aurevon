"""Order lifecycle (MTS §11). Every change is a validated transition written to OrderStatusHistory with the
actor and reason; stock follows the A-25 rules through the inventory services."""

from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.inventory import services as stock
from apps.notifications.services import alert, send_email
from common.exceptions import ApiProblem

from .models import Order, OrderStatus, OrderStatusHistory, PaymentMethod, PaymentStatus

S = OrderStatus

# Forward states and exits (MTS §11 diagram). "Awaiting" is skipped for cash on delivery.
TRANSITIONS: dict[str, set[str]] = {
    S.AWAITING_PAYMENT: {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED: {S.PACKING, S.CANCELLED},
    S.PACKING: {S.DISPATCHED, S.CANCELLED, S.CONFIRMED},
    S.DISPATCHED: {S.DELIVERED, S.UNDELIVERED},
    S.DELIVERED: {S.RETURNED},
    S.CANCELLED: set(),
    S.UNDELIVERED: set(),
    S.RETURNED: set(),
}
BEFORE_DISPATCH = {S.AWAITING_PAYMENT, S.CONFIRMED, S.PACKING}


def next_number() -> str:
    with connection.cursor() as cur:
        cur.execute("SELECT nextval('orders_number_seq')")
        (n,) = cur.fetchone()
    return f"AV{n}"


def history(order: Order, to: str, actor_label: str, reason: str = "", *, kind: str = "order", frm: str = "") -> None:
    OrderStatusHistory.objects.create(
        order=order, kind=kind, from_status=frm, to_status=to, actor_label=actor_label[:254], reason=reason[:300]
    )


def set_payment_status(order: Order, to: str, actor_label: str, reason: str = "") -> None:
    if order.payment_status == to:
        return
    frm = order.payment_status
    order.payment_status = to
    order.save(update_fields=["payment_status", "updated_at"])
    history(order, to, actor_label, reason, kind="payment", frm=frm)


def lock(order_id: Any) -> Order:
    return Order.objects.select_for_update().get(pk=order_id)


def _move(order: Order, to: str, actor_label: str, reason: str) -> None:
    if to not in TRANSITIONS[order.status]:
        raise ApiProblem(
            409,
            "invalid-transition",
            f"An order that is {order.get_status_display().lower()} can't become {S(to).label.lower()}.",
        )
    frm = order.status
    order.status = to
    now = timezone.now()
    stamp: dict[str, str] = {
        S.CONFIRMED: "confirmed_at",
        S.DISPATCHED: "dispatched_at",
        S.DELIVERED: "delivered_at",
        S.CANCELLED: "cancelled_at",
    }
    fields = ["status", "updated_at"]
    if to in stamp and getattr(order, stamp[to]) is None:
        setattr(order, stamp[to], now)
        fields.append(stamp[to])
    order.save(update_fields=fields)
    history(order, to, actor_label, reason, frm=frm)


def _link(order: Order) -> str:
    return f"{settings.SITE_URL}/{order.locale}/account/orders/{order.number}"


def _email(order: Order, template: str, **extra: Any) -> None:
    send_email(
        [order.email],
        template,
        {
            "number": order.number,
            "total": f"{order.total:,.2f}",
            "currency": order.currency,
            "link": _link(order),
            **extra,
        },
    )


@transaction.atomic
def confirm_paid(order_id: Any, actor_label: str, reason: str = "Payment confirmed") -> Order:
    """A verified online payment: stock is committed and the order confirmed (MTS §11).

    A payment that arrives after the reservation was released (D-07, provisional rule as proposed): the stock is
    re-reserved if still available and the order restored; otherwise the payment is refunded automatically.
    Staff are alerted either way.
    """
    order = lock(order_id)
    late = order.status == S.CANCELLED and order.payment_method == PaymentMethod.CARD
    if late:
        expires = timezone.now() + timedelta(minutes=5)
        if stock.rereserve(order.pk, order.number, expires):
            order.status, order.cancelled_at, order.cancel_reason = S.AWAITING_PAYMENT, None, ""
            order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
            history(order, S.AWAITING_PAYMENT, actor_label, "Late payment: stock re-reserved", frm=S.CANCELLED)
            alert(
                "late-payment-restored",
                f"Order {order.number} was paid after it expired and has been restored.",
                target_type="order",
                target_id=order.number,
            )
        else:
            set_payment_status(order, PaymentStatus.PAID, actor_label, "Late payment; stock no longer available")
            alert(
                "late-payment-refund",
                f"Order {order.number} was paid after it expired and the stock is gone. "
                "A refund has been raised automatically.",
                severity="critical",
                target_type="order",
                target_id=order.number,
            )
            from apps.payments import services as payments  # circular at import time

            payments.request_refund(
                order,
                order.total,
                "Paid after the order expired; item no longer available",
                Actor(None, "system"),
                source="late-payment",
                auto_approve=True,
            )
            return order
    if order.status != S.AWAITING_PAYMENT:
        set_payment_status(order, PaymentStatus.PAID, actor_label, reason)
        return order
    stock.commit(order.pk, order.number)
    order.reservation_expires_at = None
    order.save(update_fields=["reservation_expires_at", "updated_at"])
    _move(order, S.CONFIRMED, actor_label, reason)
    set_payment_status(order, PaymentStatus.PAID, actor_label, reason)
    _email(order, "order_confirmed", paid=True)
    return order


@transaction.atomic
def cancel(order_id: Any, actor: Actor, reason: str, request: Any = None, *, expired: bool = False) -> Order:
    """Before dispatch only (A-25): stock goes straight back; a paid order gets a refund request."""
    order = lock(order_id)
    if order.status not in BEFORE_DISPATCH:
        raise ApiProblem(409, "invalid-transition", "Only orders that haven't been dispatched can be cancelled.")
    was_awaiting = order.status == S.AWAITING_PAYMENT
    if was_awaiting:
        stock.release(order.pk, order.number)
    else:
        stock.restore(order.pk, order.number, actor.label)
    order.cancel_reason = reason[:200]
    order.reservation_expires_at = None
    order.save(update_fields=["cancel_reason", "reservation_expires_at", "updated_at"])
    _move(order, S.CANCELLED, actor.label, reason)
    if order.payment_method == PaymentMethod.COD:
        set_payment_status(order, PaymentStatus.COD_CANCELLED, actor.label, reason)
    elif order.payment_status == PaymentStatus.PAID:
        from apps.payments import services as payments

        payments.request_refund(order, order.total, f"Order cancelled: {reason}", actor, source="cancellation")
    if not expired:
        record(
            "order.cancel",
            actor,
            target_type="order",
            target_id=order.number,
            after={"reason": reason},
            request=request,
        )
    _email(order, "order_cancelled", reason=reason, expired=expired)
    return order


@transaction.atomic
def advance(order_id: Any, to: str, actor: Actor, reason: str = "", request: Any = None) -> Order:
    """Staff moves an order forward: packing, back to confirmed, delivered, undelivered or returned.

    Dispatch goes through shipping.services.dispatch (it needs a courier and tracking), cancellation through
    cancel(), and confirmation of unpaid online orders only through a verified payment.
    """
    order = lock(order_id)
    if to in (S.DISPATCHED, S.CANCELLED) or (to == S.CONFIRMED and order.status == S.AWAITING_PAYMENT):
        raise ApiProblem(400, "use-dedicated-action", "Use the dedicated action for this change.")
    _move(order, to, actor.label, reason)
    if to == S.DELIVERED:
        if order.payment_method == PaymentMethod.COD:
            set_payment_status(
                order, PaymentStatus.COD_REMITTANCE_PENDING, actor.label, "Delivered; awaiting courier remittance"
            )
        _email(order, "order_delivered")
    if to == S.UNDELIVERED and order.payment_method == PaymentMethod.COD:
        set_payment_status(order, PaymentStatus.COD_CANCELLED, actor.label, "Undelivered: nothing to collect")
    record(f"order.{to}", actor, target_type="order", target_id=order.number, after={"reason": reason}, request=request)
    return order


def mark_dispatched(order: Order, actor: Actor, reason: str) -> None:
    """Called by shipping.services.dispatch inside its transaction, with the order locked."""
    _move(order, S.DISPATCHED, actor.label, reason)
    if order.payment_method == PaymentMethod.COD and order.payment_status != PaymentStatus.COD_COLLECT:
        set_payment_status(order, PaymentStatus.COD_COLLECT, actor.label, "Courier collects on delivery")


def restock_undelivered(order: Order, actor_label: str) -> None:
    """An undelivered parcel came back unopened: its units return to sellable stock."""
    from apps.inventory.models import MovementReason

    stock.restore(order.pk, order.number, actor_label, reason=MovementReason.RETURN)


COD_NEXT: dict[str, set[str]] = {
    PaymentStatus.COD_REMITTANCE_PENDING: {PaymentStatus.COD_REMITTANCE_RECEIVED, PaymentStatus.COD_DISCREPANCY},
    PaymentStatus.COD_REMITTANCE_RECEIVED: {PaymentStatus.COD_RECONCILED, PaymentStatus.COD_DISCREPANCY},
    PaymentStatus.COD_DISCREPANCY: {PaymentStatus.COD_RECONCILED},
}


@transaction.atomic
def cod_remittance(
    order_id: Any,
    action: str,
    actor: Actor,
    *,
    amount: Any = None,
    reference: str = "",
    note: str = "",
    request: Any = None,
) -> Order:
    """Cash on delivery money from the courier (MTS §10): received (with the amount and the courier's reference),
    then reconciled. A short or wrong amount becomes a discrepancy and alerts finance; reconciling a discrepancy
    needs a note saying how it was settled."""
    from decimal import Decimal, InvalidOperation

    order = lock(order_id)
    if order.payment_method != PaymentMethod.COD:
        raise ApiProblem(400, "not-cod", "This order wasn't paid by cash on delivery.")
    if action == "received":
        try:
            received = Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise ApiProblem(400, "amount", "Enter the amount the courier remitted.") from None
        if not reference.strip():
            raise ApiProblem(400, "reference", "Enter the courier's remittance reference.")
        to = PaymentStatus.COD_REMITTANCE_RECEIVED if received == order.total else PaymentStatus.COD_DISCREPANCY
        why = f"Remitted Rs {received:,.2f} (ref {reference.strip()[:60]})"
    elif action == "reconciled":
        to = PaymentStatus.COD_RECONCILED
        if order.payment_status == PaymentStatus.COD_DISCREPANCY and not note.strip():
            raise ApiProblem(400, "note", "Say how the discrepancy was settled.")
        why = note.strip()[:200] or "Reconciled with the courier statement"
    else:
        raise ApiProblem(400, "action", "Unknown remittance action.")
    if to not in COD_NEXT.get(order.payment_status, set()):
        raise ApiProblem(
            409, "invalid-transition", f"Nothing to do: this order is {order.get_payment_status_display().lower()}."
        )
    set_payment_status(order, to, actor.label, why)
    if to == PaymentStatus.COD_DISCREPANCY:
        alert(
            "cod_discrepancy",
            f"Cash on delivery remittance for {order.number} doesn't match the order total.",
            target_type="order",
            target_id=order.number,
            dedupe_key=f"cod_discrepancy:{order.number}",
        )
    record(
        f"order.cod_{action}",
        actor,
        target_type="order",
        target_id=order.number,
        after={"amount": None if amount is None else str(amount), "reference": reference, "note": note},
        request=request,
    )
    return order


def expire_due(now: Any = None, limit: int = 100) -> int:
    """Unpaid online orders past their reservation (MTS §11). One at a time, row-locked with SKIP LOCKED, and the
    provider is always asked first, so expiry never races a payment."""
    from apps.payments import services as payments

    now = now or timezone.now()
    done = 0
    for _ in range(limit):
        with transaction.atomic():
            order = (
                Order.objects.select_for_update(skip_locked=True)
                .filter(status=S.AWAITING_PAYMENT, reservation_expires_at__lte=now)
                .order_by("reservation_expires_at")
                .first()
            )
            if order is None:
                break
            verdict = payments.final_check_before_expiry(order)
            if verdict == "paid":
                done += 1
                continue  # confirm_paid already ran inside the check
            if verdict.startswith("hold:"):
                order.reservation_expires_at = datetime.fromisoformat(verdict[5:])
                order.save(update_fields=["reservation_expires_at", "updated_at"])
                continue
            cancel(order.pk, Actor(None, "system"), "Payment wasn't completed in time", expired=True)
            done += 1
    return done
