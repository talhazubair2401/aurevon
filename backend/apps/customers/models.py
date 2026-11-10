"""Customer profile, addresses and wishlist (MTS §6 Identity). Always owned by a customer Account; staff
accounts never have any of these (A-22)."""

import uuid

from django.db import models
from django.db.models import Q

# Pakistan provinces and territories (M15 localization: Pakistan address format at launch).
PROVINCES = [
    ("punjab", "Punjab"),
    ("sindh", "Sindh"),
    ("kp", "Khyber Pakhtunkhwa"),
    ("balochistan", "Balochistan"),
    ("ict", "Islamabad Capital Territory"),
    ("gb", "Gilgit-Baltistan"),
    ("ajk", "Azad Jammu and Kashmir"),
]
PROVINCE_CODES = [code for code, _ in PROVINCES]


class CustomerProfile(models.Model):
    account = models.OneToOneField(
        "accounts.Account", primary_key=True, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=20, blank=True)  # E.164, e.g. +923001234567
    preferred_locale = models.CharField(max_length=5, default="en")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.account_id)


class Address(models.Model):
    """A Pakistani delivery address. Orders copy it (snapshot), so editing or deleting never changes past orders."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=40, blank=True)  # "Home", "Office"
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    area = models.CharField(max_length=100, blank=True)  # area, sector or block
    city = models.CharField(max_length=80)
    province = models.CharField(max_length=12)
    postal_code = models.CharField(max_length=5, blank=True)
    country = models.CharField(max_length=2, default="PK")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(province__in=PROVINCE_CODES), name="address_province_valid"),
            models.UniqueConstraint(
                fields=["account"], condition=Q(is_default=True), name="address_one_default_per_account"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name}, {self.city}"


class WishlistItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["account", "product"], name="wishlist_unique")]

    def __str__(self) -> str:
        return f"{self.account_id}:{self.product_id}"
