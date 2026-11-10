"""/api/v1/staff/shipping-zones, /shipping-rates, /tax-rules (MTS §10; M10).

Permissions (decision 0003): `settings.store` reads and changes delivery zones, rates and tax rules. Tax rules change
what customers pay, so saving one asks for the authenticator code again (decision 0003, 2.5, "prices"). Zones and
rates are what checkout quotes from (`shipping.services.options`); orders keep a copy of the zone code and fee, so
changing or deleting a zone never rewrites past orders. No tax rule is seeded: P-11 is still open, so tax stays zero
until the Owner enters the rule their accountant confirms.
"""

import json
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.audit.services import Actor, record
from apps.customers.models import PROVINCE_CODES
from apps.localization.models import TaxRule
from apps.localization.services import rule_in_force
from common.exceptions import ApiProblem

from ..models import ShippingMethod, ShippingRate, ShippingZone

TAG = ["staff shipping and tax"]


class _SettingsView(StaffAPIView):
    required_permission = Perm.SETTINGS_STORE

    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)


def _valid(serializer: serializers.Serializer[Any]) -> dict[str, Any]:
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


# --- Zones ---------------------------------------------------------------------------------------------------


class RateOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    zone = serializers.CharField()
    method = serializers.CharField()
    fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    free_over = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    days_min = serializers.IntegerField()
    days_max = serializers.IntegerField()
    cod_allowed = serializers.BooleanField()
    cod_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_active = serializers.BooleanField()


class ZoneOut(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()
    cities = serializers.ListField(child=serializers.CharField())
    provinces = serializers.ListField(child=serializers.CharField())
    is_fallback = serializers.BooleanField()
    position = serializers.IntegerField()
    rates = RateOut(many=True)


class ZoneIn(serializers.Serializer[Any]):
    code = serializers.SlugField(max_length=40)
    name = serializers.CharField(max_length=80)
    cities = serializers.ListField(child=serializers.CharField(max_length=60), required=False, default=list)
    provinces = serializers.ListField(
        child=serializers.ChoiceField(choices=PROVINCE_CODES), required=False, default=list
    )
    is_fallback = serializers.BooleanField(required=False, default=False)
    position = serializers.IntegerField(min_value=0, max_value=10000, required=False, default=0)


def rate_out(r: ShippingRate) -> dict[str, Any]:
    return dict(
        RateOut(
            {
                "id": r.pk,
                "zone": r.zone_id,
                "method": r.method,
                "fee": r.fee,
                "free_over": r.free_over,
                "days_min": r.days_min,
                "days_max": r.days_max,
                "cod_allowed": r.cod_allowed,
                "cod_fee": r.cod_fee,
                "is_active": r.is_active,
            }
        ).data
    )


def zone_out(z: ShippingZone) -> dict[str, Any]:
    return dict(
        ZoneOut(
            {
                "code": z.code,
                "name": z.name,
                "cities": z.cities,
                "provinces": z.provinces,
                "is_fallback": z.is_fallback,
                "position": z.position,
                "rates": [rate_out(r) for r in z.rates.all().order_by("fee")],
            }
        ).data
    )


def _save_zone(zone: ShippingZone | None, request: Request, actor: Actor) -> ShippingZone:
    data = _valid(ZoneIn(data=request.data))
    if zone is None and ShippingZone.objects.filter(pk=data["code"]).exists():
        raise ApiProblem(400, "code", "A zone with that code already exists.")
    cities = sorted({c.strip().title() for c in data["cities"] if c.strip()})
    taken: dict[str, str] = {}
    for other in ShippingZone.objects.exclude(pk=zone.pk if zone else data["code"]):
        for c in other.cities:
            taken[c.lower()] = other.name
    clash = [c for c in cities if c.lower() in taken]
    if clash:
        raise ApiProblem(400, "cities", f"{clash[0]} is already in the {taken[clash[0].lower()]} zone.")
    if not (cities or data["provinces"] or data["is_fallback"]):
        raise ApiProblem(400, "cities", "Add at least one city or province, or make this the catch-all zone.")
    before = zone_out(zone) if zone else None
    with transaction.atomic():
        if data["is_fallback"]:
            ShippingZone.objects.exclude(code=zone.pk if zone else data["code"]).update(is_fallback=False)
        zone = zone or ShippingZone(code=data["code"])
        zone.name = data["name"].strip()
        zone.cities = cities
        zone.provinces = sorted(set(data["provinces"]))
        zone.is_fallback = data["is_fallback"]
        zone.position = data["position"]
        zone.save()
    after = zone_out(zone)
    after.pop("rates")
    if before:
        before.pop("rates")
    record(
        "shipping.zone_save",
        actor,
        target_type="shipping_zone",
        target_id=zone.pk,
        before=before,
        after=after,
        request=request,
    )
    return zone


class ZonesView(_SettingsView):
    @extend_schema(tags=TAG, operation_id="staff_shipping_zones", responses={200: ZoneOut(many=True)})
    def get(self, request: Request) -> Response:
        return Response([zone_out(z) for z in ShippingZone.objects.prefetch_related("rates")])

    @extend_schema(tags=TAG, operation_id="staff_shipping_zone_create", request=ZoneIn, responses={201: ZoneOut})
    def post(self, request: Request) -> Response:
        return Response(zone_out(_save_zone(None, request, self.actor())), status=201)


class ZoneView(_SettingsView):
    def _zone(self, code: str) -> ShippingZone:
        zone = ShippingZone.objects.filter(pk=code).first()
        if zone is None:
            raise ApiProblem(404, "not-found", "No such delivery zone.")
        return zone

    @extend_schema(tags=TAG, operation_id="staff_shipping_zone_update", request=ZoneIn, responses={200: ZoneOut})
    def put(self, request: Request, code: str) -> Response:
        zone = self._zone(code)
        if request.data.get("code", code) != code:
            raise ApiProblem(400, "code", "A zone's code can't be changed.")
        return Response(zone_out(_save_zone(zone, request, self.actor())))

    @extend_schema(tags=TAG, operation_id="staff_shipping_zone_delete", responses={204: None})
    def delete(self, request: Request, code: str) -> Response:
        zone = self._zone(code)
        before = _json(zone_out(zone))
        zone.delete()
        record(
            "shipping.zone_delete",
            self.actor(),
            target_type="shipping_zone",
            target_id=code,
            before=before,
            request=request,
        )
        return Response(status=204)


# --- Rates ---------------------------------------------------------------------------------------------------


class RateIn(serializers.Serializer[Any]):
    zone = serializers.CharField(max_length=40)
    method = serializers.ChoiceField(choices=ShippingMethod.values)
    fee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    free_over = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )
    days_min = serializers.IntegerField(min_value=0, max_value=60)
    days_max = serializers.IntegerField(min_value=0, max_value=60)
    cod_allowed = serializers.BooleanField(required=False, default=True)
    cod_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0")
    )
    is_active = serializers.BooleanField(required=False, default=True)


