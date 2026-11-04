"""Store settings (MTS §6 CMS and SEO: StoreSetting). Each key is declared in `settings_registry`."""

from django.db import models


class StoreSetting(models.Model):
    key = models.CharField(primary_key=True, max_length=80)
    value = models.JSONField(null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by_id = models.UUIDField(null=True, blank=True)

    def __str__(self) -> str:
        return self.key


class HomepageSectionKey(models.TextChoices):
    HERO = "hero", "Hero"
    COLLECTIONS = "collections", "Collections"
    FEATURED_PRODUCTS = "featured_products", "Featured products"
    NEW_ARRIVALS = "new_arrivals", "New arrivals"
    BRAND_STORY = "brand_story", "Brand story"


class HomepageSection(models.Model):
    """One homepage section (MTS §6 HomepageSection; M07). Copy lives per language in `content`
    ({"en": {...}, "ur": {...}}), the genuinely variable part; order and visibility are columns."""

    key = models.CharField(primary_key=True, max_length=30, choices=HomepageSectionKey.choices)
    position = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    content = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(key__in=HomepageSectionKey.values), name="homepage_section_key_valid"
            )
        ]

    def __str__(self) -> str:
        return self.key


class Banner(models.Model):
    """A named editorial banner placed by the storefront, e.g. "shop_editorial" on Shop All (MTS §6 Banner)."""

    key = models.SlugField(primary_key=True, max_length=60)
    is_enabled = models.BooleanField(default=True)
    content = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.key
