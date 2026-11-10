"""Cart reads and writes (MTS §8 Cart). Prices are always the live variant price; stock is checked, never held."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.accounts.models import Account, AccountType
from apps.catalog import selectors as catalog_selectors
from apps.catalog.models import ProductStatus, ProductVariant
from apps.inventory import selectors as stock
from common.exceptions import ApiProblem
from common.security import new_token, token_hash

from .models import Cart, CartItem

MAX_PER_LINE = 10
MAX_LINES = 30


@dataclass
class Line:
    item: CartItem
    variant: ProductVariant
    name: str
    available: int
    problem: str | None  # unavailable | insufficient

    @property
    def line_total(self) -> Decimal:
        return self.variant.price * self.item.quantity


def for_account(account: Account, *, create: bool) -> Cart | None:
    if account.account_type != AccountType.CUSTOMER:
        return None
    cart = Cart.objects.filter(account=account).first()
    if cart is None and create:
        cart, _ = Cart.objects.get_or_create(account=account, defaults={"csrf_token": new_token()})
    return cart


def for_guest(token: str | None) -> Cart | None:
    if not token:
        return None
    return Cart.objects.filter(token_hash=token_hash(token), account__isnull=True).first()


def new_guest_cart() -> tuple[Cart, str]:
    token = new_token()
    return Cart.objects.create(token_hash=token_hash(token), csrf_token=new_token()), token


@transaction.atomic
def merge_guest_into(account: Account, guest: Cart) -> Cart:
    """On sign-in the guest cart joins the customer's cart; quantities add up to the per-line limit."""
    target = for_account(account, create=True)
    if target is None:
        raise ApiProblem(403, "customers-only", "Only customer accounts have a bag.")
    if guest.pk == target.pk:
        return target
    for gi in guest.items.all():
        existing = target.items.filter(variant_id=gi.variant_id).first()
        if existing:
            existing.quantity = min(existing.quantity + gi.quantity, MAX_PER_LINE)
            existing.save(update_fields=["quantity"])
        elif target.items.count() < MAX_LINES:
            CartItem.objects.create(cart=target, variant_id=gi.variant_id, quantity=gi.quantity)
    if guest.coupon_code and not target.coupon_code:
        target.coupon_code = guest.coupon_code
    target.reminded_at = None
    target.save()
    guest.delete()
    return target


def _sellable_variant(sku: str) -> ProductVariant:
    v = (
        ProductVariant.objects.select_related("product", "colour")
        .filter(sku=sku, is_active=True, product__status=ProductStatus.PUBLISHED)
        .first()
    )
    if v is None:
        raise ApiProblem(404, "not-found", "This item isn't available.")
    return v


def _touch(cart: Cart) -> None:
    """Any change restarts the abandoned-cart clock (M11)."""
    cart.reminded_at = None
    cart.save(update_fields=["reminded_at", "updated_at"])


@transaction.atomic
def add(cart: Cart, sku: str, quantity: int) -> CartItem:
    variant = _sellable_variant(sku)
    item = CartItem.objects.select_for_update().filter(cart=cart, variant=variant).first()
    new_qty = (item.quantity if item else 0) + quantity
    if new_qty > MAX_PER_LINE:
        raise ApiProblem(400, "quantity-limit", f"You can add up to {MAX_PER_LINE} of each item.")
    available = stock.available([variant.pk])[variant.pk]
    if new_qty > available:
        if available == 0:
            raise ApiProblem(409, "out-of-stock", "This size is sold out.")
        raise ApiProblem(409, "insufficient-stock", f"Only {available} left in this size.")
    if item is None:
        if cart.items.count() >= MAX_LINES:
            raise ApiProblem(400, "cart-full", f"Your bag can hold up to {MAX_LINES} different items.")
        item = CartItem.objects.create(cart=cart, variant=variant, quantity=new_qty)
    else:
        item.quantity = new_qty
        item.save(update_fields=["quantity"])
    _touch(cart)
    return item


@transaction.atomic
def set_quantity(cart: Cart, item_id: Any, quantity: int) -> None:
    item = CartItem.objects.select_for_update().filter(cart=cart, pk=item_id).first()
    if item is None:
        raise ApiProblem(404, "not-found", "This item isn't in your bag.")
    if not 1 <= quantity <= MAX_PER_LINE:
        raise ApiProblem(400, "quantity-limit", f"Choose between 1 and {MAX_PER_LINE}.")
    available = stock.available([item.variant_id])[item.variant_id]
    if quantity > available and quantity > item.quantity:
        raise ApiProblem(409, "insufficient-stock", f"Only {available} left in this size.")
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    _touch(cart)


def remove(cart: Cart, item_id: Any) -> None:
    CartItem.objects.filter(cart=cart, pk=item_id).delete()
    _touch(cart)


def clear(cart: Cart) -> None:
    cart.items.all().delete()
    cart.coupon_code = ""
    cart.save(update_fields=["coupon_code", "updated_at"])


def lines(cart: Cart, locale: str = "en") -> list[Line]:
    items = list(
        cart.items.select_related("variant__product", "variant__colour").prefetch_related(
            "variant__product__translations", "variant__product__images"
        )
    )
    avail = stock.available([i.variant_id for i in items])
    result = []
    for i in items:
        v = i.variant
        names = catalog_selectors.translations(v.product)
        name = names.get(locale, names.get("en", {"name": v.product.slug}))["name"]
        ok = v.is_active and v.product.status == ProductStatus.PUBLISHED
        problem = None if ok else "unavailable"
        if ok and i.quantity > avail[v.pk]:
            problem = "insufficient"
        result.append(Line(i, v, name, avail[v.pk] if ok else 0, problem))
    return result
