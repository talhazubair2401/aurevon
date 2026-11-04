"""Store settings (MTS §6 CMS and SEO: StoreSetting). Each key is declared in `settings_registry`."""

from django.db import models


class StoreSetting(models.Model):
    key = models.CharField(primary_key=True, max_length=80)
    value = models.JSONField(null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by_id = models.UUIDField(null=True, blank=True)

    def __str__(self) -> str:
        return self.key
