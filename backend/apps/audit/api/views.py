"""/api/v1/staff/audit-log — read-only for Owners, Store Admins and Accountants (decision 0003, 1.6)."""

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm

from ..models import AuditLog


class AuditLogOut(serializers.ModelSerializer[AuditLog]):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "at",
            "actor_id",
            "actor_label",
            "action",
            "target_type",
            "target_id",
            "before",
            "after",
            "ip",
            "request_id",
        ]


class AuditLogPageOut(serializers.Serializer[Any]):
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AuditLogOut(many=True)


class _Pages(CursorPagination):
    ordering = "-at"
    page_size = 50


class AuditLogView(StaffAPIView):
    required_permission = Perm.AUDIT_VIEW

    @extend_schema(
        tags=["staff administration"],
        parameters=[
            OpenApiParameter("action", str, description="Exact action, e.g. staff.suspended"),
            OpenApiParameter("target_id", str),
            OpenApiParameter("actor_id", str),
            OpenApiParameter("cursor", str, description="From the `next` or `previous` link of a page"),
        ],
        responses={200: AuditLogPageOut},
        operation_id="staff_audit_log",
    )
    def get(self, request: Request) -> Response:
        rows = AuditLog.objects.all()
        filters: dict[str, Any] = {}
        for name in ("action", "target_id", "actor_id"):
            value = request.query_params.get(name)
            if value:
                filters[name] = value
        if filters:
            rows = rows.filter(**filters)
        pages = _Pages()
        page = pages.paginate_queryset(rows, request, view=self)
        return pages.get_paginated_response(AuditLogOut(page, many=True).data)
