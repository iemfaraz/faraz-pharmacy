"""Database models (Milestone 8).

Two tables, mirroring the reviewed-invoice record:

    invoices        1 --- * invoice_items

Design notes:
- Amounts are stored as REAL (float). For an accounting product you'd
  use integer cents; for OCR-derived data reviewed by a human, float
  round-tripping is acceptable and keeps the whole pipeline consistent.
- source_file keeps the stored upload name so the original image can
  always be re-opened next to its data.
- extraction_confidence is stored as JSON text — audit trail of what the
  machine believed before the human reviewed it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor: Mapped[str | None] = mapped_column(String(200), index=True)
    invoice_date: Mapped[object | None] = mapped_column(Date, index=True)
    subtotal: Mapped[float | None] = mapped_column(Float)
    tax: Mapped[float | None] = mapped_column(Float)
    total: Mapped[float | None] = mapped_column(Float, index=True)
    currency: Mapped[str | None] = mapped_column(String(3))
    source_file: Mapped[str | None] = mapped_column(String(300))
    extraction_confidence: Mapped[str | None] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now)

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vendor": self.vendor,
            "date": self.invoice_date.isoformat() if self.invoice_date else None,
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "currency": self.currency,
            "source_file": self.source_file,
            "created_at": self.created_at.isoformat(timespec="seconds") if self.created_at else None,
            "items": [i.to_dict() for i in self.items],
        }


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[float | None] = mapped_column(Float)
    unit_price: Mapped[float | None] = mapped_column(Float)
    line_total: Mapped[float | None] = mapped_column(Float)

    invoice: Mapped[Invoice] = relationship(back_populates="items")

    def to_dict(self) -> dict:
        return {"description": self.description, "quantity": self.quantity,
                "unit_price": self.unit_price, "line_total": self.line_total}
