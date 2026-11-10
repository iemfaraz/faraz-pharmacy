"""Batch triage: clean detection, review routing, record conversion."""
import pytest

from app.batch import make_item, record_from_item, triage
from app.extraction.rules import ExtractedFields
from app.extraction.tables import LineItem, TableResult
from app.database import repository as repo


def _fields(total=100.0, sub=90.0, tax=10.0, conf=None):
    f = ExtractedFields(vendor="V", date="2026-01-01", subtotal=sub, tax=tax,
                        total=total, currency="USD")
    f.confidence = conf or {"vendor": 0.9, "date": 0.9, "subtotal": 0.9,
                            "tax": 0.9, "total": 0.9, "currency": 0.9}
    return f


def _table(rows=None):
    t = TableResult()
    for d, lt in (rows or []):
        t.items.append(LineItem(description=d, line_total=lt))
    return t


def test_clean_invoice_is_clean():
    it = make_item("a.jpg", "a.jpg", _fields(), _table([("X", 90.0)]))
    assert it.is_clean and not it.warnings


def test_low_confidence_needs_review():
    # low confidence AND broken math (no reconciliation path)
    it = make_item("b.jpg", "b.jpg",
                   _fields(total=999.0, sub=90.0, tax=10.0,
                           conf={"vendor": 0.4, "date": 0.4, "total": 0.5}), _table())
    assert not it.is_clean


def test_math_mismatch_needs_review():
    # subtotal+tax (100) != total (200): gap warning blocks "clean"
    it = make_item("c.jpg", "c.jpg", _fields(total=200.0, sub=90.0, tax=10.0),
                   _table())
    assert not it.is_clean
    assert any("gap" in w.lower() or "total" in w.lower() for w in it.warnings)


def test_reconciling_receipt_is_clean_despite_modest_confidence():
    # real-world: honest-but-modest confidence (0.65 date) still counts as
    # clean when the numbers reconcile — this is the recalibration that keeps
    # correct extractions out of the review queue
    # self-consistent: items sum to subtotal, subtotal+tax = total
    f = _fields(total=13.39, sub=12.37, tax=1.02,
                conf={"vendor": 0.94, "date": 0.65, "total": 0.69})
    it = make_item("r.jpg", "r.jpg", f, _table([("A", 6.29), ("B", 6.08)]))
    assert it.is_clean  # 6.29+6.08=12.37 subtotal, +1.02 tax = 13.39


def test_missing_total_needs_review():
    it = make_item("d.jpg", "d.jpg",
                   _fields(total=None, conf={"vendor": 0.9}), _table())
    assert not it.is_clean


def test_triage_sorts_worst_first():
    # review items have a gap warning (sub+tax != total) so they can't
    # reconcile to clean; sorted worst-confidence first
    items = [
        make_item("a.jpg", "a.jpg", _fields(), _table([("X", 90.0)])),
        make_item("b.jpg", "b.jpg",
                  _fields(total=555.0, sub=90.0, tax=10.0,
                          conf={"vendor": 0.3, "date": 0.3, "total": 0.3}), _table()),
        make_item("c.jpg", "c.jpg",
                  _fields(total=555.0, sub=90.0, tax=10.0,
                          conf={"vendor": 0.6, "date": 0.6, "total": 0.6}), _table()),
    ]
    clean, review = triage(items)
    assert len(clean) == 1 and len(review) == 2
    assert review[0].min_confidence <= review[1].min_confidence


def test_record_saves_via_repository(tmp_path):
    repo.init_db(tmp_path / "b.db")
    it = make_item("a.jpg", "a.jpg", _fields(), _table([("X", 90.0)]))
    new_id = repo.save_invoice(record_from_item(it))
    assert repo.get_invoice(new_id)["total"] == 100.0