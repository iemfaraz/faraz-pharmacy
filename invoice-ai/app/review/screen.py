"""Review & edit screen (Milestone 7).

The trust-building step: everything the pipeline extracted, shown
editable next to the invoice image, color-coded by confidence, with
live math validation. Nothing is saved without passing human eyes.

Design decisions:
- Pure functions where possible; Streamlit calls only in render_*.
- Confidence -> icon thresholds match the metrics view (>=0.8 green,
  >=0.5 yellow, else red) so the whole app speaks one language.
- Validation WARNS, never blocks: receipts legitimately have inclusive
  tax, discounts, and rounding. The human decides; we inform.
- Save writes reviewed JSON to outputs/ for now — Milestone 8 swaps
  this for the database without touching the form logic.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from app.extraction.rules import ExtractedFields
from app.extraction.tables import TableResult

REVIEWED_DIR = config.OUTPUT_DIR / "reviewed"


def conf_icon(conf: float) -> str:
    return "🟢" if conf >= 0.8 else ("🟡" if conf >= 0.5 else "🔴")


def _parse_iso(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_amounts(subtotal, tax, total, items_sum) -> list[str]:
    """Pure validation logic — unit-testable without Streamlit."""
    warnings = []
    if None not in (subtotal, tax, total):
        gap = (subtotal + tax) - total
        # tight tolerance: 5 cents or 0.1% — a review screen must surface
        # real discounts/rounding, not silently absorb them like the
        # extractor's looser internal checks do
        if abs(gap) > max(0.05, (total or 0) * 0.001):
            warnings.append(
                f"Subtotal + tax = {subtotal + tax:.2f} but total = {total:.2f} "
                f"(gap {gap:+.2f}) — could be a discount, inclusive tax, or a misread."
            )
    if items_sum is not None and subtotal is not None and items_sum > 0:
        if abs(items_sum - subtotal) > max(0.02, subtotal * 0.02):
            warnings.append(
                f"Line items sum to {items_sum:.2f} but subtotal is {subtotal:.2f} — "
                "check for missed or duplicated items."
            )
    return warnings


def render_review(fields: ExtractedFields, table: TableResult,
                  source_file: str) -> None:
    """Editable form pre-filled with extraction results."""
    st.subheader("Review & edit")
    st.caption("Check flagged fields (🟡/🔴), fix anything wrong, then save.")

    conf = fields.confidence

    c1, c2 = st.columns(2)
    vendor = c1.text_input(
        f"{conf_icon(conf.get('vendor', 0))} Vendor",
        value=fields.vendor or "", key="rv_vendor")
    date_default = _parse_iso(fields.date)
    invoice_date = c2.date_input(
        f"{conf_icon(conf.get('date', 0))} Date",
        value=date_default, key="rv_date")

    c3, c4, c5, c6 = st.columns(4)
    subtotal = c3.number_input(
        f"{conf_icon(conf.get('subtotal', 0))} Subtotal",
        value=float(fields.subtotal) if fields.subtotal is not None else 0.0,
        min_value=0.0, step=0.01, format="%.2f", key="rv_subtotal")
    tax = c4.number_input(
        f"{conf_icon(conf.get('tax', 0))} Tax",
        value=float(fields.tax) if fields.tax is not None else 0.0,
        min_value=0.0, step=0.01, format="%.2f", key="rv_tax")
    total = c5.number_input(
        f"{conf_icon(conf.get('total', 0))} Total",
        value=float(fields.total) if fields.total is not None else 0.0,
        min_value=0.0, step=0.01, format="%.2f", key="rv_total")
    currency = c6.text_input(
        f"{conf_icon(conf.get('currency', 0))} Currency",
        value=fields.currency or "", max_chars=3, key="rv_currency")

    st.markdown("**Line items** — edit cells, add or delete rows:")
    if table.items:
        items_df = pd.DataFrame(
            [{"description": i.description, "quantity": i.quantity,
              "unit_price": i.unit_price, "line_total": i.line_total}
             for i in table.items])
    else:
        items_df = pd.DataFrame(
            columns=["description", "quantity", "unit_price", "line_total"])
    edited = st.data_editor(
        items_df, num_rows="dynamic", use_container_width=True, key="rv_items",
        column_config={
            "description": st.column_config.TextColumn("Description", required=True),
            "quantity": st.column_config.NumberColumn("Qty", min_value=0, step=1),
            "unit_price": st.column_config.NumberColumn("Unit price", min_value=0.0, format="%.2f"),
            "line_total": st.column_config.NumberColumn("Line total", min_value=0.0, format="%.2f"),
        })

    items_sum = float(edited["line_total"].dropna().sum()) if len(edited) else 0.0
    st.caption(f"Items sum: {items_sum:.2f}")

    for w in validate_amounts(subtotal or None, tax or None, total or None,
                              items_sum or None):
        st.warning(w)
    for f in table.flags:
        st.info(f"Extractor note: {f}")

    record = {
        "vendor": vendor.strip() or None,
        "date": invoice_date.isoformat() if invoice_date else None,
        "subtotal": subtotal or None,
        "tax": tax or None,
        "total": total or None,
        "currency": currency.strip().upper() or None,
        "items": edited.dropna(how="all").to_dict("records"),
        "source_file": source_file,
        "extraction_confidence": {k: round(v, 2) for k, v in conf.items()},
    }

    from app.database import repository as repo
    dup = repo.find_duplicate(record["vendor"], record["date"], record["total"])
    if dup and not st.session_state.get("rv_dup_ok"):
        st.warning(f"Possible duplicate: invoice #{dup['id']} has the same vendor, "
                   f"date, and total (saved {dup['created_at']}).")
        st.checkbox("Save anyway — this is a different invoice", key="rv_dup_ok")

    if st.button("💾 Save invoice", type="primary", key="rv_save",
                 disabled=bool(dup) and not st.session_state.get("rv_dup_ok")):
        new_id = repo.save_invoice(record)
        st.success(f"Saved as invoice #{new_id} ✔ — find it in Saved Invoices.")


def save_reviewed(record: dict) -> Path:
    REVIEWED_DIR.mkdir(parents=True, exist_ok=True)
    path = REVIEWED_DIR / f"invoice_{uuid.uuid4().hex[:12]}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path