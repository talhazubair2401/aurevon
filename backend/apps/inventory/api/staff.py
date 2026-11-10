"""/api/v1/staff/inventory, /suppliers, /purchase-orders (MTS §8 "Staff: inventory"; M9).

Permissions (decision 0003): `inventory.view` reads; `inventory.adjust` corrects stock and sets reorder levels;
`inventory.inspect` moves stock between quarantine, damaged and sellable; `purchase_orders.manage` looks after
suppliers and purchase orders. Every change writes a stock movement and an audit entry.
"""

from datetime import date
from typing import Any

from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import StaffAPIView
from apps.accounts.permissions import Perm
from apps.audit.services import Actor, record
from apps.catalog.models import ProductVariant
from common.exceptions import ApiProblem

from .. import services as stock
from ..models import (
    MAIN_WAREHOUSE,
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderStatus,
    StockMovement,
    Supplier,
)

TAG = ["staff inventory"]


class _InventoryView(StaffAPIView):
    def actor(self) -> Actor:
        return Actor(self.account.pk, self.account.email)

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, stock.StockError):
            exc = ApiProblem(400, "invalid-stock", str(exc))
        return super().handle_exception(exc)


def _body(request: Request) -> dict[str, Any]:
    if not isinstance(request.data, dict):
        raise ApiProblem(400, "invalid", "Send a JSON object.")
    return dict(request.data)


def _int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiProblem(400, label, "Enter a whole number.") from None


def _variant(sku: str) -> ProductVariant:
    v = ProductVariant.objects.select_related("product").filter(sku=sku.upper()).first()
    if v is None:
        raise ApiProblem(404, "not-found", "No such SKU.")
    return v


def _name(v: ProductVariant) -> str:
    t = next((t for t in v.product.translations.all() if t.locale == "en"), None)
    return t.name if t else v.product.slug


# --- Stock ---------------------------------------------------------------------------------------------------


class StockRowOut(serializers.Serializer[Any]):
    sku = serializers.CharField()
    product = serializers.CharField()
    product_slug = serializers.CharField()
    colour = serializers.CharField()
    size = serializers.CharField()
    on_hand = serializers.IntegerField()
    reserved = serializers.IntegerField()
    available = serializers.IntegerField()
    quarantine = serializers.IntegerField()
    damaged = serializers.IntegerField()
    reorder_level = serializers.IntegerField()
    low = serializers.BooleanField()
    is_active = serializers.BooleanField()


class MovementOut(serializers.Serializer[Any]):
    location = serializers.CharField()
    quantity = serializers.IntegerField()
    reason = serializers.CharField()
    reference = serializers.CharField()
    note = serializers.CharField()
    actor = serializers.CharField()
    at = serializers.DateTimeField()


class StockDetailOut(StockRowOut):
    movements = MovementOut(many=True)


def stock_rows(variants: list[ProductVariant]) -> list[dict[str, Any]]:
    items: dict[tuple[Any, str], InventoryItem] = {
        (i.variant_id, i.location_id): i for i in InventoryItem.objects.filter(variant__in=variants)
    }
    rows = []
    for v in variants:
        main = items.get((v.pk, MAIN_WAREHOUSE))
        on_hand, reserved, level = (main.on_hand, main.reserved, main.reorder_level) if main else (0, 0, 0)
        q, d = items.get((v.pk, "quarantine")), items.get((v.pk, "damaged"))
        rows.append(
            {
                "sku": v.sku,
                "product": _name(v),
                "product_slug": v.product.slug,
                "colour": v.colour.name_en,
                "size": v.size,
                "on_hand": on_hand,
                "reserved": reserved,
                "available": on_hand - reserved,
                "quarantine": q.on_hand if q else 0,
                "damaged": d.on_hand if d else 0,
                "reorder_level": level,
                "low": bool(level) and on_hand - reserved <= level,
                "is_active": v.is_active,
            }
        )
    return rows


class StockView(_InventoryView):
    required_permission = Perm.INVENTORY_VIEW

    @extend_schema(
        tags=TAG,
        operation_id="staff_stock",
        parameters=[OpenApiParameter("q", str), OpenApiParameter("low", bool), OpenApiParameter("offset", int)],
        responses={200: StockRowOut(many=True)},
    )
    def get(self, request: Request) -> Response:
        qs = ProductVariant.objects.select_related("product", "colour").prefetch_related("product__translations")
        q = (request.query_params.get("q") or "").strip()[:80]
        if q:
            qs = qs.filter(
                Q(sku__icontains=q) | Q(product__translations__name__icontains=q) | Q(product__slug__icontains=q)
            ).distinct()
        if request.query_params.get("low") in ("1", "true"):
            low_ids = [
                i.variant_id
                for i in InventoryItem.objects.filter(location_id=MAIN_WAREHOUSE, reorder_level__gt=0)
                if i.on_hand - i.reserved <= i.reorder_level
            ]
            qs = qs.filter(pk__in=low_ids)
        offset = max(_int(request.query_params.get("offset", "0") or "0", "offset"), 0)
        variants = list(qs.order_by("product__slug", "sku")[offset : offset + 100])
        return Response(stock_rows(variants))


