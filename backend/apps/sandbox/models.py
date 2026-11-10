"""Sandbox-only stand-ins for external providers. These tables play the provider's side so the whole payment
path (hosted page, signed callback, status check, refund) is exercised for real. Never enabled in production."""

from django.db import models


class SandboxPayment(models.Model):
    ref = models.CharField(max_length=40, primary_key=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    return_url = models.URLField(max_length=500)
    state = models.CharField(max_length=12, default="pending")  # pending | succeeded | failed | expired
    refunded = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.ref
