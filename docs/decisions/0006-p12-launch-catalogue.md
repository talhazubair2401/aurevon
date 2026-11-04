# 0006 — P-12: launch catalogue rules

Date: 4 November 2026 · Decided by: Talha (product owner) · Blueprint: MTS v2.1 §6, §7 (M02, M14), §16 (M5)
Status: **APPROVED** (all 12 recommendations; #4 adjusted)

| # | Decision |
| --- | --- |
| 1 | Departments: Women and Men. Kids and unisex can be added later without structural change. |
| 2 | Categories: Women — Dresses, Kurtas, Outerwear, Trousers, Skirts; Men — Shirts, Kurtas, Knitwear, Tailoring, Trousers. Staff can add more. |
| 3 | Stitched ready-to-wear only at launch. Unstitched fabric later as its own category with a single size. |
| 4 **(adjusted)** | **Both letter sizes (XS–XXL) and numeric sizes (e.g. 28, 30, 32, 34). Each category has its own configurable, ordered size list and its own size chart in cm.** |
| 5 | Staff-managed colour list: English name, Urdu name, swatch. A variant is one size in one colour. |
| 6 | SKU `AV-{category}-{style no.}-{colour}-{size}`, e.g. `AV-WKU-0012-IVR-M`; generated, never changed once a variant has been sold. |
| 7 | One price per product in PKR; a variant may override it. Sale prices with promotions (M11). Tax-inclusive display waits for P-11. |
| 8 | Product details: name and description in English and Urdu, fabric, care, fit note, style number. Drafts until published by a role with `catalog.publish`. |
| 9 | Images 4:5 portrait, at least 1600×2000 px, front, back and detail per colour, with alt text. Illustrations stand in until the imagery decision. |
| 10 | Staff entry in the dashboard plus CSV import for bulk loading. The demo catalogue is local and review only. |
| 11 | One stock record per variant in the sellable location "Main warehouse", starting at 0. Quantities are entered in M9; M5 shows available or unavailable. |
| 12 | No fixed launch size. |

Before launch the owner supplies the real product list, size-chart measurements and images. MTS v2.1 is not
edited; the next MTS revision moves P-12 into the approved register as A-31.
