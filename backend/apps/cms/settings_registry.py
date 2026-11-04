"""Every store setting, who may change it and how its value is validated.

Settings come in two groups (decision 0003, 1.3): `store` settings (Owner and Store Admin) and
`security` settings (Owner only). A key that isn't declared here can't be stored."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

Group = Literal["store", "security"]


@dataclass(frozen=True)
class SettingSpec:
    key: str
    group: Group
    label: str
    default: Any
    validate: Callable[[Any], Any]


def _money_or_none(value: Any) -> Any:
    """`null` or {"amount": "<decimal string>", "currency": "PKR"}, as everywhere in the API (MTS §8)."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"amount", "currency"}:
        raise ValueError('Use null or {"amount": "25000.00", "currency": "PKR"}.')
    try:
        amount = Decimal(str(value["amount"]))
    except InvalidOperation as exc:
        raise ValueError("The amount must be a decimal number.") from exc
    if amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("The amount must be zero or more, with at most two decimal places.")
    if not isinstance(value["currency"], str) or len(value["currency"]) != 3 or not value["currency"].isupper():
        raise ValueError("The currency must be a three-letter code such as PKR.")
    return {"amount": f"{amount:.2f}", "currency": value["currency"]}


def _short_text(value: Any) -> Any:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError("Use text of up to 200 characters.")
    return value.strip()


SETTINGS: dict[str, SettingSpec] = {
    spec.key: spec
    for spec in [
        # Decision 0003, 1.5. Unset (null) means every refund needs a second approver; the amount is decided at M8.
        SettingSpec(
            "refunds.dual_approval_threshold",
            "security",
            "Refunds above this amount need a second approver",
            None,
            _money_or_none,
        ),
        SettingSpec("store.support_email", "store", "Customer support email address", "", _short_text),
    ]
}
