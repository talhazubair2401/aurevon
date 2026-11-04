"""/api/v1/staff/settings — store settings. Security settings: Owner only, with re-confirmation."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.accounts.services import access
from apps.audit.services import Actor
from common.exceptions import ApiProblem

from .. import services
from ..settings_registry import SETTINGS


class SettingOut(serializers.Serializer[Any]):
    key = serializers.CharField()
    group = serializers.CharField()
    description = serializers.CharField()
    value = serializers.JSONField(allow_null=True)
    editable = serializers.BooleanField()


class SettingIn(serializers.Serializer[Any]):
    value = serializers.JSONField(allow_null=True)


GROUP_PERMISSION = {"store": Perm.SETTINGS_STORE, "security": Perm.SETTINGS_SECURITY}


class SettingsView(StaffAPIView):
    required_permission = Perm.SETTINGS_STORE

    @extend_schema(
        tags=["staff administration"], responses={200: SettingOut(many=True)}, operation_id="staff_settings_list"
    )
    def get(self, request: Request) -> Response:
        values = services.all_values()
        return Response(
            [
                {
                    "key": key,
                    "group": spec.group,
                    "description": spec.label,
                    "value": values[key],
                    "editable": access.has_perm(self.account, GROUP_PERMISSION[spec.group]),
                }
                for key, spec in SETTINGS.items()
            ]
        )


class SettingView(StaffAPIView):
    required_permission = Perm.SETTINGS_STORE

    @extend_schema(
        tags=["staff administration"], request=SettingIn, responses={200: SettingOut}, operation_id="staff_settings_set"
    )
    def put(self, request: Request, key: str) -> Response:
        spec = SETTINGS.get(key)
        if spec is None:
            raise ApiProblem(404, "not-found", "No such setting.")
        if not access.has_perm(self.account, GROUP_PERMISSION[spec.group]):
            raise ApiProblem(403, "permission-denied", "Your role doesn't allow changing this setting.")
        if spec.group == "security" and not access.stepped_up(self.session):
            raise ApiProblem(403, "step-up-required", "Confirm with your authenticator code to continue.")
        serializer = SettingIn(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            value = services.set_value(
                key, serializer.validated_data["value"], Actor(self.account.pk, self.account.email), request
            )
        except ValueError as exc:
            raise ApiProblem(400, "invalid-value", str(exc)) from exc
        return Response({"key": key, "group": spec.group, "description": spec.label, "value": value, "editable": True})