class StockItemView(_InventoryView):
    required_permission = Perm.INVENTORY_VIEW

    @extend_schema(tags=TAG, operation_id="staff_stock_item", responses={200: StockDetailOut})
    def get(self, request: Request, sku: str) -> Response:
        v = _variant(sku)
        row = stock_rows([v])[0]
        row["movements"] = [
            {
                "location": m.item.location_id,
                "quantity": m.quantity,
                "reason": m.reason,
                "reference": m.reference,
                "note": m.note,
                "actor": m.actor_label,
                "at": m.created_at,
            }
            for m in StockMovement.objects.filter(item__variant=v).select_related("item").order_by("-created_at")[:200]
        ]
        return Response(row)


class StockAdjustView(_InventoryView):
    required_permission = Perm.INVENTORY_ADJUST

    @extend_schema(
        tags=TAG, operation_id="staff_stock_adjust", request=OpenApiTypes.OBJECT, responses={200: StockRowOut}
    )
    def post(self, request: Request, sku: str) -> Response:
        data, v = _body(request), _variant(sku)
        stock.adjust(
            v.pk,
            str(data.get("location") or MAIN_WAREHOUSE),
            _int(data.get("delta"), "delta"),
            str(data.get("reason", "")),
            str(data.get("note", "")),
            self.actor(),
            request,
        )
        return Response(stock_rows([v])[0])


class StockTransferView(_InventoryView):
    required_permission = Perm.INVENTORY_INSPECT

    @extend_schema(
        tags=TAG, operation_id="staff_stock_transfer", request=OpenApiTypes.OBJECT, responses={200: StockRowOut}
    )
    def post(self, request: Request, sku: str) -> Response:
        data, v = _body(request), _variant(sku)
        stock.transfer(
            v.pk,
            str(data.get("from", "")),
            str(data.get("to", "")),
            _int(data.get("quantity"), "quantity"),
            str(data.get("note", "")),
            self.actor(),
            request,
        )
        return Response(stock_rows([v])[0])


class StockReorderView(_InventoryView):
    required_permission = Perm.INVENTORY_ADJUST

    @extend_schema(
        tags=TAG, operation_id="staff_stock_reorder", request=OpenApiTypes.OBJECT, responses={200: StockRowOut}
    )
    def put(self, request: Request, sku: str) -> Response:
        v = _variant(sku)
        stock.set_reorder_level(v.pk, _int(_body(request).get("level"), "level"), self.actor(), request)
        return Response(stock_rows([v])[0])


# --- Suppliers -----------------------------------------------------------------------------------------------


class SupplierOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    contact_name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    notes = serializers.CharField()
    is_active = serializers.BooleanField()
    open_orders = serializers.IntegerField()


class SupplierIn(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=120)
    contact_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)


def supplier_out(s: Supplier) -> dict[str, Any]:
    return {
        "id": s.pk,
        "name": s.name,
        "contact_name": s.contact_name,
        "email": s.email,
        "phone": s.phone,
        "address": s.address,
        "notes": s.notes,
        "is_active": s.is_active,
        "open_orders": s.purchase_orders.filter(
            status__in=[PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTLY_RECEIVED]
        ).count(),
    }


def _save_supplier(supplier: Supplier | None, request: Request, actor: Actor) -> Supplier:
    s = SupplierIn(data=request.data)
    s.is_valid(raise_exception=True)
    data = dict(s.validated_data)
    name = data["name"].strip()
    clash = Supplier.objects.filter(name__iexact=name)
    if supplier is not None:
        clash = clash.exclude(pk=supplier.pk)
    if clash.exists():
        raise ApiProblem(400, "name", "Another supplier already has that name.")
    supplier = supplier or Supplier()
    for key, value in data.items():
        setattr(supplier, key, value.strip() if isinstance(value, str) else value)
    supplier.save()
    record(
        "supplier.save",
        actor,
        target_type="supplier",
        target_id=supplier.pk,
        after={"name": supplier.name},
        request=request,
    )
    return supplier


class SuppliersView(_InventoryView):
    required_permission = {"GET": Perm.INVENTORY_VIEW, "POST": Perm.PURCHASE_ORDERS_MANAGE}

    @extend_schema(tags=TAG, operation_id="staff_suppliers", responses={200: SupplierOut(many=True)})
    def get(self, request: Request) -> Response:
        return Response([supplier_out(s) for s in Supplier.objects.all()])

    @extend_schema(tags=TAG, operation_id="staff_supplier_create", request=SupplierIn, responses={201: SupplierOut})
    def post(self, request: Request) -> Response:
        return Response(supplier_out(_save_supplier(None, request, self.actor())), status=201)


class SupplierView(_InventoryView):
    required_permission = Perm.PURCHASE_ORDERS_MANAGE

    @extend_schema(tags=TAG, operation_id="staff_supplier_update", request=SupplierIn, responses={200: SupplierOut})
    def put(self, request: Request, supplier_id: str) -> Response:
        supplier = Supplier.objects.filter(pk=supplier_id).first()
        if supplier is None:
            raise ApiProblem(404, "not-found", "No such supplier.")
        return Response(supplier_out(_save_supplier(supplier, request, self.actor())))


