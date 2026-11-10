"""Tax rules with effective dates (MTS §10 Tax, M15). Rates and whether shelf prices include tax are pending
decision P-11: with no active rule, tax is zero and nothing is invented."""

import uuid

from django.db import models
from django.db.models import Q


class TaxRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)  # e.g. "Sales tax (provincial)"
    rate = models.DecimalField(max_digits=6, decimal_places=4)  # 0.1700 = 17 %
    prices_include_tax = models.BooleanField(default=True)
    applies_to_shipping = models.BooleanField(default=False)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from"]
        constraints = [
            models.CheckConstraint(condition=Q(rate__gte=0) & Q(rate__lt=1), name="tax_rate_range"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F("effective_from")),
                name="tax_dates_ordered",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.rate}"
