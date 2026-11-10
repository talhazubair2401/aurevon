"""/api/v1/me, /me/addresses, /me/wishlist, /me/password: the signed-in customer's own data (MTS §8)."""

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.api.base import CustomerAPIView
from apps.accounts.models import AccountType
from apps.accounts.services import passwords, sessions
from apps.catalog import selectors as catalog_selectors
from apps.catalog.api.views import ProductCardSerializer
from apps.catalog.models import ProductStatus
from apps.catalog.presenters import product_card
from apps.notifications import services as consent
from apps.notifications.models import ConsentPurpose
from common.api import LOCALES, request_locale
from common.exceptions import ApiProblem

from .. import services
from ..models import Address, WishlistItem
from ..validators import AddressSerializer, normalize_phone

TAG = ["customer account"]


class ProfileOut(serializers.Serializer[Any]):
    email = serializers.EmailField()
    full_name = serializers.CharField()
    email_verified = serializers.BooleanField()
    phone = serializers.CharField(allow_blank=True)
    preferred_locale = serializers.ChoiceField(choices=LOCALES)


class ProfileIn(serializers.Serializer[Any]):
    full_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    preferred_locale = serializers.ChoiceField(choices=LOCALES, required=False)

    def validate_phone(self, value: str) -> str:
        return normalize_phone(value) if value else ""


class AddressOut(AddressSerializer):
    id = serializers.UUIDField()
    label = serializers.CharField(allow_blank=True)  # type: ignore[assignment]
    is_default = serializers.BooleanField()


class AddressIn(AddressSerializer):
    label = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")  # type: ignore[assignment]
    make_default = serializers.BooleanField(required=False, default=False)


class PasswordChangeIn(serializers.Serializer[Any]):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False)
    new_password = serializers.CharField(max_length=256, trim_whitespace=False)


class WishlistIn(serializers.Serializer[Any]):
    slug = serializers.SlugField(max_length=120)


def _valid(cls: type[serializers.Serializer[Any]], request: Request, partial: bool = False) -> dict[str, Any]:
    s = cls(data=request.data, partial=partial)
    s.is_valid(raise_exception=True)
    return dict(s.validated_data)


def _profile(view: CustomerAPIView) -> dict[str, Any]:
    p = services.profile(view.account)
    a = view.account
    return {
        "email": a.email,
        "full_name": a.full_name,
        "email_verified": a.email_verified_at is not None,
        "phone": p.phone,
        "preferred_locale": p.preferred_locale,
    }


def _address(a: Address) -> dict[str, Any]:
    fields = ("id", "label", "full_name", "phone", "line1", "line2", "area", "city", "province", "postal_code")
    return {**{f: getattr(a, f) for f in fields}, "is_default": a.is_default}


class MeView(CustomerAPIView):
    @extend_schema(tags=TAG, responses={200: ProfileOut}, operation_id="me_get")
    def get(self, request: Request) -> Response:
        return Response(_profile(self))

    @extend_schema(tags=TAG, request=ProfileIn, responses={200: ProfileOut}, operation_id="me_update")
    def patch(self, request: Request) -> Response:
        services.update_profile(self.account, _valid(ProfileIn, request, partial=True))
        return Response(_profile(self))


class PasswordView(CustomerAPIView):
    @extend_schema(tags=TAG, request=PasswordChangeIn, responses={204: None}, operation_id="me_password_change")
    def post(self, request: Request) -> Response:
        data = _valid(PasswordChangeIn, request)
        account = self.account
        if account.account_type != AccountType.CUSTOMER or not account.check_password(data["current_password"]):
            raise ApiProblem(400, "wrong-password", "Your current password is incorrect.")
        errors = passwords.validate(data["new_password"], AccountType.CUSTOMER, account)
        if errors:
            raise ApiProblem(400, "weak-password", " ".join(errors))
        passwords.set_password(account, data["new_password"])
        for other in sessions.live_sessions(sessions.CUSTOMER, account):
            if other.pk != self.session.pk:
                sessions.revoke(sessions.CUSTOMER, other, sessions.RevokeReason.PASSWORD_CHANGED)
        return Response(status=204)


class AddressesView(CustomerAPIView):
    @extend_schema(tags=TAG, responses={200: AddressOut(many=True)}, operation_id="me_addresses")
    def get(self, request: Request) -> Response:
        return Response([_address(a) for a in Address.objects.filter(account=self.account)])

    @extend_schema(tags=TAG, request=AddressIn, responses={201: AddressOut}, operation_id="me_address_create")
    def post(self, request: Request) -> Response:
        data = _valid(AddressIn, request)
        make_default = data.pop("make_default")
        return Response(_address(services.add_address(self.account, data, make_default=make_default)), status=201)


