"""Business reports from the order, stock, returns and coupon records (MTS §6 "Analytics"; M13).

Definitions (provisional until P-16 sets the analytics definitions; recorded in docs/decisions/provisional-settings):
- A *sale* is an order that was accepted: confirmed or later (packing, dispatched, delivered, returned,
  undelivered). Orders still awaiting online payment and cancelled orders are not sales. Exchange replacements
  (no charge) are left out so units aren't counted twice.
- Days are Pakistan days (Asia/Karachi), by when the order was placed.
- Gross sales = order totals (goods after discount, plus delivery, COD fee and any added tax).
- Refunds = refunds paid out (by the provider or manually) in the period, by when they were completed.
- Net sales = gross sales - refunds.
These are management figures, not accounting statements: the accountant's books remain the record.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate

from apps.inventory.models import MAIN_WAREHOUSE, InventoryItem
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus
from apps.payments.models import Refund, RefundState
from apps.promotions.models import CouponRedemption
from apps.returns.models import ReturnItem, ReturnRequest, ReturnStatus

ZERO = Decimal("0.00")
SALE_STATUSES = [
    OrderStatus.CONFIRMED,
    OrderStatus.PACKING,
    OrderStatus.DISPATCHED,
    OrderStatus.DELIVERED,
    OrderStatus.RETURNED,
    OrderStatus.UNDELIVERED,
]
DEFINITIONS = (
    "Sales are orders confirmed or later (not awaiting payment, not cancelled, not exchange replacements), "
    "counted on the Pakistan day they were placed. Gross sales are order totals after discounts, including "
    "delivery and cash-on-delivery fees. Refunds are refunds paid out in the period. Net sales = gross sales "
    "minus refunds. Provisional until P-16 sets the analytics definitions; the accountant's books remain the record."
)
PAID_OUT = [RefundState.SUCCEEDED, RefundState.MANUAL_COMPLETED]
MAX_DAYS = 400


def tz() -> ZoneInfo:
    return ZoneInfo(settings.DISPLAY_TIME_ZONE)


@dataclass(frozen=True)
class Period:
    start: date  # inclusive, Pakistan time
    end: date  # inclusive

    @property
    def since(self) -> datetime:
        return datetime.combine(self.start, time.min, tzinfo=tz())

    @property
    def until(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=tz())

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> "Period":
        return Period(self.start - timedelta(days=self.days), self.start - timedelta(days=1))


def period(start: date | None, end: date | None, today: date | None = None) -> Period:
    today = today or datetime.now(tz()).date()
    end = end or today
    start = start or end - timedelta(days=29)
    if start > end:
        start, end = end, start
    if (end - start).days + 1 > MAX_DAYS:
        start = end - timedelta(days=MAX_DAYS - 1)
    return Period(start, end)


def sales_orders(p: Period) -> Any:
    return Order.objects.filter(placed_at__gte=p.since, placed_at__lt=p.until, status__in=SALE_STATUSES).exclude(
        payment_method=PaymentMethod.EXCHANGE
    )


def _money(value: Any) -> Decimal:
    return (value or ZERO).quantize(Decimal("0.01"))


def summary(p: Period) -> dict[str, Any]:
    orders = sales_orders(p)
    agg = orders.aggregate(
        n=Count("id"),
        gross=Sum("total"),
        discount=Sum("discount"),
        shipping=Sum("shipping_fee"),
        cod_fees=Sum("cod_fee"),
        tax=Sum("tax"),
    )
    units = OrderItem.objects.filter(order__in=orders).aggregate(n=Sum("quantity"))["n"] or 0
    refunds = _money(
        Refund.objects.filter(state__in=PAID_OUT, completed_at__gte=p.since, completed_at__lt=p.until).aggregate(
            s=Sum("amount")
        )["s"]
    )
    placed = Order.objects.filter(placed_at__gte=p.since, placed_at__lt=p.until).exclude(
        payment_method=PaymentMethod.EXCHANGE
    )
    n = agg["n"] or 0
    gross = _money(agg["gross"])
    by_method = {
        m: _money(orders.filter(payment_method=m).aggregate(s=Sum("total"))["s"])
        for m in (PaymentMethod.CARD, PaymentMethod.COD)
    }
    cod_outstanding = _money(
        Order.objects.filter(
            payment_method=PaymentMethod.COD,
            payment_status__in=[PaymentStatus.COD_REMITTANCE_PENDING, PaymentStatus.COD_DISCREPANCY],
        ).aggregate(s=Sum("total"))["s"]
    )
    return {
        "orders": n,
        "units": units,
        "gross_sales": gross,
        "discounts": _money(agg["discount"]),
        "shipping": _money(agg["shipping"]),
        "cod_fees": _money(agg["cod_fees"]),
        "tax": _money(agg["tax"]),
        "refunds": refunds,
        "net_sales": gross - refunds,
        "average_order": (gross / n).quantize(Decimal("0.01")) if n else ZERO,
        "cancelled": placed.filter(status=OrderStatus.CANCELLED).count(),
        "awaiting_payment": placed.filter(status=OrderStatus.AWAITING_PAYMENT).count(),
        "card_sales": by_method[PaymentMethod.CARD],
        "cod_sales": by_method[PaymentMethod.COD],
        "cod_outstanding": cod_outstanding,  # all time: delivered COD money not yet reconciled
    }


def daily(p: Period) -> list[dict[str, Any]]:
    rows = {
        r["day"]: r
        for r in sales_orders(p)
        .annotate(day=TruncDate("placed_at", tzinfo=tz()))
        .values("day")
        .annotate(orders=Count("id"), gross=Sum("total"))
    }
    out = []
    for i in range(p.days):
        d = p.start + timedelta(days=i)
        r = rows.get(d)
        out.append({"day": d, "orders": r["orders"] if r else 0, "gross_sales": _money(r["gross"] if r else None)})
    return out


def products(p: Period, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        OrderItem.objects.filter(order__in=sales_orders(p))
        .values("product_slug", "name")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"), returned=Sum("returned_quantity"))
        .order_by("-revenue", "product_slug")[:limit]
    )
    return [
        {
            "product": r["product_slug"],
            "name": r["name"],
            "units": r["units"],
            "revenue": _money(r["revenue"]),
            "returned_units": r["returned"] or 0,
        }
        for r in rows
    ]


def categories(p: Period) -> list[dict[str, Any]]:
    rows = (
        OrderItem.objects.filter(order__in=sales_orders(p))
        .values(category=F("variant__product__category__slug"))
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue")
    )
    return [{"category": r["category"], "units": r["units"], "revenue": _money(r["revenue"])} for r in rows]


def cities(p: Period, limit: int = 10) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for city, total in sales_orders(p).values_list("shipping_address__city", "total"):
        key = str(city or "").strip().title() or "Unknown"
        row = totals.setdefault(key, {"city": key, "orders": 0, "gross_sales": ZERO})
        row["orders"] += 1
        row["gross_sales"] += total
    return sorted(totals.values(), key=lambda r: (-r["gross_sales"], r["city"]))[:limit]


def customers(p: Period) -> dict[str, Any]:
    from apps.accounts.models import Account, AccountType

    orders = sales_orders(p)
    with_account = orders.filter(account__isnull=False)
    buyers = with_account.values("account").distinct().count()
    returning = (
        with_account.values("account")
        .annotate(before=Count("account__orders", filter=Q(account__orders__placed_at__lt=p.since)))
        .filter(before__gt=0)
        .count()
    )
    return {
        "new_accounts": Account.objects.filter(
            account_type=AccountType.CUSTOMER, created_at__gte=p.since, created_at__lt=p.until
        ).count(),
        "guest_orders": orders.filter(account__isnull=True).count(),
        "account_orders": with_account.count(),
        "buying_accounts": buyers,
        "returning_accounts": returning,
    }


def returns(p: Period) -> dict[str, Any]:
    qs = ReturnRequest.objects.filter(created_at__gte=p.since, created_at__lt=p.until)
    units_sold = OrderItem.objects.filter(order__in=sales_orders(p)).aggregate(n=Sum("quantity"))["n"] or 0
    units_returned = (
        ReturnItem.objects.filter(
            request__in=qs.exclude(status__in=[ReturnStatus.CANCELLED, ReturnStatus.REJECTED])
        ).aggregate(n=Sum("quantity"))["n"]
        or 0
    )
    from apps.returns.services import REASONS

    return {
        "requests": qs.count(),
        "refunds": qs.filter(kind="refund").count(),
        "exchanges": qs.filter(kind="exchange").count(),
        "units_returned": units_returned,
        "return_rate_percent": round(units_returned * 100 / units_sold, 1) if units_sold else 0.0,
        "by_reason": [
            {"reason": REASONS.get(r["reason"], r["reason"]), "count": r["n"]}
            for r in qs.values("reason").annotate(n=Count("id")).order_by("-n")
        ],
    }


def coupons(p: Period) -> list[dict[str, Any]]:
    rows = (
        CouponRedemption.objects.filter(created_at__gte=p.since, created_at__lt=p.until)
        .values(code=F("coupon__code"))
        .annotate(uses=Count("id"), discount=Sum("amount"), orders_value=Sum("order__total"))
        .order_by("-uses")
    )
    return [
        {
            "code": r["code"],
            "uses": r["uses"],
            "discount": _money(r["discount"]),
            "orders_value": _money(r["orders_value"]),
        }
        for r in rows
    ]


def inventory() -> dict[str, Any]:
    sellable = InventoryItem.objects.filter(location_id=MAIN_WAREHOUSE, variant__is_active=True)
    agg = sellable.aggregate(units=Sum("on_hand"), reserved=Sum("reserved"))
    value = sum(
        (i.on_hand * i.variant.price for i in sellable.select_related("variant").only("on_hand", "variant__price")),
        ZERO,
    )
    return {
        "sellable_units": agg["units"] or 0,
        "reserved_units": agg["reserved"] or 0,
        "retail_value": _money(value),
        "out_of_stock": sellable.filter(on_hand__lte=F("reserved")).count(),
        "low_stock": sellable.filter(reorder_level__gt=0, on_hand__lte=F("reorder_level") + F("reserved")).count(),
        "quarantine_units": InventoryItem.objects.filter(location_id="quarantine").aggregate(n=Sum("on_hand"))["n"]
        or 0,
        "damaged_units": InventoryItem.objects.filter(location_id="damaged").aggregate(n=Sum("on_hand"))["n"] or 0,
    }


def change(now: Decimal | int, before: Decimal | int) -> float | None:
    """Percent change against the previous period of the same length; None when there was nothing before."""
    if not before:
        return None
    return round(float((Decimal(now) - Decimal(before)) * 100 / Decimal(before)), 1)


# --- CSV exports ---------------------------------------------------------------------------------------------


def csv_rows(kind: str, p: Period) -> tuple[list[str], list[list[Any]]]:
    if kind == "daily-sales":
        return ["date", "orders", "gross_sales_pkr"], [[r["day"], r["orders"], r["gross_sales"]] for r in daily(p)]
    if kind == "products":
        return (
            ["product", "name", "units", "revenue_pkr", "returned_units"],
            [[r["product"], r["name"], r["units"], r["revenue"], r["returned_units"]] for r in products(p, 1000)],
        )
    if kind == "categories":
        return ["category", "units", "revenue_pkr"], [[r["category"], r["units"], r["revenue"]] for r in categories(p)]
    if kind == "orders":  # personal data: reports.export_personal only
        rows = []
        for o in sales_orders(p).order_by("placed_at").prefetch_related("items"):
            a = o.shipping_address
            rows.append(
                [
                    o.number,
                    o.placed_at.astimezone(tz()).strftime("%Y-%m-%d %H:%M"),
                    o.status,
                    o.payment_method,
                    o.payment_status,
                    a.get("full_name", ""),
                    o.email,
                    o.phone,
                    a.get("city", ""),
                    a.get("province", ""),
                    sum(i.quantity for i in o.items.all()),
                    o.subtotal,
                    o.discount,
                    o.shipping_fee + o.cod_fee,
                    o.tax,
                    o.total,
                    o.coupon_code,
                ]
            )
        header = [
            "order",
            "placed_pkt",
            "status",
            "payment_method",
            "payment_status",
            "name",
            "email",
            "phone",
            "city",
            "province",
            "units",
            "subtotal_pkr",
            "discount_pkr",
            "delivery_pkr",
            "tax_pkr",
            "total_pkr",
            "coupon",
        ]
        return header, rows
    raise KeyError(kind)


PERSONAL_EXPORTS = {"orders"}
EXPORTS = {"daily-sales", "products", "categories", "orders"}


def safe_cell(value: Any) -> str:
    """Spreadsheet formula injection guard (OWASP): text that starts like a formula is prefixed with a quote."""
    text = "" if value is None else str(value)
    if text and text[0] in "=+-@\t\r" and not _is_number(text):
        return "'" + text
    return text


def _is_number(text: str) -> bool:
    try:
        Decimal(text)
    except ArithmeticError:
        return False
    except ValueError:
        return False
    return True
