"""CMS and SEO records (MTS v2.1 §6 CMS and SEO; modules M07 and M17).

Content is data; design and code stay with developers. Editable content follows one rule everywhere:
`content` is what the storefront shows, `draft` holds unpublished changes. Staff with `cms.edit` save drafts,
staff with `cms.publish` publish them (services.py). Store settings are declared in `settings_registry`.
"""

import uuid

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
    draft = models.JSONField(null=True, blank=True)
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
    draft = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.key


class PageKind(models.TextChoices):
    CONTENT = "content", "Content page"
    POLICY = "policy", "Policy page"


class Page(models.Model):
    """A content or policy page at /pages/<slug> (MTS §6 Page, PolicyPage). Per-language copy, body blocks and
    SEO fields live in `content` ({"en": {...}, "ur": {...}}); see content.validate_page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80, unique=True)
    kind = models.CharField(max_length=10, choices=PageKind.choices, default=PageKind.CONTENT)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    content = models.JSONField(default=dict)
    draft = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "slug"]
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=PageKind.values), name="page_kind_valid"),
            models.CheckConstraint(
                condition=models.Q(is_published=False) | models.Q(published_at__isnull=False),
                name="page_published_has_date",
            ),
        ]

    def __str__(self) -> str:
        return self.slug


class NavigationMenu(models.TextChoices):
    HEADER = "header", "Header"
    FOOTER_SHOP = "footer_shop", "Footer: Shop"
    FOOTER_HELP = "footer_help", "Footer: Help"


class NavigationItem(models.Model):
    """One link in a storefront menu (MTS §6 NavigationItem). `href` is always a storefront path."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    menu = models.CharField(max_length=20, choices=NavigationMenu.choices)
    label = models.JSONField(default=dict)
    href = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["menu", "position"]
        constraints = [
            models.CheckConstraint(condition=models.Q(menu__in=NavigationMenu.values), name="navigation_menu_valid")
        ]

    def __str__(self) -> str:
        return f"{self.menu}:{self.href}"


class SEORecord(models.Model):
    """Search titles and descriptions for pages that aren't CMS pages: "home", "shop", "collections" and
    "collection:<slug>" (MTS §6 SEORecord; M17). CMS pages carry their own SEO fields in their content."""

    key = models.CharField(primary_key=True, max_length=100)
    content = models.JSONField(default=dict)
    noindex = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.key


class RedirectSource(models.TextChoices):
    MANUAL = "manual", "Added by staff"
    SLUG_CHANGE = "slug_change", "Created when a URL changed"


class Redirect(models.Model):
    """A storefront redirect (M17: redirects on URL changes). Paths are locale-free: "/pages/about-us"
    serves both /en/pages/about-us and /ur/pages/about-us."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_path = models.CharField(max_length=200, unique=True)
    to_path = models.CharField(max_length=200)
    is_permanent = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=RedirectSource.choices, default=RedirectSource.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["from_path"]
        constraints = [
            models.CheckConstraint(condition=models.Q(source__in=RedirectSource.values), name="redirect_source_valid"),
            models.CheckConstraint(condition=~models.Q(from_path=models.F("to_path")), name="redirect_not_to_itself"),
        ]

    def __str__(self) -> str:
        return f"{self.from_path} -> {self.to_path}"
