"""Shipping options for an address, dispatch and tracking (MTS §10). Fees come only from staff-maintained zones
and rates; couriers come through integrations.couriers."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services import Actor, record
from apps.notifications.services import alert, send_email, send_sms
from common.exceptions import ApiProblem
from integrations import couriers

from .models import Shipment, ShipmentStatus, ShippingMethod, ShippingRate, ShippingZone, TrackingEvent


@dataclass(frozen=True)
class Option:
    zone: str
    method: str
    label: str
    fee: Decimal
    standard_fee: Decimal
    free_over: Decimal | None
    days_min: int
    days_max: int
    cod_allowed: bool
    cod_fee: Decimal


def match_zone(city: str, province: str) -> ShippingZone | None:
    city_key = city.strip().lower()
    zones = list(ShippingZone.objects.all())
    for z in zones:
        if city_key in {c.lower() for c in z.cities}:
            return z
    for z in zones:
        if province in z.provinces:
            return z
    return next((z for z in zones if z.is_fallback), None)


def options(city: str, province: str, goods_total: Decimal) -> list[Option]:
    zone = match_zone(city, province)
    if zone is None:
        return []
    result = []
    for r in ShippingRate.objects.filter(zone=zone, is_active=True).order_by("fee"):
        free = r.free_over is not None and goods_total >= r.free_over
        result.append(
            Option(
                zone=zone.code,
                method=r.method,
                label=ShippingMethod(r.method).label,
                fee=Decimal("0.00") if free else r.fee,
                standard_fee=r.fee,
                free_over=r.free_over,
                days_min=r.days_min,
                days_max=r.days_max,
                cod_allowed=r.cod_allowed,
                cod_fee=r.cod_fee,
            )
        )
    return result


def choose(city: str, province: str, goods_total: Decimal, method: str) -> Option:
    for o in options(city, province, goods_total):
        if o.method == method:
            return o
    raise ApiProblem(400, "shipping-unavailable", "This delivery option isn't available for this address.")


# --- Dispatch and tracking (MTS §10, A-24) --------------------------------------------------------------------

# Shipment progress: forward only, plus the failed-delivery path back to AureVon.
SHIPMENT_NEXT: dict[str, set[str]] = {
    "booked": {"in_transit", "out_for_delivery", "delivered", "failed", "returning"},
    "in_transit": {"out_for_delivery", "delivered", "failed", "returning"},
    "out_for_delivery": {"delivered", "failed", "in_transit"},
    "failed": {"out_for_delivery", "returning", "returned"},
    "returning": {"returned"},
    "delivered": set(),
    "returned": set(),
}


def dispatch(
    order_id: Any, courier_code: str, tracking_number: str, tracking_url: str, actor: Actor, request: Any = None
) -> Shipment:
    """A packed order goes out: the shipment is booked, the order becomes dispatched and the customer is told.
    Cash on delivery: the shipment carries the amount the courier must collect."""
    from apps.orders import services as orders
    from apps.orders.models import OrderStatus, PaymentMethod

    courier = couriers.get(courier_code)
    if courier is None:
        raise ApiProblem(400, "courier", "Choose a courier.")
    tracking_number = tracking_number.strip()[:60]
    tracking_url = tracking_url.strip()[:200]
    if not courier.books_automatically and not tracking_number:
        raise ApiProblem(400, "tracking", "Enter the courier's tracking number.")
    if tracking_url and not tracking_url.startswith("https://"):
        raise ApiProblem(400, "tracking", "The tracking link must start with https://")
    with transaction.atomic():
        order = orders.lock(order_id)
        if order.status != OrderStatus.PACKING:
            raise ApiProblem(409, "invalid-transition", "Only orders being packed can be dispatched.")
        booking = courier.book(order.number, tracking_number, tracking_url)
        if (
            Shipment.objects.filter(courier=courier.code, tracking_number=booking.tracking_number)
            .exclude(tracking_number="")
            .exists()
        ):
            raise ApiProblem(409, "tracking", "Another shipment already uses this tracking number.")
        shipment = Shipment.objects.create(
            order=order,
            courier=courier.code,
            tracking_number=booking.tracking_number,
            tracking_url=booking.tracking_url,
            cod_amount=order.total if order.payment_method == PaymentMethod.COD else Decimal("0.00"),
        )
        TrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentStatus.BOOKED,
            description="Booked with the courier",
            occurred_at=timezone.now(),
            source="staff",
        )
        orders.mark_dispatched(order, actor, f"{courier.label}: {booking.tracking_number}".strip(": "))
        record(
            "order.dispatch",
            actor,
            target_type="order",
            target_id=order.number,
            after={"courier": courier.code, "tracking_number": booking.tracking_number},
            request=request,
        )
        send_email(
            [order.email],
            "order_dispatched",
            {
                "number": order.number,
                "courier": courier.label if courier.code != "manual" else "our courier",
                "tracking_number": booking.tracking_number,
                "tracking_url": booking.tracking_url,
                "link": orders._link(order),
            },
        )
        send_sms(order.phone, dispatch_sms(order.number, order.locale, booking.tracking_url), consent_email=order.email)
    return shipment


def dispatch_sms(number: str, locale: str, tracking_url: str) -> str:
    if locale == "ur":
        return f"AureVon: آپ کا آرڈر {number} روانہ کر دیا گیا ہے۔ ٹریک کریں: {tracking_url}"  # noqa: RUF001
    return f"AureVon: your order {number} is on its way. Track it: {tracking_url}"


def add_event(
    shipment_id: Any,
    status: str,
    actor: Actor,
    *,
    description: str = "",
    location: str = "",
    occurred_at: Any = None,
    source: str = "staff",
    external_id: str = "",
    request: Any = None,
) -> Shipment:
    """A tracking update. Delivered completes the order; returned to AureVon makes it undelivered and puts the
    unopened parcel's units back into sellable stock."""
    from apps.orders import services as orders
    from apps.orders.models import OrderStatus

    if status not in ShipmentStatus.values:
        raise ApiProblem(400, "status", "Unknown tracking status.")
    with transaction.atomic():
        shipment = Shipment.objects.select_for_update().select_related("order").get(pk=shipment_id)
        if external_id and shipment.events.filter(external_id=external_id).exists():
            return shipment  # a courier update we already have
        if status not in SHIPMENT_NEXT[shipment.status]:
            raise ApiProblem(
                409,
                "invalid-transition",
                f"A shipment that is {ShipmentStatus(shipment.status).label.lower()} can't become "
                f"{ShipmentStatus(status).label.lower()}.",
            )
        TrackingEvent.objects.create(
            shipment=shipment,
            status=status,
            description=description.strip()[:200],
            location=location.strip()[:80],
            occurred_at=occurred_at or timezone.now(),
            source=source,
            external_id=external_id[:80],
        )
        shipment.status = status
        fields = ["status"]
        if status == ShipmentStatus.DELIVERED:
            shipment.delivered_at = timezone.now()
            fields.append("delivered_at")
        shipment.save(update_fields=fields)
        order = shipment.order
        if status == ShipmentStatus.DELIVERED and order.status == OrderStatus.DISPATCHED:
            orders.advance(order.pk, OrderStatus.DELIVERED, actor, "Courier: delivered", request)
        elif status == ShipmentStatus.RETURNED and order.status == OrderStatus.DISPATCHED:
            orders.advance(order.pk, OrderStatus.UNDELIVERED, actor, "Parcel returned to AureVon", request)
            orders.restock_undelivered(order, actor.label)
        elif status == ShipmentStatus.FAILED:
            alert(
                "delivery_failed",
                f"Delivery failed for order {order.number}. Contact the customer or arrange a return.",
                target_type="order",
                target_id=order.number,
                dedupe_key=f"delivery_failed:{shipment.pk}",
            )
    return shipment
