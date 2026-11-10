"""Payment attempts, provider events, status checks and refunds (MTS §10, A-23).

Rules enforced here:
- payments only move forward; an event that would move backwards is stored and ignored;
- an event that contradicts a final state is never applied: the payment is flagged and staff alerted;
- the browser's return never changes a payment: only verified callbacks and direct provider checks do;
- three independent paths confirm payments: callbacks, scheduled status checks, and the checks made before a
  reservation expires.
"""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.cms.services import get_value
from apps.notifications.services import alert, send_email
from apps.orders import services as orders
from apps.orders.models import Order, OrderStatus, PaymentMethod, PaymentStatus
from common.exceptions import ApiProblem
from common.security import new_token
from integrations import payments as adapters

from .models import Payment, PaymentEvent, PaymentState, Refund, RefundState

P = PaymentState
FINAL_SUCCESS = {P.SUCCEEDED, P.PARTLY_REFUNDED, P.REFUNDED}
CHECK_BACKOFF = [60, 120, 300, 600, 1800, 3600]  # seconds between scheduled status checks
REFUND_BACKOFF = [300, 900, 3600, 4 * 3600, 12 * 3600]  # then Manual required


# --- Attempts ------------------------------------------------------------------------------------------------


@transaction.atomic
def start_attempt(order: Order, return_url: str) -> Payment:
    order = orders.lock(order.pk)
    if order.payment_method != PaymentMethod.CARD:
        raise ApiProblem(409, "not-online-payment", "This order is paid on delivery.")
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise ApiProblem(409, "order-not-payable", "This order no longer needs payment.")
    if order.reservation_expires_at and order.reservation_expires_at <= timezone.now():
        raise ApiProblem(409, "order-expired", "The time to pay for this order has run out.")
    adapter = adapters.online_adapter()
    if adapter is None:
        raise ApiProblem(
            503, "payments-unavailable", "Online payment isn't available right now. Please try again shortly."
        )
    payment = Payment.objects.create(order=order, provider=adapter.code, amount=order.total, currency=order.currency)
    try:
        started = adapter.start(str(payment.pk), order.total, order.currency, return_url)
    except Exception as exc:  # provider unreachable: the attempt is recorded as not paid; the shopper may retry
        payment.state, payment.failure_reason = P.NOT_PAID, f"Provider unavailable: {type(exc).__name__}"
        payment.save(update_fields=["state", "failure_reason", "updated_at"])
        alert(
            "payment-provider-error",
            f"Couldn't start a payment with {adapter.code}.",
            dedupe_key=f"provider-down:{adapter.code}",
        )
        raise ApiProblem(
            503, "payments-unavailable", "Online payment isn't available right now. Please try again shortly."
        ) from exc
    payment.state = P.PENDING
    payment.provider_ref = started.provider_ref
    payment.redirect_url = started.redirect_url
    payment.provider_window_ends_at = started.window_ends_at
    payment.next_check_at = timezone.now() + timedelta(seconds=CHECK_BACKOFF[0])
    payment.save()
    # Never let the reservation expire while the shopper can still pay at the provider (D-06).
    if order.reservation_expires_at and order.reservation_expires_at < started.window_ends_at + timedelta(minutes=2):
        order.reservation_expires_at = started.window_ends_at + timedelta(minutes=2)
        order.save(update_fields=["reservation_expires_at", "updated_at"])
    return payment


