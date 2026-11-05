"""Demo 3D model for local review and the end-to-end viewer tests (M6). Never run in production.

Reads a .glb on standard input (so it works through `docker compose exec -T`), runs it through the real model
pipeline and approves it for the product. Idempotent: the same file already approved is left as it is.
Shoppers still see it only where THREED_FOR_SHOPPERS is on (off until V-01 to V-03 pass).
"""

import hashlib
import sys
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.audit.services import SYSTEM
from apps.catalog import threed
from apps.catalog.models import Product, ThreeDAsset, ThreeDStatus


class Command(BaseCommand):
    help = "Approve a demo 3D model (read from stdin) for a product. Demo data only."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("product", help="Product slug")
        parser.add_argument("--name", default="demo.glb")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not getattr(settings, "ALLOW_DEMO_DATA", False):  # same rule as the catalogue
            raise CommandError("Demo data is only for local development and review environments.")
        product = Product.objects.filter(slug=options["product"]).first()
        if product is None:
            raise CommandError(f"No product {options['product']}.")
        data = sys.stdin.buffer.read()
        source = hashlib.sha256(data).hexdigest()
        done = ThreeDAsset.objects.filter(product=product, status=ThreeDStatus.APPROVED, report__source=source)
        if done.exists():
            self.stdout.write("Already approved.")
            return
        asset = threed.upload(product, options["name"], data, SYSTEM)
        threed.process(str(asset.pk))  # here, so the result is known; the queued run then does nothing
        asset.refresh_from_db()
        if asset.status != ThreeDStatus.DRAFT:
            raise CommandError(f"The model didn't process: {asset.report}")
        asset.report = {**asset.report, "source": source}
        asset.save(update_fields=["report"])
        threed.approve(asset, True, SYSTEM)
        self.stdout.write(f"Approved {asset.file_name} for {product.slug}.")
