"""CSV import for bulk loading the catalogue (decision 0006, #10).

One row per product. A row whose `slug` exists updates that product; any other row creates a draft. Every row
is checked before anything is written: one bad row and nothing changes (a dry run shows the same report).
Publishing stays a separate, deliberate step. Prices are set from the file, so importing needs `prices.edit`.
"""

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from apps.audit.services import Actor, record

from . import editing
from .models import Category, Colour, Product

COLUMNS = [
    "slug",
    "category",
    "name_en",
    "name_ur",
    "description_en",
    "description_ur",
    "fabric_en",
    "fabric_ur",
    "care_en",
    "care_ur",
    "fit_note_en",
    "fit_note_ur",
    "base_price",
    "colours",
    "sizes",
    "featured",
]
REQUIRED = {"slug", "category", "name_en", "base_price", "colours", "sizes"}
MAX_ROWS = 2000
MAX_BYTES = 2 * 1024 * 1024


@dataclass
class ImportReport:
    rows: int = 0
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    applied: bool = False


def template() -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    writer.writerow(
        [
            "block-print-kurta",
            "women-kurtas",
            "Block-Print Kurta",
            "بلاک پرنٹ کرتا",
            "",
            "",
            "Cotton lawn",
            "",
            "Machine wash cold",
            "",
            "True to size",
            "",
            "9800",
            "ivory|sage",
            "XS|S|M|L",
            "no",
        ]
    )
    return out.getvalue()


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def _parse(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(text))
    header = set(reader.fieldnames or [])
    missing = REQUIRED - header
    if missing:
        return [], [{"row": 1, "message": f"Missing columns: {', '.join(sorted(missing))}."}]
    unknown = header - set(COLUMNS)
    if unknown:
        return [], [{"row": 1, "message": f"Unknown columns: {', '.join(sorted(unknown))}."}]
    rows, errors = [], []
    categories = {c.slug: c for c in Category.objects.all()}
    colours = set(Colour.objects.values_list("slug", flat=True))
    seen: set[str] = set()
    for number, raw in enumerate(reader, start=2):
        if number - 1 > MAX_ROWS:
            errors.append({"row": number, "message": f"At most {MAX_ROWS} rows per file."})
            break
        row = {k: (v or "").strip() for k, v in raw.items() if k}
        try:
            slug = editing._slug(row["slug"])
            if slug in seen:
                raise editing.CatalogError("This address appears twice in the file.")
            seen.add(slug)
            category = categories.get(row["category"])
            if category is None:
                raise editing.CatalogError(f"Unknown category {row['category']!r}.")
            row_colours = _split(row["colours"])
            if not row_colours or set(row_colours) - colours:
                raise editing.CatalogError("Colours: existing colour addresses separated by |, e.g. ivory|sage.")
            row_sizes = [s.upper() for s in _split(row["sizes"])]
            if not row_sizes or set(row_sizes) - set(category.sizes):
                raise editing.CatalogError(f"Sizes: this category sells {'|'.join(category.sizes)}.")
            editing.price(row["base_price"], "Base price")
            if not row.get("name_en"):
                raise editing.CatalogError("English name is required.")
            rows.append({**row, "slug": slug, "colours": row_colours, "sizes": row_sizes, "number": number})
        except editing.CatalogError as exc:
            errors.append({"row": number, "message": str(exc)})
    return rows, errors


def run(data: bytes, actor: Actor, apply: bool, request: Any = None) -> ImportReport:
    report = ImportReport()
    if len(data) > MAX_BYTES:
        report.errors.append({"row": 0, "message": "The file is larger than 2 MB. Split it into smaller files."})
        return report
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        report.errors.append({"row": 0, "message": "Save the file as CSV UTF-8 (keeps Urdu text intact)."})
        return report
    rows, report.errors = _parse(text)
    report.rows = len(rows) + len([e for e in report.errors if e["row"] > 1])
    existing = set(Product.objects.filter(slug__in=[r["slug"] for r in rows]).values_list("slug", flat=True))
    for r in rows:
        (report.updated if r["slug"] in existing else report.created).append(r["slug"])
    if report.errors or not apply:
        return report
    try:
        with transaction.atomic():
            for r in rows:
                copy = {
                    loc: {f: r.get(f"{f}_{loc}", "") for f in ("name", "description", "fabric", "care", "fit_note")}
                    for loc in ("en", "ur")
                }
                data_in = {
                    "slug": r["slug"],
                    "category": r["category"],
                    "copy": copy,
                    "is_featured": r.get("featured", "").lower() in ("yes", "true", "1"),
                }
                product = Product.objects.filter(slug=r["slug"]).first()
                if product is None:
                    product = editing.create_product({**data_in, "base_price": r["base_price"]}, actor, True, request)
                else:
                    product = editing.update_product(product, data_in, actor, request)
                editing.set_variants(product, r["colours"], r["sizes"], actor, request)
                editing.set_prices(product, r["base_price"], None, actor, request)
            record(
                "catalog.import",
                actor,
                target_type="import",
                after={"created": report.created, "updated": report.updated},
                request=request,
            )
    except editing.CatalogError as exc:
        report.errors.append({"row": 0, "message": str(exc)})
        return report
    report.applied = True
    return report
