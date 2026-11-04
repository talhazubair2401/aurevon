"""What staff may put into CMS content, and how it is checked (MTS §12: validate every field).

Content is plain text in a fixed shape: there is no HTML anywhere, so nothing needs sanitising and the
storefront renders every value as text. Links are storefront paths only ("/shop?department=women"), never
other sites, so content can't send shoppers off the domain. Per-language copy is {"en": {...}, "ur": {...}}:
English is required where a field is required; Urdu is optional and falls back to English field by field.
"""

import re
from dataclasses import dataclass
from typing import Any, Literal

from .models import HomepageSectionKey

LOCALES = ("en", "ur")
Kind = Literal["text", "textarea", "href"]

# Storefront paths: start with one "/", carry no locale (the storefront adds it) and no scheme or host.
_HREF = re.compile(r"^/(?!/)[A-Za-z0-9\-._~/?=&%+,]*$")
_REDIRECT_FROM = re.compile(r"^/(?!/)[a-z0-9\-_/]*[a-z0-9\-_]$")
RESERVED_PREFIXES = ("/api", "/staff", "/_next", "/media", "/3d", "/internal", "/health")


class ContentError(ValueError):
    """A readable reason, shown to staff as-is."""


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: Kind = "text"
    max_length: int = 120
    required: bool = False
    translatable: bool = True  # links are shared by both languages and edited once

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "max_length": self.max_length,
            "required": self.required,
            "translatable": self.translatable,
        }


def _link(prefix: str, label: str) -> list[Field]:
    return [
        Field(f"{prefix}_label", f"{label} label", max_length=40),
        Field(f"{prefix}_href", f"{label} link", kind="href", max_length=200, translatable=False),
    ]


SECTION_FIELDS: dict[str, list[Field]] = {
    HomepageSectionKey.HERO: [
        Field("eyebrow", "Eyebrow", max_length=80),
        Field("title", "Title", required=True),
        Field("subtitle", "Subtitle", kind="textarea", max_length=300),
        *_link("primary", "Primary button"),
        *_link("secondary", "Secondary button"),
    ],
    HomepageSectionKey.COLLECTIONS: [
        Field("title", "Title", required=True),
        Field("subtitle", "Subtitle", kind="textarea", max_length=300),
    ],
    HomepageSectionKey.FEATURED_PRODUCTS: [Field("title", "Title", required=True), *_link("link", "Link")],
    HomepageSectionKey.NEW_ARRIVALS: [Field("title", "Title", required=True), *_link("link", "Link")],
    HomepageSectionKey.BRAND_STORY: [
        Field("eyebrow", "Eyebrow", max_length=80),
        Field("title", "Title", required=True),
        Field("body", "Story", kind="textarea", max_length=1200),
        *_link("link", "Link"),
    ],
}

# Banners are placed by the storefront by key; each placement has a fixed shape.
BANNER_FIELDS: dict[str, list[Field]] = {
    "shop_editorial": [
        Field("title", "Title", required=True, max_length=60),
        Field("body", "Text", kind="textarea", max_length=300),
        *_link("link", "Link"),
    ],
}

PAGE_FIELDS: list[Field] = [
    Field("title", "Title", required=True),
    Field("summary", "Summary", kind="textarea", max_length=300),
    Field("seo_title", "Search title", max_length=70),
    Field("seo_description", "Search description", kind="textarea", max_length=160),
]
SEO_FIELDS: list[Field] = [
    Field("title", "Search title", max_length=70),
    Field("description", "Search description", kind="textarea", max_length=160),
]

BLOCK_TYPES = ("heading", "paragraph", "list")
MAX_BLOCKS = 100
MAX_PARAGRAPH = 4000
MAX_LIST_ITEMS = 30
MAX_MENU_ITEMS = 12


def validate_href(value: Any, label: str = "Link") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"{label}: enter a storefront path such as /shop.")
    href = value.strip()
    if len(href) > 200 or not _HREF.match(href):
        raise ContentError(f"{label}: use a storefront path that starts with /, such as /shop?department=women.")
    first = href.split("?")[0].split("/")[1] if "/" in href else ""
    if first in LOCALES:
        raise ContentError(f"{label}: leave out the language (/en or /ur); the storefront adds it.")
    if href.split("?")[0].startswith(RESERVED_PREFIXES):
        raise ContentError(f"{label}: that path isn't a storefront page.")
    return href


def _text(value: Any, field: Field, where: str) -> str:
    if not isinstance(value, str):
        raise ContentError(f"{where}{field.label}: must be text.")
    text = value.strip()
    if field.kind == "text":
        text = " ".join(text.split())  # single line
    if len(text) > field.max_length:
        raise ContentError(f"{where}{field.label}: use at most {field.max_length} characters.")
    return text


