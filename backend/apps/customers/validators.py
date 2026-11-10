"""Pakistan formats (M15 at launch): mobile numbers and postal codes. Shared by addresses and guest checkout."""

import re

from rest_framework import serializers

from .models import PROVINCE_CODES

_PHONE = re.compile(r"^(?:\+92|0092|92|0)?(3\d{9}|[1-9]\d{8,9})$")


def normalize_phone(value: str) -> str:
    """Accepts 0300 1234567, +92 300 1234567, 923001234567 … and returns +923001234567."""
    digits = re.sub(r"[\s\-()]", "", value or "")
    match = _PHONE.match(digits)
    if not match:
        raise serializers.ValidationError("Enter a Pakistani phone number, for example 0300 1234567.")
    return "+92" + match.group(1)


class AddressSerializer(serializers.Serializer):  # type: ignore[type-arg]
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30)
    line1 = serializers.CharField(max_length=200)
    line2 = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=80)
    province = serializers.ChoiceField(choices=PROVINCE_CODES)
    postal_code = serializers.RegexField(r"^\d{5}$", required=False, allow_blank=True, default="")

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value)

    def validate_city(self, value: str) -> str:
        return value.strip().title()