def _apply(payment: Payment, outcome: str, source: str) -> str:
    """Moves one payment forward. Returns what happened: applied | ignored | conflict."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if outcome == "pending":
        return "ignored"
    if outcome == "succeeded":
        if payment.state in FINAL_SUCCESS:
            return "ignored"
        payment.state, payment.succeeded_at, payment.next_check_at = P.SUCCEEDED, timezone.now(), None
        try:
            with transaction.atomic():
                payment.save()
        except IntegrityError:
            # Another attempt for this order already succeeded: never take money twice silently.
            Payment.objects.filter(pk=payment.pk).update(needs_review=True, review_note="Second successful payment")
            alert(
                "payment-duplicate",
                f"Order {payment.order.number} has two successful payments. Refund one.",
                severity="critical",
                target_type="order",
                target_id=payment.order.number,
            )
            return "conflict"
        orders.confirm_paid(payment.order_id, f"payment {payment.provider}", f"Payment confirmed ({source})")
        return "applied"
    # failed / expired
    if payment.state in FINAL_SUCCESS:
        payment.needs_review, payment.review_note = True, f"Provider reported '{outcome}' after success ({source})"
        payment.save(update_fields=["needs_review", "review_note", "updated_at"])
        alert(
            "payment-conflict",
            f"Payment for order {payment.order.number} was reported {outcome} after it succeeded.",
            severity="critical",
            target_type="order",
            target_id=payment.order.number,
        )
        return "conflict"
    if payment.state == P.NOT_PAID:
        return "ignored"
    payment.state, payment.failure_reason, payment.next_check_at = P.NOT_PAID, outcome, None
    payment.save(update_fields=["state", "failure_reason", "next_check_at", "updated_at"])
    return "applied"


def receive_webhook(provider: str, body: bytes, headers: dict[str, str]) -> int:
    """Signature first; each event stored once, then applied. Returns the number of events applied."""
    adapter = adapters.get(provider)
    if adapter is None:
        raise ApiProblem(404, "not-found", "Unknown provider.")
    try:
        events = adapter.parse_webhook(body, {k.lower(): v for k, v in headers.items()})
    except adapters.InvalidSignature as exc:
        alert(
            "webhook-bad-signature",
            f"A {provider} callback failed its signature check.",
            dedupe_key=f"badsig:{provider}",
        )
        raise ApiProblem(400, "invalid-signature", "Signature check failed.") from exc
    applied = 0
    for ev in events:
        with transaction.atomic():
            try:
                with transaction.atomic():
                    stored = PaymentEvent.objects.create(
                        provider=provider, event_id=ev.event_id, kind=ev.kind, payload=ev.data, signature_valid=True
                    )
            except IntegrityError:
                continue  # duplicate delivery: acknowledged, not applied again
            payment = (
                Payment.objects.filter(provider=provider, provider_ref=ev.provider_ref).select_related("order").first()
            )
            stored.payment = payment
            if payment is None:
                stored.outcome = "unknown-payment"
            else:
                outcome = {
                    "payment.succeeded": "succeeded",
                    "payment.failed": "failed",
                    "payment.expired": "expired",
                }.get(ev.kind, "pending")
                if outcome == "succeeded":
                    # Where the provider supports it, confirm success with a direct check before applying (A-23).
                    check = adapter.check(payment.provider_ref)
                    if check.state != "succeeded":
                        stored.outcome = "unconfirmed"
                        stored.processed_at = timezone.now()
                        stored.save()
                        continue
                stored.outcome = _apply(payment, outcome, "callback")
                applied += stored.outcome == "applied"
            stored.processed_at = timezone.now()
            stored.save()
    return applied


@transaction.atomic
def check(payment: Payment, source: str = "status check") -> str:
    """Asks the provider directly. Used by the return page, the scheduled job and before expiry."""
    adapter = adapters.get(payment.provider)
    if adapter is None or payment.state != P.PENDING:
        return payment.state
    try:
        result = adapter.check(payment.provider_ref)
    except Exception:  # provider outage: try again later
        result = adapters.CheckResult("pending", "provider unreachable")
    PaymentEvent.objects.create(
        provider=payment.provider,
        event_id=f"check:{payment.pk}:{new_token(6)}",
        payment=payment,
        kind="check",
        payload={"state": result.state, "reason": result.reason},
        signature_valid=True,
        processed_at=timezone.now(),
        outcome=result.state,
    )
    if result.state == "pending":
        payment.check_count += 1
        delay = CHECK_BACKOFF[min(payment.check_count, len(CHECK_BACKOFF) - 1)]
        payment.next_check_at = timezone.now() + timedelta(seconds=delay)
        payment.save(update_fields=["check_count", "next_check_at", "updated_at"])
        return P.PENDING
    _apply(payment, result.state, source)
    payment.refresh_from_db()
    return payment.state


def check_pending(limit: int = 200) -> int:
    due = Payment.objects.filter(state=P.PENDING, next_check_at__lte=timezone.now()).order_by("next_check_at")[:limit]
    n = 0
    for p in due:
        check(p, "scheduled check")
        n += 1
    return n


def final_check_before_expiry(order: Order) -> str:
    """Called with the order locked. 'paid' (confirmed now), 'hold:<iso time>' or 'release'."""
    for p in Payment.objects.filter(order=order, state=P.PENDING).order_by("-created_at"):
        state = check(p, "check before expiry")
        if state in FINAL_SUCCESS:
            return "paid"
        if state == P.PENDING and p.provider_window_ends_at and p.provider_window_ends_at > timezone.now():
            return "hold:" + (p.provider_window_ends_at + timedelta(minutes=2)).isoformat()
    return "release"


# --- Refunds -------------------------------------------------------------------------------------------------


def _refundable(order: Order) -> tuple[Payment | None, Decimal]:
    payment = Payment.objects.filter(order=order, state__in=list(FINAL_SUCCESS)).first()
    open_or_done = sum((r.amount for r in order.refunds.exclude(state=RefundState.REJECTED)), Decimal("0.00"))
    if order.payment_method == PaymentMethod.COD:
        collected = order.payment_status in (
            PaymentStatus.COD_REMITTANCE_RECEIVED,
            PaymentStatus.COD_RECONCILED,
            PaymentStatus.COD_REMITTANCE_PENDING,
        )
        return None, (order.total - open_or_done) if collected else Decimal("0.00")
    if payment is None:
        return None, Decimal("0.00")
    return payment, payment.amount - open_or_done


@transaction.atomic
def request_refund(
    order: Order,
    amount: Decimal,
    reason: str,
    actor: Actor,
    *,
    source: str = "staff",
    auto_approve: bool = False,
    request: Any = None,
) -> Refund:
    order = orders.lock(order.pk)
    payment, remaining = _refundable(order)
    if amount <= 0 or amount > remaining:
        raise ApiProblem(400, "refund-amount", f"You can refund up to Rs {remaining:,.2f} on this order.")
    refund = Refund.objects.create(
        order=order, payment=payment, amount=amount, reason=reason[:300], source=source, requested_by=actor.label
    )
    record(
        "refund.request",
        actor,
        target_type="order",
        target_id=order.number,
        after={"amount": str(amount), "reason": reason},
        request=request,
    )
    if auto_approve:
        refund.state, refund.approved_by = RefundState.APPROVED, "system (automatic)"
        refund.save(update_fields=["state", "approved_by", "updated_at"])
        transaction.on_commit(lambda: process_refund(refund.pk))
    return refund


def _threshold() -> Decimal | None:
    value = get_value("refunds.dual_approval_threshold")
    return None if value is None else Decimal(value["amount"])


@transaction.atomic
def approve_refund(refund_id: Any, actor: Actor, request: Any = None) -> Refund:
    """Decision 0003, 1.5: with no threshold set, every refund needs a second approver; above the threshold too.
    The requester can never approve their own refund."""
    refund = Refund.objects.select_for_update().get(pk=refund_id)
    if refund.state != RefundState.REQUESTED:
        raise ApiProblem(409, "refund-state", "This refund isn't waiting for approval.")
    if actor.label in (refund.requested_by, refund.approved_by):
        raise ApiProblem(403, "four-eyes", "Someone else needs to approve this refund.")
    threshold = _threshold()
    needs_two = threshold is None or refund.amount > threshold
    if needs_two and not refund.approved_by:
        refund.approved_by = actor.label
        refund.save(update_fields=["approved_by", "updated_at"])
        record("refund.approve_first", actor, target_type="refund", target_id=refund.pk, request=request)
        return refund
    if needs_two:
        refund.second_approved_by = actor.label
    else:
        refund.approved_by = actor.label
    refund.state = RefundState.APPROVED
    refund.save()
    record("refund.approve", actor, target_type="refund", target_id=refund.pk, request=request)
    transaction.on_commit(lambda: process_refund(refund.pk))
    return refund


@transaction.atomic
def reject_refund(refund_id: Any, actor: Actor, note: str, request: Any = None) -> Refund:
    refund = Refund.objects.select_for_update().get(pk=refund_id)
    if refund.state != RefundState.REQUESTED:
        raise ApiProblem(409, "refund-state", "This refund isn't waiting for approval.")
    refund.state, refund.decision_note = RefundState.REJECTED, note[:300]
    refund.save()
    record("refund.reject", actor, target_type="refund", target_id=refund.pk, after={"note": note}, request=request)
    return refund


def _recompute_order_payment(order: Order, actor_label: str) -> None:
    done = sum(
        (r.amount for r in order.refunds.filter(state__in=[RefundState.SUCCEEDED, RefundState.MANUAL_COMPLETED])),
        Decimal("0.00"),
    )
    if done <= 0 or order.payment_method == PaymentMethod.COD:
        return
    orders.set_payment_status(
        order,
        PaymentStatus.REFUNDED if done >= order.total else PaymentStatus.PARTLY_REFUNDED,
        actor_label,
        "Refund completed",
    )


@transaction.atomic
def process_refund(refund_id: Any) -> Refund:
    refund = Refund.objects.select_for_update(of=("self",)).select_related("order", "payment").get(pk=refund_id)
    if refund.state not in (RefundState.APPROVED, RefundState.FAILED):
        return refund
    order = refund.order
    if refund.payment is None:  # COD and other offline payments are refunded by hand (MTS §10)
        refund.state = RefundState.MANUAL_REQUIRED
        refund.save(update_fields=["state", "updated_at"])
        alert(
            "refund-manual",
            f"Refund of Rs {refund.amount:,.2f} for order {order.number} must be paid manually.",
            target_type="refund",
            target_id=refund.pk,
        )
        return refund
    adapter = adapters.get(refund.payment.provider)
    refund.state, refund.attempts = RefundState.PROCESSING, refund.attempts + 1
    refund.save(update_fields=["state", "attempts", "updated_at"])
    try:
        result = (
            adapter.refund(refund.payment.provider_ref, refund.amount, str(refund.pk))
            if adapter
            else adapters.RefundResult(False, error="provider not available", retryable=True)
        )
    except Exception as exc:
        result = adapters.RefundResult(False, error=f"{type(exc).__name__}", retryable=True)
    if result.ok:
        refund.state, refund.provider_ref, refund.completed_at, refund.next_retry_at = (
            RefundState.SUCCEEDED,
            result.provider_ref,
            timezone.now(),
            None,
        )
        refund.save()
        payment = Payment.objects.select_for_update().get(pk=refund.payment.pk)
        payment.refunded_amount += refund.amount
        payment.state = P.REFUNDED if payment.refunded_amount >= payment.amount else P.PARTLY_REFUNDED
        payment.save(update_fields=["refunded_amount", "state", "updated_at"])
        _recompute_order_payment(order, "refunds")
        send_email([order.email], "refund_completed", {"number": order.number, "amount": f"{refund.amount:,.2f}"})
        return refund
    refund.last_error = result.error[:300]
    if not result.retryable or refund.attempts > len(REFUND_BACKOFF):
        refund.state, refund.next_retry_at = RefundState.MANUAL_REQUIRED, None
        refund.save()
        alert(
            "refund-manual",
            f"Refund for order {order.number} failed ({result.error}) and needs a manual payment.",
            severity="critical",
            target_type="refund",
            target_id=refund.pk,
        )
        return refund
    refund.state = RefundState.FAILED
    refund.next_retry_at = timezone.now() + timedelta(seconds=REFUND_BACKOFF[refund.attempts - 1])
    refund.save()
    return refund


def retry_due_refunds() -> int:
    ids = list(
        Refund.objects.filter(state=RefundState.FAILED, next_retry_at__lte=timezone.now()).values_list("pk", flat=True)[
            :100
        ]
    )
    for rid in ids:
        process_refund(rid)
    return len(ids)


@transaction.atomic
def complete_manual(refund_id: Any, reference: str, actor: Actor, request: Any = None) -> Refund:
    refund = Refund.objects.select_for_update(of=("self",)).select_related("order").get(pk=refund_id)
    if refund.state != RefundState.MANUAL_REQUIRED:
        raise ApiProblem(409, "refund-state", "This refund isn't waiting for a manual payment.")
    refund.state, refund.manual_reference, refund.completed_at = (
        RefundState.MANUAL_COMPLETED,
        reference[:120],
        timezone.now(),
    )
    refund.save()
    record(
        "refund.manual_complete",
        actor,
        target_type="refund",
        target_id=refund.pk,
        after={"reference": reference},
        request=request,
    )
    _recompute_order_payment(refund.order, actor.label)
    send_email(
        [refund.order.email], "refund_completed", {"number": refund.order.number, "amount": f"{refund.amount:,.2f}"}
    )
    return refund


def resolve_review(payment_id: Any, actor: Actor, note: str, request: Any = None) -> None:
    Payment.objects.filter(pk=payment_id).update(needs_review=False, review_note=note[:300])
    record(
        "payment.review_resolved",
        actor,
        target_type="payment",
        target_id=payment_id,
        after={"note": note},
        request=request,
    )