def validate_fields(raw: Any, fields: list[Field]) -> dict[str, dict[str, str]]:
    """{"en": {...}, "ur": {...}} for a fixed field list. Unknown keys are refused; empty values are dropped."""
    if not isinstance(raw, dict) or not set(raw) <= set(LOCALES):
        raise ContentError('Content must be {"en": {...}, "ur": {...}}.')
    by_name = {f.name: f for f in fields}
    result: dict[str, dict[str, str]] = {}
    for locale in LOCALES:
        values = raw.get(locale) or {}
        if not isinstance(values, dict):
            raise ContentError(f"{locale}: must be an object.")
        unknown = set(values) - set(by_name)
        if unknown:
            raise ContentError(f"Unknown field: {sorted(unknown)[0]}.")
        where = "Urdu: " if locale == "ur" else ""
        clean: dict[str, str] = {}
        for name, value in values.items():
            field = by_name[name]
            if value in (None, ""):
                continue
            if not field.translatable and locale != "en":
                continue  # shared values are kept once, in English
            clean[name] = (
                validate_href(value, f"{where}{field.label}") if field.kind == "href" else _text(value, field, where)
            )
            if clean[name] == "":
                del clean[name]
        result[locale] = clean
    for field in fields:
        if field.required and not result["en"].get(field.name):
            raise ContentError(f"{field.label} is required in English.")
    for field in fields:
        if field.kind == "href" and field.name.endswith("_href"):
            label_name = field.name.removesuffix("_href") + "_label"
            if result["en"].get(label_name) and not result["en"].get(field.name):
                raise ContentError(f"{field.label}: add a link for the label.")
    return result


def _blocks(raw: Any, where: str) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_BLOCKS:
        raise ContentError(f"{where}Body: use a list of at most {MAX_BLOCKS} blocks.")
    blocks: list[dict[str, Any]] = []
    for index, block in enumerate(raw, start=1):
        if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
            raise ContentError(f"{where}Block {index}: the type must be heading, paragraph or list.")
        kind = block["type"]
        if set(block) - {"type", "text", "items"}:
            raise ContentError(f"{where}Block {index}: unknown property.")
        if kind == "list":
            items = block.get("items")
            if not isinstance(items, list) or not items or len(items) > MAX_LIST_ITEMS:
                raise ContentError(f"{where}Block {index}: a list needs 1 to {MAX_LIST_ITEMS} items.")
            clean_items = [
                _text(item, Field("item", f"Block {index} item", kind="textarea", max_length=500), where)
                for item in items
            ]
            clean_items = [i for i in clean_items if i]
            if clean_items:
                blocks.append({"type": "list", "items": clean_items})
            continue
        limit = 120 if kind == "heading" else MAX_PARAGRAPH
        text = _text(
            block.get("text", ""),
            Field("text", f"Block {index}", kind="text" if kind == "heading" else "textarea", max_length=limit),
            where,
        )
        if text:
            blocks.append({"type": kind, "text": text})
    return blocks


def validate_page(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ContentError('Content must be {"en": {...}, "ur": {...}}.')
    plain = {
        locale: {k: v for k, v in (raw.get(locale) or {}).items() if k != "body"}
        for locale in LOCALES
        if isinstance(raw.get(locale) or {}, dict)
    }
    result: dict[str, dict[str, Any]] = dict(validate_fields(plain, PAGE_FIELDS))
    for locale in LOCALES:
        where = "Urdu: " if locale == "ur" else ""
        body = _blocks((raw.get(locale) or {}).get("body"), where)
        if body:
            result[locale]["body"] = body
    if not result["en"].get("body"):
        raise ContentError("Body is required in English: add at least one paragraph.")
    return result


def validate_section(key: str, raw: Any) -> dict[str, dict[str, str]]:
    return validate_fields(raw, SECTION_FIELDS[key])


def validate_banner(key: str, raw: Any) -> dict[str, dict[str, str]]:
    fields = BANNER_FIELDS.get(key)
    if fields is None:
        raise ContentError("The storefront doesn't place a banner with that key.")
    return validate_fields(raw, fields)


def validate_seo(raw: Any) -> dict[str, dict[str, str]]:
    return validate_fields(raw, SEO_FIELDS)


def validate_menu(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) > MAX_MENU_ITEMS:
        raise ContentError(f"A menu holds at most {MAX_MENU_ITEMS} links.")
    clean: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict) or set(item) - {"label", "href"}:
            raise ContentError(f"Link {index}: use a label and a link.")
        label = validate_fields(
            {k: {"label": v} for k, v in (item.get("label") or {}).items()},
            [Field("label", f"Link {index} label", max_length=40, required=True)],
        )
        clean.append(
            {
                "label": {k: v["label"] for k, v in label.items() if v.get("label")},
                "href": validate_href(item.get("href"), f"Link {index}"),
            }
        )
    return clean


def validate_redirect_from(value: Any) -> str:
    if not isinstance(value, str):
        raise ContentError("From: enter a path such as /pages/old-name.")
    path = value.strip()
    if len(path) > 200 or not _REDIRECT_FROM.match(path):
        raise ContentError("From: use a path in lower case, without a query, such as /pages/old-name.")
    if path.split("/")[1] in LOCALES:
        raise ContentError("From: leave out the language (/en or /ur); a redirect covers both languages.")
    if path.startswith(RESERVED_PREFIXES):
        raise ContentError("From: that path isn't a storefront page.")
    return path


def localised(content: dict[str, Any], locale: str) -> dict[str, Any]:
    """The copy in `locale`, falling back field by field to English."""
    english: dict[str, Any] = content.get("en", {})
    chosen: dict[str, Any] = content.get(locale, {})
    return {**english, **{k: v for k, v in chosen.items() if v not in (None, "", [])}}