class AddressView(CustomerAPIView):
    @extend_schema(tags=TAG, request=AddressIn, responses={200: AddressOut}, operation_id="me_address_update")
    def patch(self, request: Request, address_id: str) -> Response:
        data = _valid(AddressIn, request, partial=True)
        make_default = data.pop("make_default", False)
        address = services.update_address(self.account, address_id, data)
        if make_default:
            address = services.set_default_address(self.account, address_id)
        return Response(_address(address))

    @extend_schema(tags=TAG, responses={204: None}, operation_id="me_address_delete")
    def delete(self, request: Request, address_id: str) -> Response:
        services.delete_address(self.account, address_id)
        return Response(status=204)


class WishlistView(CustomerAPIView):
    @extend_schema(tags=TAG, responses={200: ProductCardSerializer(many=True)}, operation_id="me_wishlist")
    def get(self, request: Request) -> Response:
        locale = request_locale(request)
        ids = list(WishlistItem.objects.filter(account=self.account).values_list("product_id", flat=True))
        products = {
            p.pk: p
            for p in catalog_selectors.with_card_data(
                catalog_selectors.published().filter(pk__in=ids, status=ProductStatus.PUBLISHED)
            )
        }
        return Response([product_card(products[i], locale) for i in ids if i in products])

    @extend_schema(tags=TAG, request=WishlistIn, responses={204: None}, operation_id="me_wishlist_add")
    def post(self, request: Request) -> Response:
        services.add_to_wishlist(self.account, _valid(WishlistIn, request)["slug"])
        return Response(status=204)


class WishlistItemView(CustomerAPIView):
    @extend_schema(tags=TAG, responses={204: None}, operation_id="me_wishlist_remove")
    def delete(self, request: Request, slug: str) -> Response:
        services.remove_from_wishlist(self.account, slug)
        return Response(status=204)


class PreferencesOut(serializers.Serializer[Any]):
    newsletter = serializers.ChoiceField(choices=["none", "pending", "confirmed", "withdrawn"])
    cart_reminders = serializers.BooleanField()
    sms_updates = serializers.BooleanField()
    email_verified = serializers.BooleanField()
    has_phone = serializers.BooleanField()


class PreferencesIn(serializers.Serializer[Any]):
    newsletter = serializers.BooleanField(required=False)
    cart_reminders = serializers.BooleanField(required=False)
    sms_updates = serializers.BooleanField(required=False)


def _preferences(view: CustomerAPIView) -> dict[str, Any]:
    email = view.account.email
    return {
        "newsletter": consent.consent_status(email, ConsentPurpose.NEWSLETTER),
        "cart_reminders": consent.has_consent(email, ConsentPurpose.CART_REMINDERS),
        "sms_updates": consent.has_consent(email, ConsentPurpose.SMS_UPDATES),
        "email_verified": view.account.email_verified_at is not None,
        "has_phone": bool(services.profile(view.account).phone),
    }


class PreferencesView(CustomerAPIView):
    """Message preferences (M11). Each choice is a consent record with its wording version and time."""

    @extend_schema(tags=TAG, responses={200: PreferencesOut}, operation_id="me_preferences_get")
    def get(self, request: Request) -> Response:
        return Response(_preferences(self))

    @extend_schema(
        tags=TAG, request=PreferencesIn, responses={200: PreferencesOut}, operation_id="me_preferences_update"
    )
    def put(self, request: Request) -> Response:
        data = _valid(PreferencesIn, request)
        account = self.account
        locale = services.profile(account).preferred_locale
        wants_more = data.get("cart_reminders") or data.get("sms_updates")
        if wants_more and account.email_verified_at is None:
            raise ApiProblem(400, "email-unverified", "Verify your email address first.")
        if data.get("sms_updates") and not services.profile(account).phone:
            raise ApiProblem(400, "phone", "Add a mobile number to your profile first.")
        for purpose in (ConsentPurpose.CART_REMINDERS, ConsentPurpose.SMS_UPDATES):
            if purpose.value in data:
                consent.set_preference(account.email, purpose, data[purpose.value], locale=locale, source="account")
        if "newsletter" in data:
            if data["newsletter"]:
                if consent.consent_status(account.email, ConsentPurpose.NEWSLETTER) != "confirmed":
                    consent.request_newsletter(account.email, locale, "account")
            else:
                consent.withdraw(account.email, ConsentPurpose.NEWSLETTER)
        return Response(_preferences(self))
