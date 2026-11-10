"""Demo delivery zones and rates for local review and tests ONLY. The real zones, fees, free-delivery
thresholds and delivery promises are pending decision P-13 and are entered by staff."""

from decimal import Decimal

from .models import ShippingRate, ShippingZone

DEMO_ZONES = [
    # code, name, cities, provinces, fallback, standard fee, express fee, days std, days exp
    ("karachi", "Karachi", ["Karachi"], [], False, "250", "450", (1, 3), (1, 1)),
    ("lahore", "Lahore", ["Lahore"], [], False, "250", "450", (1, 3), (1, 1)),
    (
        "islamabad",
        "Islamabad and Rawalpindi",
        ["Islamabad", "Rawalpindi"],
        ["ict"],
        False,
        "250",
        "450",
        (1, 3),
        (1, 1),
    ),
    ("rest", "Rest of Pakistan", [], [], True, "350", "650", (3, 6), (2, 3)),
]


def seed() -> None:
    for position, (code, name, cities, provinces, fallback, std, exp, dstd, dexp) in enumerate(DEMO_ZONES):
        zone, _ = ShippingZone.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "cities": cities,
                "provinces": provinces,
                "is_fallback": fallback,
                "position": position,
            },
        )
        ShippingRate.objects.update_or_create(
            zone=zone,
            method="standard",
            defaults={
                "fee": Decimal(std),
                "free_over": Decimal("15000"),
                "days_min": dstd[0],
                "days_max": dstd[1],
                "cod_allowed": True,
                "cod_fee": Decimal("0"),
            },
        )
        ShippingRate.objects.update_or_create(
            zone=zone,
            method="express",
            defaults={
                "fee": Decimal(exp),
                "free_over": None,
                "days_min": dexp[0],
                "days_max": dexp[1],
                "cod_allowed": True,
                "cod_fee": Decimal("0"),
            },
        )
