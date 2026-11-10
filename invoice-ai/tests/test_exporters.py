"""Export round-trips: write each format, read it back, verify."""
import csv
import io
import json

import pytest
from openpyxl import load_workbook

from app.database import repository as repo
from app.export import exporters as ex


@pytest.fixture(autouse=True)
def seeded_db(tmp_path):
    repo.init_db(tmp_path / "test.db")
    repo.save_invoice({"vendor": "Pinewood Cafe+Kitchen", "date": "2026-07-30",
                       "subtotal": 937.0, "tax": 45.85, "total": 980.0,
                       "currency": "BDT", "source_file": "p.jpg",
                       "items": [{"description": "MILK SHAKE", "quantity": 1,
                                  "unit_price": 269.0, "line_total": 269.0}]})
    repo.save_invoice({"vendor": "Beef-a-Roo", "date": "2020-02-20",
                       "total": 13.39, "currency": "USD", "source_file": "b.jpg",
                       "items": [{"description": "5pc Chicken Strip",
                                  "line_total": 6.29}]})
    yield


def test_excel_roundtrip():
    wb = load_workbook(io.BytesIO(ex.to_excel(repo.search_invoices())))
    assert wb.sheetnames == ["Invoices", "Line Items"]
    rows = list(wb["Invoices"].iter_rows(min_row=2, values_only=True))
    assert len(rows) == 2
    assert wb["Invoices"][1][0].font.bold
    assert wb["Invoices"].freeze_panes == "A2"
    items = list(wb["Line Items"].iter_rows(min_row=2, values_only=True))
    assert len(items) == 2


def test_csv_roundtrip():
    text = ex.to_csv_invoices(repo.search_invoices()).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 2
    itext = ex.to_csv_items(repo.search_invoices()).decode("utf-8-sig")
    irows = list(csv.DictReader(io.StringIO(itext)))
    assert len(irows) == 2
    strip = next(r for r in irows if "Strip" in r["Description"])
    assert strip["Quantity"] == ""  # None survives as blank


def test_json_roundtrip():
    payload = json.loads(ex.to_json(repo.search_invoices()).decode())
    assert payload["invoice_count"] == 2
    pw = next(i for i in payload["invoices"]
              if i["vendor"] == "Pinewood Cafe+Kitchen")
    assert pw["items"][0]["description"] == "MILK SHAKE"


def test_export_respects_filters():
    filtered = repo.search_invoices(vendor="beef")
    wb = load_workbook(io.BytesIO(ex.to_excel(filtered)))
    rows = list(wb["Invoices"].iter_rows(min_row=2, values_only=True))
    assert len(rows) == 1 and rows[0][1] == "Beef-a-Roo"


def test_empty_export():
    wb = load_workbook(io.BytesIO(ex.to_excel([])))
    assert wb["Invoices"]["A1"].value == "No invoices in this export."
    assert json.loads(ex.to_json([]).decode())["invoice_count"] == 0
