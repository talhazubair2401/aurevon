# Decision 0006 (P-12), step 2 of 3: colours become a list, categories get codes and size lists, products get
# style numbers and base prices, SKUs take the approved format. Its own migration (transaction): PostgreSQL
# refuses to alter a table with pending updates in the same transaction.
from django.db import migrations

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def forwards(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Colour = apps.get_model("catalog", "Colour")
    Product = apps.get_model("catalog", "Product")
    Variant = apps.get_model("catalog", "ProductVariant")

    used_codes: set[str] = set()

    def unique_code(seed: str) -> str:
        letters = "".join(ch for ch in seed.upper() if ch.isalpha()) + "XXX"
        for i in range(len(letters) - 2):
            code = (letters[0] + letters[i + 1 : i + 3])[:3]
            if code not in used_codes:
                used_codes.add(code)
                return code
        for n in range(26 * 26 * 26):  # fall back to any free code
            code = "".join(chr(65 + (n // d) % 26) for d in (676, 26, 1))
            if code not in used_codes:
                used_codes.add(code)
                return code
        raise RuntimeError("no free code")

    colours = {}
    for position, row in enumerate(
        Variant.objects.values("colour_slug", "colour_name_en", "colour_name_ur", "colour_hex").distinct().order_by("colour_slug")
    ):
        if row["colour_slug"] in colours:
            continue
        colours[row["colour_slug"]] = Colour.objects.create(
            slug=row["colour_slug"],
            code=unique_code(row["colour_slug"]),
            name_en=row["colour_name_en"],
            name_ur=row["colour_name_ur"],
            hex=row["colour_hex"],
            position=position,
        )
    for slug, colour in colours.items():
        Variant.objects.filter(colour_slug=slug).update(colour=colour)

    used_codes.clear()
    for category in Category.objects.order_by("department", "position", "slug"):
        dept, _, rest = category.slug.partition("-")
        category.code = unique_code((dept[:1] or "X") + (rest or category.slug))
        sizes = set(Variant.objects.filter(product__category=category).values_list("size", flat=True))
        category.sizes = sorted(sizes, key=lambda s: SIZE_ORDER.index(s) if s in SIZE_ORDER else 99)
        category.save(update_fields=["code", "sizes"])

    for number, product in enumerate(Product.objects.order_by("created_at", "slug"), start=1):
        prices = list(Variant.objects.filter(product=product).values_list("price", flat=True))
        product.style_number = number
        product.base_price = min(prices) if prices else 0
        product.save(update_fields=["style_number", "base_price"])
        Variant.objects.filter(product=product).exclude(price=product.base_price).update(price_overridden=True)

    # SKUs in the approved format. Nothing has been sold yet (orders arrive in M8), so this is the last change.
    for v in Variant.objects.select_related("product__category", "colour"):
        v.sku = f"AV-{v.product.category.code}-{v.product.style_number:04d}-{v.colour.code}-{v.size.upper()}"
        v.save(update_fields=["sku"])


def backwards(apps, schema_editor):
    Variant = apps.get_model("catalog", "ProductVariant")
    for v in Variant.objects.select_related("colour"):
        v.colour_slug, v.colour_name_en, v.colour_name_ur, v.colour_hex = (
            v.colour.slug, v.colour.name_en, v.colour.name_ur, v.colour.hex
        )
        v.save(update_fields=["colour_slug", "colour_name_en", "colour_name_ur", "colour_hex"])



class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_p12_expand")]
    operations = [migrations.RunPython(forwards, backwards)]
