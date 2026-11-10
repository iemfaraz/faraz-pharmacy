"""Database CRUD, search, duplicates, aggregates — on a throwaway DB."""
from datetime import date

import pytest

from app.database import repository as repo


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    repo.init_db(tmp_path / "test.db")
    yield


def _seed():
    a = repo.save_invoice({"vendor": "Pinewood Cafe+Kitchen", "date": "2026-07-30",
                           "subtotal": 937.0, "tax": 45.85, "total": 980.0,
                           "currency": "BDT",
                           "items": [{"description": "MILK SHAKE", "quantity": 1,
                                      "unit_price": 269.0, "line_total": 269.0}]})
    b = repo.save_invoice({"vendor": "Beef-a-Roo", "date": "2020-02-20",
                           "total": 13.39, "currency": "USD",
                           "items": [{"description": "Onion Rings", "line_total": 3.09}]})
    return a, b


def test_save_get_roundtrip():
    a, _ = _seed()
    inv = repo.get_invoice(a)
    assert inv["vendor"] == "Pinewood Cafe+Kitchen"
    assert inv["date"] == "2026-07-30"
    assert len(inv["items"]) == 1


def test_empty_item_rows_dropped():
    i = repo.save_invoice({"vendor": "X", "total": 1.0,
                           "items": [{"description": "", "line_total": None},
                                     {"description": "real", "line_total": 1.0}]})
    assert len(repo.get_invoice(i)["items"]) == 1


def test_search_text_reaches_items():
    _seed()
    assert len(repo.search_invoices(text="Onion")) == 1
    assert len(repo.search_invoices(text="MILK SHAKE")) == 1
    assert len(repo.search_invoices(vendor="beef")) == 1
    assert len(repo.search_invoices(min_total=100)) == 1
    assert len(repo.search_invoices(date_from=date(2025, 1, 1))) == 1


def test_duplicate_detection_case_insensitive():
    a, _ = _seed()
    dup = repo.find_duplicate("pinewood cafe+kitchen", "2026-07-30", 980.0)
    assert dup and dup["id"] == a
    assert repo.find_duplicate("Pinewood Cafe+Kitchen", "2026-07-30", 999.0) is None
    assert repo.find_duplicate(None, None, 980.0) is None


def test_update_replaces_items():
    a, _ = _seed()
    assert repo.update_invoice(a, {"vendor": "Pinewood", "date": "2026-07-30",
                                   "total": 980.0,
                                   "items": [{"description": "corrected",
                                              "line_total": 980.0}]})
    inv = repo.get_invoice(a)
    assert inv["items"][0]["description"] == "corrected"
    assert not repo.update_invoice(99999, {})


def test_delete_cascades():
    _, b = _seed()
    assert repo.delete_invoice(b)
    assert repo.get_invoice(b) is None
    assert len(repo.search_invoices(text="Onion")) == 0
    assert not repo.delete_invoice(b)


def test_aggregates_group_by_currency():
    _seed()
    repo.save_invoice({"vendor": "BFC", "date": "2026-07-19",
                       "total": 325.0, "currency": "BDT", "items": []})
    stats = {s["currency"]: s for s in repo.stats_by_currency()}
    assert stats["BDT"]["count"] == 2 and stats["BDT"]["total_spend"] == 1305.0
    assert stats["USD"]["total_spend"] == 13.39
    months = repo.monthly_totals()
    assert {"month": "2026-07", "currency": "BDT", "total": 1305.0} in months
    tv = repo.top_vendors(2)
    assert tv[0]["vendor"] == "Pinewood Cafe+Kitchen"


def test_empty_db_aggregates():
    assert repo.stats_by_currency() == []
    assert repo.monthly_totals() == []
    assert repo.top_vendors() == []
    assert repo.count_invoices() == 0
