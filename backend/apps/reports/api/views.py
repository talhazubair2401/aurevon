"""/api/v1/staff/reports (MTS §8 "Staff: reports"; M13).

`reports.aggregate` (Owner, Store Admin, Accountant) sees totals and downloads aggregate CSVs (no personal data).
`reports.export_personal` (Owner, Accountant) can also download the order list with customer details; every such
download is audited (decision 0003). Dates are Pakistan days; ranges are at most 400 days.
"""

import csv
import io
from datetime import date
from typing import Any

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor, record
from common.exceptions import ApiProblem

from .. import services as reports

TAG = ["staff reports"]
RANGE = [
    OpenApiParameter("from", OpenApiTypes.DATE, description="First day (Pakistan time); default 29 days before `to`"),
    OpenApiParameter("to", OpenApiTypes.DATE, description="Last day (Pakistan time); default today"),
]


def money() -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=14, decimal_places=2)


def _period(request: Request) -> reports.Period:
    def day(key: str) -> date | None:
        raw = request.query_params.get(key, "")
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise ApiProblem(400, key, "Use a date like 2026-11-30.") from None

    return reports.period(day("from"), day("to"))


class SummaryOut(serializers.Serializer[Any]):
    orders = serializers.IntegerField()
    units = serializers.IntegerField()
    gross_sales = money()
    discounts = money()
    shipping = money()
    cod_fees = money()
    tax = money()
    refunds = money()
    net_sales = money()
    average_order = money()
    cancelled = serializers.IntegerField()
    awaiting_payment = serializers.IntegerField()
    card_sales = money()
    cod_sales = money()
    cod_outstanding = money()


class ChangeOut(serializers.Serializer[Any]):
    orders = serializers.FloatField(allow_null=True)
    gross_sales = serializers.FloatField(allow_null=True)
    net_sales = serializers.FloatField(allow_null=True)
    average_order = serializers.FloatField(allow_null=True)


class DayOut(serializers.Serializer[Any]):
    day = serializers.DateField()
    orders = serializers.IntegerField()
    gross_sales = money()


class ProductRowOut(serializers.Serializer[Any]):
    product = serializers.CharField()
    name = serializers.CharField()
    units = serializers.IntegerField()
    revenue = money()
    returned_units = serializers.IntegerField()


class CategoryRowOut(serializers.Serializer[Any]):
    category = serializers.CharField(allow_null=True)
    units = serializers.IntegerField()
    revenue = money()


class CityRowOut(serializers.Serializer[Any]):
    city = serializers.CharField()
    orders = serializers.IntegerField()
    gross_sales = money()


class CustomersOut(serializers.Serializer[Any]):
    new_accounts = serializers.IntegerField()
    guest_orders = serializers.IntegerField()
    account_orders = serializers.IntegerField()
    buying_accounts = serializers.IntegerField()
    returning_accounts = serializers.IntegerField()


class ReasonCountOut(serializers.Serializer[Any]):
    reason = serializers.CharField()
    count = serializers.IntegerField()


class ReturnsReportOut(serializers.Serializer[Any]):
    requests = serializers.IntegerField()
    refunds = serializers.IntegerField()
    exchanges = serializers.IntegerField()
    units_returned = serializers.IntegerField()
    return_rate_percent = serializers.FloatField()
    by_reason = ReasonCountOut(many=True)


class CouponRowOut(serializers.Serializer[Any]):
    code = serializers.CharField()
    uses = serializers.IntegerField()
    discount = money()
    orders_value = money()


class InventoryReportOut(serializers.Serializer[Any]):
    sellable_units = serializers.IntegerField()
    reserved_units = serializers.IntegerField()
    retail_value = money()
    out_of_stock = serializers.IntegerField()
    low_stock = serializers.IntegerField()
    quarantine_units = serializers.IntegerField()
    damaged_units = serializers.IntegerField()


class DashboardOut(serializers.Serializer[Any]):
    start = serializers.DateField()
    end = serializers.DateField()
    previous_start = serializers.DateField()
    previous_end = serializers.DateField()
    summary = SummaryOut()
    change = ChangeOut()
    daily = DayOut(many=True)
    products = ProductRowOut(many=True)
    categories = CategoryRowOut(many=True)
    cities = CityRowOut(many=True)
    customers = CustomersOut()
    returns = ReturnsReportOut()
    coupons = CouponRowOut(many=True)
    inventory = InventoryReportOut()
    exports = serializers.ListField(child=serializers.CharField())
    definitions = serializers.CharField()


class DashboardView(StaffAPIView):
    required_permission = Perm.REPORTS_AGGREGATE

    @extend_schema(tags=TAG, parameters=RANGE, responses={200: DashboardOut}, operation_id="staff_reports_dashboard")
    def get(self, request: Request) -> Response:
        p = _period(request)
        now, before = reports.summary(p), reports.summary(p.previous())
        exports = sorted(reports.EXPORTS - reports.PERSONAL_EXPORTS)
        if access.has_perm(self.account, Perm.REPORTS_EXPORT_PERSONAL):
            exports = sorted(reports.EXPORTS)
        data = {
            "start": p.start,
            "end": p.end,
            "previous_start": p.previous().start,
            "previous_end": p.previous().end,
            "summary": now,
            "change": {
                k: reports.change(now[k], before[k]) for k in ("orders", "gross_sales", "net_sales", "average_order")
            },
            "daily": reports.daily(p),
            "products": reports.products(p),
            "categories": reports.categories(p),
            "cities": reports.cities(p),
            "customers": reports.customers(p),
            "returns": reports.returns(p),
            "coupons": reports.coupons(p),
            "inventory": reports.inventory(),
            "exports": exports,
            "definitions": reports.DEFINITIONS,
        }
        return Response(DashboardOut(data).data)


class ExportView(StaffAPIView):
    """CSV download. Aggregate reports need `reports.aggregate`; the order list needs `reports.export_personal`."""

    required_permission = Perm.REPORTS_AGGREGATE

    @extend_schema(
        tags=TAG,
        parameters=RANGE,
        responses={(200, "text/csv"): OpenApiResponse(OpenApiTypes.STR, description="CSV file")},
        operation_id="staff_reports_export",
    )
    def get(self, request: Request, kind: str) -> HttpResponse:
        if kind not in reports.EXPORTS:
            raise ApiProblem(404, "not-found", "No such report.")
        personal = kind in reports.PERSONAL_EXPORTS
        if personal and not access.has_perm(self.account, Perm.REPORTS_EXPORT_PERSONAL):
            raise ApiProblem(403, "permission-denied", "Your role can't download customer details.")
        p = _period(request)
        header, rows = reports.csv_rows(kind, p)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        for row in rows:
            writer.writerow([reports.safe_cell(v) for v in row])
        if personal:
            record(
                "report.export_personal",
                Actor(self.account.pk, self.account.email),
                target_type="report",
                target_id=kind,
                after={"from": str(p.start), "to": str(p.end), "rows": len(rows)},
                request=request,
            )
        response = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="aurevon-{kind}-{p.start}-to-{p.end}.csv"'
        response["Cache-Control"] = "no-store"
        return response