def _save_rate(rate: ShippingRate | None, request: Request, actor: Actor) -> ShippingRate:
    data = _valid(RateIn(data=request.data))
    if data["days_max"] < data["days_min"]:
        raise ApiProblem(400, "days_max", "The longest delivery time can't be shorter than the shortest.")
    zone = ShippingZone.objects.filter(pk=data.pop("zone")).first()
    if zone is None:
        raise ApiProblem(400, "zone", "No such delivery zone.")
    if not data["cod_allowed"]:
        data["cod_fee"] = Decimal("0")
    before = rate_out(rate) if rate else None
    rate = rate or ShippingRate()
    rate.zone = zone
    for key, value in data.items():
        setattr(rate, key, value)
    try:
        with transaction.atomic():
            rate.save()
    except IntegrityError:
        raise ApiProblem(400, "method", "That zone already has a rate for this delivery method.") from None
    record(
        "shipping.rate_save",
        actor,
        target_type="shipping_rate",
        target_id=rate.pk,
        before=_plain(before),
        after=_plain(rate_out(rate)),
        request=request,
    )
    return rate


def _plain(value: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if value is None else {k: str(v) if v is not None else None for k, v in value.items()}


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


class RatesView(_SettingsView):
    @extend_schema(tags=TAG, operation_id="staff_shipping_rate_create", request=RateIn, responses={201: RateOut})
    def post(self, request: Request) -> Response:
        return Response(rate_out(_save_rate(None, request, self.actor())), status=201)


class RateView(_SettingsView):
    def _rate(self, rate_id: str) -> ShippingRate:
        rate = ShippingRate.objects.filter(pk=rate_id).first()
        if rate is None:
            raise ApiProblem(404, "not-found", "No such delivery rate.")
        return rate

    @extend_schema(tags=TAG, operation_id="staff_shipping_rate_update", request=RateIn, responses={200: RateOut})
    def put(self, request: Request, rate_id: str) -> Response:
        return Response(rate_out(_save_rate(self._rate(rate_id), request, self.actor())))

    @extend_schema(tags=TAG, operation_id="staff_shipping_rate_delete", responses={204: None})
    def delete(self, request: Request, rate_id: str) -> Response:
        rate = self._rate(rate_id)
        before = _plain(rate_out(rate))
        rate.delete()
        record(
            "shipping.rate_delete",
            self.actor(),
            target_type="shipping_rate",
            target_id=rate_id,
            before=before,
            request=request,
        )
        return Response(status=204)


# --- Tax rules -----------------------------------------------------------------------------------------------


class TaxRuleOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    rate_percent = serializers.DecimalField(max_digits=6, decimal_places=2)
    prices_include_tax = serializers.BooleanField()
    applies_to_shipping = serializers.BooleanField()
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(allow_null=True)
    in_force = serializers.BooleanField()


class TaxRulesOut(serializers.Serializer[Any]):
    rules = TaxRuleOut(many=True)
    in_force = serializers.UUIDField(allow_null=True)


class TaxRuleIn(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=80)
    rate_percent = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("50")
    )
    prices_include_tax = serializers.BooleanField(required=False, default=True)
    applies_to_shipping = serializers.BooleanField(required=False, default=False)
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)


