"""Audit log of sensitive actions (MTS §6, §9). Append-only: the database refuses updates and deletes."""

import uuid

from django.db import models


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    # The actor is copied, not linked: the log must survive any later change to accounts.
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_label = models.CharField(max_length=254)
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=64, blank=True, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-at"]
        indexes = [models.Index(fields=["target_type", "target_id", "-at"])]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.actor_label} {self.action}"
