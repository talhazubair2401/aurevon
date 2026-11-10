"""Customer profile, addresses and wishlist writes. Every function takes the signed-in customer's account and
only ever touches that account's rows (MTS §9: customers see their own data only)."""

from typing import Any

from django.db import transaction

from apps.accounts.models import Account, AccountType
from apps.catalog.models import Product, ProductStatus
from common.exceptions import ApiProblem

from .models import Address, CustomerProfile, WishlistItem

MAX_ADDRESSES = 10


def _customer(account: Account) -> None:
    if account.account_type != AccountType.CUSTOMER:
        raise ApiProblem(403, "customers-only", "This is only available to customer accounts.")


def profile(account: Account) -> CustomerProfile:
    _customer(account)
    obj, _ = CustomerProfile.objects.get_or_create(account=account)
    return obj


@transaction.atomic
def update_profile(account: Account, data: dict[str, Any]) -> CustomerProfile:
    p = profile(account)
    if "full_name" in data:
        account.full_name = data["full_name"].strip()
        account.save(update_fields=["full_name"])
    for field in ("phone", "preferred_locale"):
        if field in data:
            setattr(p, field, data[field])
    p.save()
    return p


def _own(account: Account, address_id: Any) -> Address:
    obj = Address.objects.select_for_update().filter(account=account, pk=address_id).first()
    if obj is None:
        raise ApiProblem(404, "not-found", "This address doesn't exist.")
    return obj


@transaction.atomic
def add_address(account: Account, data: dict[str, Any], *, make_default: bool = False) -> Address:
    _customer(account)
    existing = Address.objects.select_for_update().filter(account=account)
    if existing.count() >= MAX_ADDRESSES:
        raise ApiProblem(400, "too-many-addresses", f"You can save up to {MAX_ADDRESSES} addresses.")
    first = not existing.exists()
    if make_default and not first:
        existing.filter(is_default=True).update(is_default=False)
    return Address.objects.create(account=account, is_default=first or make_default, **data)


@transaction.atomic
def update_address(account: Account, address_id: Any, data: dict[str, Any]) -> Address:
    obj = _own(account, address_id)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.save()
    return obj


@transaction.atomic
def set_default_address(account: Account, address_id: Any) -> Address:
    obj = _own(account, address_id)
    Address.objects.filter(account=account, is_default=True).exclude(pk=obj.pk).update(is_default=False)
    obj.is_default = True
    obj.save(update_fields=["is_default", "updated_at"])
    return obj


@transaction.atomic
def delete_address(account: Account, address_id: Any) -> None:
    obj = _own(account, address_id)
    was_default = obj.is_default
    obj.delete()
    if was_default:
        nxt = Address.objects.filter(account=account).order_by("-created_at").first()
        if nxt:
            nxt.is_default = True
            nxt.save(update_fields=["is_default", "updated_at"])


def add_to_wishlist(account: Account, slug: str) -> WishlistItem:
    _customer(account)
    product = Product.objects.filter(slug=slug, status=ProductStatus.PUBLISHED).first()
    if product is None:
        raise ApiProblem(404, "not-found", "This product isn't available.")
    item, _ = WishlistItem.objects.get_or_create(account=account, product=product)
    return item


def remove_from_wishlist(account: Account, slug: str) -> None:
    WishlistItem.objects.filter(account=account, product__slug=slug).delete()
