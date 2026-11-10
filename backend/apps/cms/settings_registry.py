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


def _bool(value: Any) -> Any:
    if not isinstance(value, bool):
        raise ValueError("Use true or false.")
    return value


def _minutes(value: Any) -> Any:
    if not isinstance(value, int) or isinstance(value, bool) or not 30 <= value <= 1440:
        raise ValueError("Use whole minutes between 30 and 1440.")
    return value


def _count(value: Any) -> Any:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10000:
        raise ValueError("Use a whole number between 0 and 10000.")
    return value


def _long_text(value: Any) -> Any:
    if not isinstance(value, str) or len(value) > 1000:
        raise ValueError("Enter up to 1,000 characters.")
    return value.strip()


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
        # PROVISIONAL until decided (recorded in docs/decisions/provisional-settings.md). Staff can change them.
        SettingSpec(
            "checkout.guest_allowed",
            "store",
            "Guests can check out without an account (P-15, provisional: on)",
            True,
            _bool,
        ),
        SettingSpec(
            "checkout.reservation_minutes",
            "store",
            "Minutes an unpaid online order holds its stock (D-06, provisional: 30; at least 30)",
            30,
            _minutes,
        ),
        SettingSpec(
            "payments.cod_enabled", "store", "Cash on delivery is offered at checkout (provisional: on)", True, _bool
        ),
        SettingSpec(
            "payments.cod_max_order",
            "store",
            "Largest order total that may use cash on delivery (null: no limit)",
            None,
            _money_or_none,
        ),
        SettingSpec(
            "returns.window_days",
            "store",
            "Days after delivery a customer can request a return (P-14, provisional: 7; 0 turns returns off)",
            7,
            _count,
        ),
        SettingSpec(
            "returns.instructions",
            "store",
            "Where and how customers send an approved return (emailed with the approval; P-14 pending)",
            "Pack the items with all tags attached and write your return number on the parcel. "
            "We will email you the courier pickup or drop-off details.",
            _long_text,
        ),
        SettingSpec(
            "inventory.low_stock_default",
            "store",
            "Default low-stock alert level per variant (0: no alerts unless set per variant)",
            2,
            _count,
        ),
    ]
}
