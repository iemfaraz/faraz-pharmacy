"""Repository: every database operation the app needs (Milestone 8).

The UI never touches SQLAlchemy sessions or models directly — it calls
these functions and receives plain dicts. That boundary is what lets
Milestone 10 export the same data and lets tests run against a
throwaway database.

save_invoice() accepts exactly the record shape the review screen
produces, so the screen's save handler is one call.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

import config
from app.database.models import Base, Invoice, InvoiceItem

_engine = None
_SessionLocal = None


def init_db(db_path=None):
    """Create engine + tables. Idempotent; call once at startup."""
    global _engine, _SessionLocal
    path = db_path or config.DB_PATH
    _engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


@contextmanager
def _session() -> Session:
    if _SessionLocal is None:
        init_db()
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _parse_date(d) -> date | None:
    if d is None or isinstance(d, date):
        return d
    try:
        return datetime.strptime(str(d), "%Y-%m-%d").date()
    except ValueError:
        return None


# --- CRUD -------------------------------------------------------------------

def save_invoice(record: dict) -> int:
    """Insert a reviewed-invoice record; returns the new id."""
    with _session() as s:
        inv = Invoice(
            vendor=record.get("vendor"),
            invoice_date=_parse_date(record.get("date")),
            subtotal=record.get("subtotal"),
            tax=record.get("tax"),
            total=record.get("total"),
            currency=record.get("currency"),
            source_file=record.get("source_file"),
            extraction_confidence=json.dumps(record.get("extraction_confidence") or {}),
        )
        for it in record.get("items") or []:
            desc = (it.get("description") or "").strip()
            if not desc:
                continue
            inv.items.append(InvoiceItem(
                description=desc,
                quantity=it.get("quantity"),
                unit_price=it.get("unit_price"),
                line_total=it.get("line_total"),
            ))
        s.add(inv)
        s.flush()
        return inv.id


def get_invoice(invoice_id: int) -> dict | None:
    with _session() as s:
        inv = s.get(Invoice, invoice_id)
        return inv.to_dict() if inv else None


def update_invoice(invoice_id: int, record: dict) -> bool:
    """Replace fields and items of an existing invoice."""
    with _session() as s:
        inv = s.get(Invoice, invoice_id)
        if inv is None:
            return False
        inv.vendor = record.get("vendor")
        inv.invoice_date = _parse_date(record.get("date"))
        inv.subtotal = record.get("subtotal")
        inv.tax = record.get("tax")
        inv.total = record.get("total")
        inv.currency = record.get("currency")
        inv.items.clear()
        for it in record.get("items") or []:
            desc = (it.get("description") or "").strip()
            if not desc:
                continue
            inv.items.append(InvoiceItem(
                description=desc, quantity=it.get("quantity"),
                unit_price=it.get("unit_price"), line_total=it.get("line_total")))
        return True


def delete_invoice(invoice_id: int) -> bool:
    with _session() as s:
        inv = s.get(Invoice, invoice_id)
        if inv is None:
            return False
        s.delete(inv)
        return True


# --- search & duplicates ----------------------------------------------------

def search_invoices(text: str | None = None,
                    vendor: str | None = None,
                    date_from: date | None = None,
                    date_to: date | None = None,
                    min_total: float | None = None,
                    max_total: float | None = None,
                    limit: int = 200) -> list[dict]:
    """Filtered, newest-first invoice list. All filters optional and ANDed."""
    with _session() as s:
        q = select(Invoice)
        if text:
            like = f"%{text.strip()}%"
            item_match = select(InvoiceItem.invoice_id).where(
                InvoiceItem.description.ilike(like))
            q = q.where(or_(Invoice.vendor.ilike(like),
                            Invoice.source_file.ilike(like),
                            Invoice.id.in_(item_match)))
        if vendor:
            q = q.where(Invoice.vendor.ilike(f"%{vendor.strip()}%"))
        if date_from:
            q = q.where(Invoice.invoice_date >= date_from)
        if date_to:
            q = q.where(Invoice.invoice_date <= date_to)
        if min_total is not None:
            q = q.where(Invoice.total >= min_total)
        if max_total is not None:
            q = q.where(Invoice.total <= max_total)
        q = q.order_by(Invoice.created_at.desc()).limit(limit)
        return [inv.to_dict() for inv in s.scalars(q)]


def find_duplicate(vendor: str | None, invoice_date, total: float | None) -> dict | None:
    """Same vendor + date + total already stored? Warn-level check."""
    if not vendor or total is None:
        return None
    d = _parse_date(invoice_date)
    with _session() as s:
        q = select(Invoice).where(
            func.lower(Invoice.vendor) == vendor.strip().lower(),
            Invoice.total == total,
        )
        if d is not None:
            q = q.where(Invoice.invoice_date == d)
        inv = s.scalars(q.limit(1)).first()
        return inv.to_dict() if inv else None


def count_invoices() -> int:
    with _session() as s:
        return s.scalar(select(func.count(Invoice.id))) or 0


# --- dashboard aggregates (Milestone 9) -------------------------------------
# All grouped by currency: summing 980 BDT with 13.39 USD would produce a
# meaningless number, so every money aggregate carries its currency.

def _cur(c):
    return c if c else "?"


def stats_by_currency(date_from: date | None = None,
                      date_to: date | None = None) -> list[dict]:
    """[{currency, count, total_spend, avg_invoice}] filtered by date."""
    with _session() as s:
        q = (select(Invoice.currency, func.count(Invoice.id),
                    func.sum(Invoice.total), func.avg(Invoice.total))
             .group_by(Invoice.currency))
        if date_from:
            q = q.where(Invoice.invoice_date >= date_from)
        if date_to:
            q = q.where(Invoice.invoice_date <= date_to)
        return [{"currency": _cur(c), "count": n or 0,
                 "total_spend": round(t or 0, 2), "avg_invoice": round(a or 0, 2)}
                for c, n, t, a in s.execute(q)]


def monthly_totals(date_from: date | None = None,
                   date_to: date | None = None) -> list[dict]:
    """[{month: 'YYYY-MM', currency, total}] for the spend-over-time chart."""
    with _session() as s:
        month = func.strftime("%Y-%m", Invoice.invoice_date)
        q = (select(month, Invoice.currency, func.sum(Invoice.total))
             .where(Invoice.invoice_date.is_not(None))
             .group_by(month, Invoice.currency)
             .order_by(month))
        if date_from:
            q = q.where(Invoice.invoice_date >= date_from)
        if date_to:
            q = q.where(Invoice.invoice_date <= date_to)
        return [{"month": m, "currency": _cur(c), "total": round(t or 0, 2)}
                for m, c, t in s.execute(q)]


def top_vendors(n: int = 5, date_from: date | None = None,
                date_to: date | None = None) -> list[dict]:
    """[{vendor, currency, total, count}] ranked by spend within currency."""
    with _session() as s:
        q = (select(Invoice.vendor, Invoice.currency,
                    func.sum(Invoice.total), func.count(Invoice.id))
             .where(Invoice.vendor.is_not(None))
             .group_by(Invoice.vendor, Invoice.currency)
             .order_by(func.sum(Invoice.total).desc())
             .limit(n))
        if date_from:
            q = q.where(Invoice.invoice_date >= date_from)
        if date_to:
            q = q.where(Invoice.invoice_date <= date_to)
        return [{"vendor": v, "currency": _cur(c),
                 "total": round(t or 0, 2), "count": k}
                for v, c, t, k in s.execute(q)]
