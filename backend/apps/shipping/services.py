"""Shipping options for an address (MTS §10). Fees come only from staff-maintained zones and rates."""

from dataclasses import dataclass
from decimal import Decimal

from common.exceptions import ApiProblem

from .models import ShippingMethod, ShippingRate, ShippingZone


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
