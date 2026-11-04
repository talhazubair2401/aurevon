# ruff: noqa: RUF001  (Urdu copy correctly uses the Arabic full stop and comma)
"""Demo pages, menus and search settings for local review (used by seed_demo_catalog; never production).

Policy pages are deliberately placeholders: shipping (P-13), returns (P-14), privacy and terms (P-11) are open
decisions, so no window, fee or legal term is invented here. Urdu copy needs a native-speaker review.
"""

from typing import Any


def _p(text: str) -> dict[str, str]:
    return {"type": "paragraph", "text": text}


def _h(text: str) -> dict[str, str]:
    return {"type": "heading", "text": text}


PENDING_EN = "This policy is being finalised. The full text will be published here before the store opens."
PENDING_UR = "یہ پالیسی حتمی مراحل میں ہے۔ مکمل متن اسٹور کے آغاز سے پہلے یہاں شائع کیا جائے گا۔"


def _policy(title_en: str, title_ur: str, summary_en: str, summary_ur: str, decision: str) -> dict[str, Any]:
    return {
        "en": {
            "title": title_en,
            "summary": summary_en,
            "body": [
                _p(PENDING_EN),
                _p(f"Demo placeholder: the terms depend on open decision {decision}."),
            ],
        },
        "ur": {"title": title_ur, "summary": summary_ur, "body": [_p(PENDING_UR)]},
    }


PAGES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "about",
        "content",
        {
            "en": {
                "title": "Our story",
                "summary": "Heritage craft and modern tailoring, pared back to what lasts.",
                "body": [
                    _p(
                        "AureVon begins with the craft we grew up around: hand embroidery, fine cotton and the "
                        "patience of a good tailor."
                    ),
                    _h("Modern heritage"),
                    _p(
                        "We pare those traditions back to clean lines and quiet colour, so every piece feels as "
                        "certain today as it will in ten years."
                    ),
                    _h("What we care about"),
                    {
                        "type": "list",
                        "items": [
                            "Considered cuts for women and men",
                            "Fabrics chosen to last",
                            "Fewer, better pieces",
                        ],
                    },
                ],
            },
            "ur": {
                "title": "ہماری کہانی",
                "summary": "روایتی کاریگری اور جدید سلائی، صرف وہ جو دیرپا ہو۔",
                "body": [
                    _p(
                        "AureVon کی ابتدا اُس کاریگری سے ہوتی ہے جس کے ساتھ ہم بڑے ہوئے: "
                        "ہاتھ کی کڑھائی، عمدہ کاٹن اور ایک اچھے درزی کا صبر۔"
                    ),
                    _h("جدید روایت"),
                    _p("ہم ان روایات کو صاف لکیروں اور پُرسکون رنگوں میں ڈھالتے ہیں۔"),
                ],
            },
        },
    ),
    (
        "contact",
        "content",
        {
            "en": {
                "title": "Contact us",
                "summary": "How to reach the AureVon team.",
                "body": [
                    _p(
                        "Demo placeholder: contact details and support hours are added once the support "
                        "setup is decided."
                    ),
                    _p("For now, the contact form arrives with customer support in M12."),
                ],
            },
            "ur": {
                "title": "رابطہ کریں",
                "summary": "AureVon ٹیم سے رابطے کا طریقہ۔",
                "body": [_p("رابطے کی تفصیلات جلد یہاں شائع کی جائیں گی۔")],
            },
        },
    ),
    (
        "shipping",
        "policy",
        _policy("Shipping", "ترسیل", "Delivery areas, fees and timings.", "ترسیل کے علاقے، فیس اور اوقات۔", "P-13"),
    ),
    (
        "returns",
        "policy",
        _policy(
            "Returns and exchanges",
            "واپسی اور تبادلہ",
            "How returns and exchanges work.",
            "واپسی اور تبادلے کا طریقہ۔",
            "P-14",
        ),
    ),
    (
        "privacy",
        "policy",
        _policy(
            "Privacy policy",
            "رازداری کی پالیسی",
            "How we collect and use personal data.",
            "ذاتی معلومات کا استعمال۔",
            "P-11",
        ),
    ),
    (
        "terms",
        "policy",
        _policy(
            "Terms of sale", "فروخت کی شرائط", "The terms that apply to every order.", "ہر آرڈر پر لاگو شرائط۔", "P-11"
        ),
    ),
]


def _link(en: str, ur: str, href: str) -> dict[str, Any]:
    return {"label": {"en": en, "ur": ur}, "href": href}


NAVIGATION: dict[str, list[dict[str, Any]]] = {
    "header": [
        _link("Shop All", "تمام مصنوعات", "/shop"),
        _link("Women", "خواتین", "/shop?department=women"),
        _link("Men", "مرد", "/shop?department=men"),
        _link("Collections", "کلیکشنز", "/collections"),
    ],
    "footer_shop": [
        _link("Shop All", "تمام مصنوعات", "/shop"),
        _link("New arrivals", "نئی آمد", "/shop?sort=newest"),
        _link("Collections", "کلیکشنز", "/collections"),
        _link("Our story", "ہماری کہانی", "/pages/about"),
    ],
    "footer_help": [
        _link("Contact us", "رابطہ کریں", "/pages/contact"),
        _link("Shipping", "ترسیل", "/pages/shipping"),
        _link("Returns", "واپسی", "/pages/returns"),
        _link("Privacy", "رازداری", "/pages/privacy"),
        _link("Terms of sale", "شرائط", "/pages/terms"),
    ],
}

SEO: dict[str, dict[str, Any]] = {
    "home": {
        "en": {
            "title": "AureVon · Modern Style. Timeless Confidence.",
            "description": "Modern heritage fashion for women and men: kurtas, tailoring, knitwear and eveningwear.",
        },
        "ur": {
            "title": "AureVon · جدید انداز۔ لازوال اعتماد۔",
            "description": "خواتین اور مردوں کے لیے جدید روایتی فیشن۔",
        },
    },
    "shop": {
        "en": {"title": "Shop All", "description": "Considered pieces for women and men, from kurtas to tailoring."},
        "ur": {"title": "تمام مصنوعات", "description": "خواتین اور مردوں کے لیے منتخب لباس۔"},
    },
    "collections": {
        "en": {"title": "Collections", "description": "The Heritage Edit, Modern Tailoring and Evening."},
        "ur": {"title": "کلیکشنز", "description": "ہیریٹیج ایڈٹ، جدید سلائی اور شام۔"},
    },
}