# --- Purchase orders -----------------------------------------------------------------------------------------


class PoLineOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    product = serializers.CharField()
    quantity_ordered = serializers.IntegerField()
    quantity_received = serializers.IntegerField()
    unit_cost = serializers.CharField()


class PoOut(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    number = serializers.CharField()
    supplier = SupplierOut()
    status = serializers.CharField()
    expected_on = serializers.DateField(allow_null=True)
    note = serializers.CharField()
    created_by = serializers.CharField()
    created_at = serializers.DateTimeField()
    sent_at = serializers.DateTimeField(allow_null=True)
    lines = PoLineOut(many=True)
    total_cost = serializers.CharField()
    units_ordered = serializers.IntegerField()
    units_received = serializers.IntegerField()


def po_out(po: PurchaseOrder) -> dict[str, Any]:
    lines = list(po.lines.select_related("variant__product").prefetch_related("variant__product__translations"))
    return {
        "id": po.pk,
        "number": po.number,
        "supplier": supplier_out(po.supplier),
        "status": po.status,
        "expected_on": po.expected_on,
        "note": po.note,
        "created_by": po.created_by,
        "created_at": po.created_at,
        "sent_at": po.sent_at,
        "lines": [
            {
                "id": line.pk,
                "sku": line.variant.sku,
                "product": _name(line.variant),
                "quantity_ordered": line.quantity_ordered,
                "quantity_received": line.quantity_received,
                "unit_cost": f"{line.unit_cost:.2f}",
            }
            for line in lines
        ],
        "total_cost": f"{sum(line.unit_cost * line.quantity_ordered for line in lines):.2f}",
        "units_ordered": sum(line.quantity_ordered for line in lines),
        "units_received": sum(line.quantity_received for line in lines),
    }


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ApiProblem(400, "expected_on", "Use a date such as 2026-12-01.") from None


def _po(po_id: str) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_related("supplier").filter(pk=po_id).first()
    if po is None:
        raise ApiProblem(404, "not-found", "No such purchase order.")
    return po


class PurchaseOrdersView(_InventoryView):
    required_permission = {"GET": Perm.INVENTORY_VIEW, "POST": Perm.PURCHASE_ORDERS_MANAGE}

    @extend_schema(
        tags=TAG,
        operation_id="staff_purchase_orders",
        parameters=[OpenApiParameter("status", str)],
        responses={200: PoOut(many=True)},
    )
    def get(self, request: Request) -> Response:
        qs = PurchaseOrder.objects.select_related("supplier")
        status = request.query_params.get("status")
        if status in PurchaseOrderStatus.values:
            qs = qs.filter(status=status)
        return Response([po_out(po) for po in qs[:200]])

    @extend_schema(
        tags=TAG, operation_id="staff_purchase_order_create", request=OpenApiTypes.OBJECT, responses={201: PoOut}
    )
    def post(self, request: Request) -> Response:
        data = _body(request)
        po = stock.create_purchase_order(
            data.get("supplier"),
            data.get("lines"),
            _date(data.get("expected_on")),
            str(data.get("note", "")),
            self.actor(),
            request,
        )
        return Response(po_out(po), status=201)


class PurchaseOrderView(_InventoryView):
    required_permission = {"GET": Perm.INVENTORY_VIEW, "PUT": Perm.PURCHASE_ORDERS_MANAGE}

    @extend_schema(tags=TAG, operation_id="staff_purchase_order", responses={200: PoOut})
    def get(self, request: Request, po_id: str) -> Response:
        return Response(po_out(_po(po_id)))

    @extend_schema(
        tags=TAG, operation_id="staff_purchase_order_update", request=OpenApiTypes.OBJECT, responses={200: PoOut}
    )
    def put(self, request: Request, po_id: str) -> Response:
        data = _body(request)
        po = stock.update_purchase_order(
            _po(po_id),
            data.get("lines"),
            _date(data.get("expected_on")),
            str(data.get("note", "")),
            self.actor(),
            request,
        )
        return Response(po_out(po))


class PurchaseOrderActionView(_InventoryView):
    required_permission = Perm.PURCHASE_ORDERS_MANAGE

    @extend_schema(
        tags=TAG, operation_id="staff_purchase_order_action", request=OpenApiTypes.OBJECT, responses={200: PoOut}
    )
    def post(self, request: Request, po_id: str, action: str) -> Response:
        po = _po(po_id)
        if action == "send":
            po = stock.send_purchase_order(po, self.actor(), request)
        elif action == "cancel":
            po = stock.cancel_purchase_order(po, self.actor(), request)
        elif action == "receive":
            po = stock.receive_purchase_order(po, _body(request).get("lines"), self.actor(), request)
        else:
            raise ApiProblem(404, "not-found", "Unknown action.")
        return Response(po_out(_po(str(po.pk))))
