# Decision 0006 (P-12), step 1 of 3: add the new tables and columns (nullable where data must be filled first).
import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Colour",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=40, unique=True)),
                ("code", models.CharField(max_length=3, unique=True)),
                ("name_en", models.CharField(max_length=40)),
                ("name_ur", models.CharField(max_length=40)),
                ("hex", models.CharField(max_length=7)),
                ("position", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["position", "name_en"]},
        ),
        migrations.AddConstraint(
            model_name="colour",
            constraint=models.CheckConstraint(condition=models.Q(code__regex="^[A-Z]{3}$"), name="colour_code_format"),
        ),
        migrations.AddConstraint(
            model_name="colour",
            constraint=models.CheckConstraint(
                condition=models.Q(hex__regex="^#[0-9A-Fa-f]{6}$"), name="colour_hex_format"
            ),
        ),
        # Expand
        migrations.AddField("category", "code", models.CharField(max_length=3, null=True)),
        migrations.AddField("category", "sizes", models.JSONField(default=list)),
        migrations.AddField("category", "size_chart", models.JSONField(default=list)),
        migrations.AddField("product", "style_number", models.PositiveIntegerField(null=True)),
        migrations.AddField("product", "base_price", models.DecimalField(decimal_places=2, max_digits=12, null=True)),
        migrations.AddField("producttranslation", "fabric", models.CharField(blank=True, max_length=300)),
        migrations.AddField("producttranslation", "care", models.CharField(blank=True, max_length=300)),
        migrations.AddField("producttranslation", "fit_note", models.CharField(blank=True, max_length=300)),
        migrations.AddField(
            "producttranslation", "search_vector", django.contrib.postgres.search.SearchVectorField(null=True)
        ),
        migrations.AddField(
            "productvariant",
            "colour",
            models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="variants", to="catalog.colour"
            ),
        ),
        migrations.AddField("productvariant", "price_overridden", models.BooleanField(default=False)),
    ]
