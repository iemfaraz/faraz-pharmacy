"""Demo mode (deployment fallback).

PaddleOCR needs ~1GB+ RAM to load its models — more than free-tier hosts
(Streamlit Community Cloud) provide. When DEMO_MODE is on, the app skips
importing PaddleOCR entirely and serves pre-extracted results for a set
of bundled sample receipts. The ENTIRE downstream product — review/edit,
confidence flags, database, dashboard, export — runs for real on this
data. Only the OCR inference step is pre-computed.

DEMO_MODE resolves True when:
- the env var INVOICE_AI_DEMO is set (how the deployment turns it on), or
- PaddleOCR cannot be imported (so a memory-starved host degrades
  gracefully instead of erroring).

Locally, with PaddleOCR installed and the env var unset, DEMO_MODE is
False and the app behaves exactly as built — live OCR on any upload.

The extracted values below are the real outputs verified during the
build (Milestones 5-7): field values, per-field confidences, and line
items, including the honest low-confidence flags and math-mismatch cases.
"""

from __future__ import annotations

import os

from app.extraction.rules import ExtractedFields
from app.extraction.tables import LineItem, TableResult
from app.ocr.engine import OcrLine


def demo_mode_enabled() -> bool:
    if os.environ.get("INVOICE_AI_DEMO"):
        return True
    try:
        import paddleocr  # noqa: F401
        return False
    except Exception:
        return True


# --- bundled sample receipts (images live in data/test_invoices/) ----------

SAMPLES = {
    "Pinewood Cafe (Bangladesh, with discount)": "photo_pinewood.jpg",
    "Beef-a-Roo (USA, clean)": "photo_beefaroo.jpg",
    "BFC (Bangladesh, inclusive VAT)": "photo_bfc.jpg",
    "Juices N Chills (India, GST-unregistered)": "photo_juicesnchills.jpg",
}


def _fields(vendor, date, subtotal, tax, total, currency, conf) -> ExtractedFields:
    f = ExtractedFields(vendor=vendor, date=date, subtotal=subtotal,
                        tax=tax, total=total, currency=currency)
    f.confidence = conf
    return f


def _items(rows) -> TableResult:
    t = TableResult()
    for desc, qty, price, line_total, c in rows:
        t.items.append(LineItem(description=desc, quantity=qty, unit_price=price,
                                line_total=line_total, confidence=c))
    return t


# Pre-extracted results verified during the build.
_RESULTS = {
    "photo_pinewood.jpg": {
        "fields": _fields("Pinewood Cafe+Kitchen", "2026-07-30", 937.0, 45.85,
                          980.0, "BDT",
                          {"vendor": 0.81, "date": 0.65, "subtotal": 0.92,
                           "tax": 0.96, "total": 0.69, "currency": 0.80}),
        "table": _items([
            ("SMOKED CHICKEN SANDWICH", 1, 339.0, 339.0, 0.78),
            ("CHICKEN CHEESE BURGER", 1, 309.0, 309.0, 0.75),
            ("MILK SHAKE", 1, 269.0, 269.0, 0.76),
            ("BOTTLE OF WATER", 1, 20.0, 20.0, 0.77),
        ]),
        "note": "Discount + rounding: subtotal+tax exceeds total by 2.85 — flagged for review, not silently altered.",
    },
    "photo_beefaroo.jpg": {
        "fields": _fields("Beef-a-Roo", "2020-02-20", 12.37, 1.02, 13.39, "USD",
                          {"vendor": 0.94, "date": 0.90, "subtotal": 0.87,
                           "tax": 1.0, "total": 0.90, "currency": 0.0}),
        "table": _items([
            ("5pc Chicken Strip (Ranch) (Buffalo Sauce)", None, None, 6.29, 0.74),
            ("Onion Rings", None, None, 3.09, 0.77),
            ("Large Fry", None, None, 2.99, 0.78),
        ]),
        "note": "Clean receipt: items sum exactly to subtotal, all fields high-confidence.",
    },
    "photo_bfc.jpg": {
        "fields": _fields("Best Fried Chicken (BFC)", "2026-07-19", None, 15.48,
                          325.0, "BDT",
                          {"vendor": 0.90, "date": 0.85, "subtotal": 0.0,
                           "tax": 0.89, "total": 0.89, "currency": 0.60}),
        "table": _items([
            ("Garlic Wrap", 1, 220.0, 220.0, 0.78),
            ("Extra Cheese", 1, 30.0, 30.0, 0.78),
            ("Coleslaw", 1, 75.0, 75.0, 0.79),
        ]),
        "note": "VAT is inclusive of total (no separate subtotal) — correctly left blank rather than guessed.",
    },
    "photo_juicesnchills.jpg": {
        "fields": _fields("JUICES N CHILLS", "2023-03-29", None, None, 120.0,
                          "INR",
                          {"vendor": 0.98, "date": 0.87, "subtotal": 0.0,
                           "tax": 0.0, "total": 0.88, "currency": 0.0}),
        "table": _items([("Fruit Chat", 1, 120.0, 120.0, 0.79)]),
        "note": "GST-unregistered vendor: zero tax is correct data, not a missed field.",
    },
}


def demo_pipeline(sample_filename: str) -> dict:
    """Return the same dict shape run_pipeline() produces, from cached data."""
    data = _RESULTS[sample_filename]
    placeholder_line = OcrLine(text="(demo mode — OCR precomputed)",
                               confidence=1.0,
                               bbox=[[0, 0], [1, 0], [1, 1], [0, 1]])
    return {"lines": [placeholder_line], "fields": data["fields"],
            "table": data["table"], "demo_note": data["note"]}