def tax_out(t: TaxRule, current: TaxRule | None) -> dict[str, Any]:
    return dict(
        TaxRuleOut(
            {
                "id": t.pk,
                "name": t.name,
                "rate_percent": str((Decimal(t.rate) * 100).quantize(Decimal("0.01"))),
                "prices_include_tax": t.prices_include_tax,
                "applies_to_shipping": t.applies_to_shipping,
                "effective_from": t.effective_from,
                "effective_to": t.effective_to,
                "in_force": current is not None and current.pk == t.pk,
            }
        ).data
    )


def _tax_list() -> dict[str, Any]:
    current = rule_in_force()
    return {
        "rules": [tax_out(t, current) for t in TaxRule.objects.all()],
        "in_force": current.pk if current else None,
    }


def _overlaps(start: date, end: date | None, exclude: Any = None) -> TaxRule | None:
    far = date(9999, 12, 31)
    for t in TaxRule.objects.exclude(pk=exclude):
        if start <= (t.effective_to or far) and t.effective_from <= (end or far):
            return t
    return None


class TaxRulesView(_SettingsView):
    step_up = frozenset({"POST"})

    @extend_schema(tags=TAG, operation_id="staff_tax_rules", responses={200: TaxRulesOut})
    def get(self, request: Request) -> Response:
        return Response(_tax_list())

    @extend_schema(tags=TAG, operation_id="staff_tax_rule_create", request=TaxRuleIn, responses={201: TaxRulesOut})
    def post(self, request: Request) -> Response:
        data = _valid(TaxRuleIn(data=request.data))
        end = data.get("effective_to")
        if end is not None and end < data["effective_from"]:
            raise ApiProblem(400, "effective_to", "The end date can't be before the start date.")
        clash = _overlaps(data["effective_from"], end)
        if clash is not None:
            raise ApiProblem(
                400, "effective_from", f"These dates overlap “{clash.name}”. End that rule first, then add this one."
            )
        rule = TaxRule.objects.create(
            name=data["name"].strip(),
            rate=(data["rate_percent"] / 100).quantize(Decimal("0.0001")),
            prices_include_tax=data["prices_include_tax"],
            applies_to_shipping=data["applies_to_shipping"],
            effective_from=data["effective_from"],
            effective_to=end,
        )
        record(
            "tax.rule_create",
            self.actor(),
            target_type="tax_rule",
            target_id=rule.pk,
            after={k: str(v) for k, v in data.items()},
            request=request,
        )
        return Response(_tax_list(), status=201)


class TaxRuleEndIn(serializers.Serializer[Any]):
    effective_to = serializers.DateField()


class TaxRuleEndView(_SettingsView):
    """Rules are never edited or deleted (orders were taxed with them); a rule is ended on a date instead."""

    step_up = True

    @extend_schema(tags=TAG, operation_id="staff_tax_rule_end", request=TaxRuleEndIn, responses={200: TaxRulesOut})
    def post(self, request: Request, rule_id: str) -> Response:
        rule = TaxRule.objects.filter(pk=rule_id).first()
        if rule is None:
            raise ApiProblem(404, "not-found", "No such tax rule.")
        end = _valid(TaxRuleEndIn(data=request.data))["effective_to"]
        if end < rule.effective_from:
            raise ApiProblem(400, "effective_to", "The end date can't be before the rule starts.")
        if rule.effective_to is not None and end > rule.effective_to:
            raise ApiProblem(400, "effective_to", "A rule can only be ended earlier, not extended.")
        before = str(rule.effective_to)
        rule.effective_to = end
        rule.save(update_fields=["effective_to"])
        record(
            "tax.rule_end",
            self.actor(),
            target_type="tax_rule",
            target_id=rule.pk,
            before={"effective_to": before},
            after={"effective_to": str(end)},
            request=request,
        )
        return Response(_tax_list())
