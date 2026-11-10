"""Delivery zones, rates, shipments and tracking (MTS §10 Shipping). Zones, fees and thresholds are store data
that staff edit; the figures themselves are pending decision P-13, so nothing here hard-codes them."""

import uuid

from django.db import models
from django.db.models import Q


class ShippingZone(models.Model):
    """Matched by city first, then province, then the catch-all zone (`is_fallback`)."""

    code = models.SlugField(primary_key=True, max_length=40)
    name = models.CharField(max_length=80)
    cities = models.JSONField(default=list)  # ["Karachi", "Hyderabad"]
    provinces = models.JSONField(default=list)  # ["sindh"]
    is_fallback = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "code"]
        constraints = [
            models.UniqueConstraint(fields=["is_fallback"], condition=Q(is_fallback=True), name="one_fallback_zone")
        ]

    def __str__(self) -> str:
        return self.code


class ShippingMethod(models.TextChoices):
    STANDARD = "standard", "Standard"
    EXPRESS = "express", "Express"


class ShippingRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE, related_name="rates")
    method = models.CharField(max_length=12, choices=ShippingMethod.choices)
    fee = models.DecimalField(max_digits=10, decimal_places=2)
    free_over = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    days_min = models.PositiveSmallIntegerField()
    days_max = models.PositiveSmallIntegerField()
    cod_allowed = models.BooleanField(default=True)
    cod_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["zone__position", "fee"]
        constraints = [
            models.UniqueConstraint(fields=["zone", "method"], name="rate_unique_per_zone_method"),
            models.CheckConstraint(condition=Q(fee__gte=0) & Q(cod_fee__gte=0), name="rate_fees_not_negative"),
            models.CheckConstraint(condition=Q(days_max__gte=models.F("days_min")), name="rate_days_ordered"),
            models.CheckConstraint(condition=Q(method__in=ShippingMethod.values), name="rate_method_valid"),
        ]

    def __str__(self) -> str:
        return f"{self.zone_id}:{self.method}"


class ShipmentStatus(models.TextChoices):
    BOOKED = "booked", "Booked with courier"
    IN_TRANSIT = "in_transit", "In transit"
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Delivery failed"
    RETURNING = "returning", "Returning to AureVon"
    RETURNED = "returned", "Returned to AureVon"


class Shipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="shipments")
    courier = models.CharField(max_length=30)  # adapter code, or "manual" (MTS §10 manual fallback)
    tracking_number = models.CharField(max_length=60, blank=True)
    tracking_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=ShipmentStatus.choices, default=ShipmentStatus.BOOKED)
    cod_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    booked_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-booked_at"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=ShipmentStatus.values), name="shipment_status_valid"),
            models.UniqueConstraint(
                fields=["courier", "tracking_number"], condition=~Q(tracking_number=""), name="tracking_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.courier}:{self.tracking_number}"


class TrackingEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20, choices=ShipmentStatus.choices)
    description = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=80, blank=True)
    occurred_at = models.DateTimeField()
    source = models.CharField(max_length=20, default="staff")  # staff | courier webhook | courier poll
    external_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["shipment", "external_id"], condition=~Q(external_id=""), name="tracking_event_once"
            )
        ]

    def __str__(self) -> str:
        return f"{self.shipment_id}:{self.status}"
