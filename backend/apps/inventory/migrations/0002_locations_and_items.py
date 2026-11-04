# The three location kinds (MTS §11) and one Main warehouse record per existing variant, at 0 (decision 0006, #11).
from django.db import migrations


def forwards(apps, schema_editor):
    Location = apps.get_model("inventory", "StockLocation")
    Item = apps.get_model("inventory", "InventoryItem")
    Variant = apps.get_model("catalog", "ProductVariant")
    for code, name, kind in (
        ("main", "Main warehouse", "sellable"),
        ("quarantine", "Quarantine", "quarantine"),
        ("damaged", "Damaged", "damaged"),
    ):
        Location.objects.update_or_create(code=code, defaults={"name": name, "kind": kind})
    Item.objects.bulk_create(
        [Item(variant_id=v, location_id="main") for v in Variant.objects.values_list("id", flat=True)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial"), ("catalog", "0004_p12_contract")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
