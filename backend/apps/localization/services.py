"""Tax from effective-dated rules (MTS §10). With no rule in force, tax is zero (P-11 pending)."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q
from django.utils import timezone

from .models import TaxRule

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Tax:
    amount: Decimal
    included: bool  # True: already inside the prices shown; False: added on top
    label: str


def rule_in_force(on: date | None = None) -> TaxRule | None:
    day = on or timezone.localdate()
    return (
        TaxRule.objects.filter(effective_from__lte=day)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
        .order_by("-effective_from")
        .first()
    )


def compute(goods: Decimal, shipping: Decimal, on: date | None = None) -> Tax:
    rule = rule_in_force(on)
    if rule is None:
        return Tax(Decimal("0.00"), True, "")
    base = goods + (shipping if rule.applies_to_shipping else Decimal("0"))
    amount = base * rule.rate / (1 + rule.rate) if rule.prices_include_tax else base * rule.rate
    return Tax(amount.quantize(CENT, ROUND_HALF_UP), rule.prices_include_tax, rule.name)
