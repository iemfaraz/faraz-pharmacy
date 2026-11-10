"""Export (Milestone 10): Excel, CSV, JSON from repository records.

All three exporters take the SAME input — the list of invoice dicts the
repository returns — so whatever filters produced the list are what get
exported. No exporter touches the database directly.

Formats:
- Excel: two sheets ("Invoices", "Line Items") linked by invoice ID,
  bold headers, frozen header row, sensible column widths.
- CSV: flat invoices file; items go in a second CSV since CSV can't nest.
- JSON: nested (each invoice carries its items) — the machine-friendly one.

Everything returns bytes, ready for st.download_button or a file write.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime


def _flat_rows(invoices: list[dict]) -> list[dict]:
    return [{
        "ID": inv["id"], "Vendor": inv["vendor"], "Date": inv["date"],
        "Subtotal": inv["subtotal"], "Tax": inv["tax"], "Total": inv["total"],
        "Currency": inv["currency"], "Items": len(inv["items"]),
        "Source file": inv["source_file"], "Saved at": inv["created_at"],
    } for inv in invoices]


def _item_rows(invoices: list[dict]) -> list[dict]:
    rows = []
    for inv in invoices:
        for it in inv["items"]:
            rows.append({
                "Invoice ID": inv["id"], "Vendor": inv["vendor"],
                "Description": it["description"], "Quantity": it["quantity"],
                "Unit price": it["unit_price"], "Line total": it["line_total"],
            })
    return rows


# --- Excel ------------------------------------------------------------------

def to_excel(invoices: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    def write_sheet(ws, rows: list[dict], empty_note: str):
        if not rows:
            ws["A1"] = empty_note
            return
        headers = list(rows[0].keys())
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append([row[h] for h in headers])
        ws.freeze_panes = "A2"
        for idx, header in enumerate(headers, start=1):
            width = max(len(str(header)),
                        *(len(str(r[header])) for r in rows)) + 2
            ws.column_dimensions[get_column_letter(idx)].width = min(width, 40)

    ws_inv = wb.active
    ws_inv.title = "Invoices"
    write_sheet(ws_inv, _flat_rows(invoices), "No invoices in this export.")
    ws_items = wb.create_sheet("Line Items")
    write_sheet(ws_items, _item_rows(invoices), "No line items in this export.")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- CSV --------------------------------------------------------------------

def _rows_to_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    # utf-8-sig so Excel opens non-ASCII vendor names correctly
    return buf.getvalue().encode("utf-8-sig")


def to_csv_invoices(invoices: list[dict]) -> bytes:
    return _rows_to_csv(_flat_rows(invoices))


def to_csv_items(invoices: list[dict]) -> bytes:
    return _rows_to_csv(_item_rows(invoices))


# --- JSON -------------------------------------------------------------------

def to_json(invoices: list[dict]) -> bytes:
    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "invoice_count": len(invoices),
        "invoices": invoices,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def export_filename(fmt: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"invoices_{stamp}.{fmt}"
