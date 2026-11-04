# Decision 0006 (P-12), step 3 of 3: drop the old colour columns, make the new fields required, add constraints.
# Rollback: one-way once the old colour columns are dropped (no production data yet); restore from backup.
import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_p12_move_data")]

    operations = [
        migrations.RemoveConstraint(model_name="productvariant", name="variant_size_colour_unique"),
        migrations.RemoveField("productvariant", "colour_slug"),
        migrations.RemoveField("productvariant", "colour_name_en"),
        migrations.RemoveField("productvariant", "colour_name_ur"),
        migrations.RemoveField("productvariant", "colour_hex"),
        migrations.AlterField("category", "code", models.CharField(max_length=3, unique=True)),
        migrations.AlterField("product", "style_number", models.PositiveIntegerField(unique=True)),
        migrations.AlterField("product", "base_price", models.DecimalField(decimal_places=2, max_digits=12)),
        migrations.AlterField(
            "productvariant",
            "colour",
            models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="variants", to="catalog.colour"),
        ),
        migrations.AddConstraint(
            model_name="productvariant",
            constraint=models.UniqueConstraint(fields=("product", "size", "colour"), name="variant_size_colour_unique"),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.CheckConstraint(condition=models.Q(code__regex="^[A-Z]{3}$"), name="category_code_format"),
        ),
        migrations.AddIndex(
            model_name="producttranslation",
            index=django.contrib.postgres.indexes.GinIndex(fields=["search_vector"], name="product_translation_search"),
        ),
        ]
