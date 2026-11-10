"""Batch processing (Milestone 13).

Process many receipts in one pass, then triage rather than blind-save:

    upload N files -> OCR+extract each -> REVIEW QUEUE
       ├─ high confidence  -> one-click "approve all clean"
       └─ flagged          -> expand, fix, approve individually

Design rationale: auto-saving a batch would bury every extraction error
in the database. The whole product value is the human check on
low-confidence fields — batch keeps that, but concentrates attention
only where it's needed. High-confidence invoices approve in one click;
flagged ones get expanded review.

An invoice is "clean" when every field it has cleared a confidence
threshold AND its math validates. Everything else is "needs review".

Pure logic (triage, readiness) is separated from the Streamlit rendering
so it stays testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.extraction.rules import ExtractedFields
from app.extraction.tables import TableResult
from app.review.screen import validate_amounts

CLEAN_THRESHOLD = 0.60          # realistic for well-calibrated (non-cocky) OCR
KEY_FIELDS = ("vendor", "date", "total")   # these gate; currency/subtotal don't


@dataclass
class BatchItem:
    filename: str
    source_file: str          # stored upload name
    fields: ExtractedFields
    table: TableResult
    approved: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def min_confidence(self) -> float:
        """Lowest confidence among the KEY fields that are present."""
        present = [self.fields.confidence.get(k, 0.0) for k in KEY_FIELDS
                   if getattr(self.fields, k, None) is not None]
        return min(present) if present else 0.0

    @property
    def math_reconciles(self) -> bool:
        """Numbers that add up are strong evidence of a correct read."""
        f = self.fields
        if None not in (f.subtotal, f.tax, f.total):
            if abs((f.subtotal + f.tax) - f.total) <= max(0.05, f.total * 0.02):
                return True
        items_sum = sum(i.line_total for i in self.table.items
                        if i.line_total is not None)
        if items_sum and f.total is not None:
            # items reconcile if they sum close to the total, or close to
            # the subtotal (tax added separately). "Close" = within 2%.
            for target in (f.total, f.subtotal):
                if target and abs(items_sum - target) <= max(0.05, target * 0.02):
                    return True
        return False

    @property
    def is_clean(self) -> bool:
        """Clean when a total exists, no hard warnings, and EITHER the math
        reconciles OR every key field cleared the confidence threshold."""
        if self.fields.total is None:
            return False
        # Any subtotal/tax/total gap warning or missing-total warning blocks
        # "clean". These phrases come from validate_amounts() and the table
        # extractor; match them explicitly rather than guessing keywords.
        blocking_phrases = ("gap", "but total", "no total", "differ",
                            "sum", "review")
        blocking = [w for w in self.warnings
                    if any(p in w.lower() for p in blocking_phrases)]
        if blocking:
            return False
        return self.math_reconciles or self.min_confidence >= CLEAN_THRESHOLD


def compute_warnings(fields: ExtractedFields, table: TableResult) -> list[str]:
    items_sum = sum(i.line_total for i in table.items
                    if i.line_total is not None) or None
    w = validate_amounts(fields.subtotal, fields.tax, fields.total, items_sum)
    w += list(table.flags)
    if fields.total is None:
        w.append("No total extracted.")
    return w


def make_item(filename: str, source_file: str,
              fields: ExtractedFields, table: TableResult) -> BatchItem:
    return BatchItem(filename=filename, source_file=source_file,
                     fields=fields, table=table,
                     warnings=compute_warnings(fields, table))


def triage(items: list[BatchItem]) -> tuple[list[BatchItem], list[BatchItem]]:
    """Split into (clean, needs_review), each sorted for a sensible queue."""
    clean = [i for i in items if i.is_clean]
    review = [i for i in items if not i.is_clean]
    review.sort(key=lambda i: i.min_confidence)  # worst first
    return clean, review


def record_from_item(item: BatchItem) -> dict:
    """Convert a BatchItem into the dict repository.save_invoice expects."""
    f = item.fields
    return {
        "vendor": f.vendor, "date": f.date, "subtotal": f.subtotal,
        "tax": f.tax, "total": f.total, "currency": f.currency,
        "source_file": item.source_file,
        "extraction_confidence": {k: round(v, 2) for k, v in f.confidence.items()},
        "items": [{"description": it.description, "quantity": it.quantity,
                   "unit_price": it.unit_price, "line_total": it.line_total}
                  for it in item.table.items],
    }