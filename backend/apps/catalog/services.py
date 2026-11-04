"""Catalogue writes. Other apps call these, never the models directly (MTS §5)."""

from django.db import transaction
from django.db.models import Max, Min

from .models import Product


@transaction.atomic
def refresh_price_range(product: Product) -> None:
    """Keep the denormalised price range in step with the product's active variants."""
    agg = product.variants.filter(is_active=True).aggregate(lo=Min("price"), hi=Max("price"))
    Product.objects.filter(pk=product.pk).update(price_min=agg["lo"], price_max=agg["hi"])
    product.price_min, product.price_max = agg["lo"], agg["hi"]
