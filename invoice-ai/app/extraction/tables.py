"""Line-item table extraction (Milestone 6).

Strategy (geometric + pattern, no ML):
1. Locate the table header row (>=2 column keywords: item/qty/price/...)
   — or, if absent, start after the vendor/meta block.
2. Locate the table end: the first totals-section row (subtotal/total/tax).
3. Parse rows in between into LineItem(description, quantity, unit_price,
   line_total), handling the layouts we've actually seen:
   - amounts on the same row as the name        (BFC:      "Garlic Wrap 1 220")
   - name split across two rows                 (Pinewood: "SMOKED CHICKEN" / "SANDWICH 339 339")
   - price-less modifier lines                  (Beefaroo: "Ranch", "Buffalo Sauce")
   - currency glued to price                    (SROIE:    "RM117.90")
4. Validate: qty x unit_price ~= line_total per row; sum of line totals
   ~= subtotal/total. Mismatches become FLAGS, never silent corrections —
   receipts round, discount, and lie.

Confidence philosophy: same as Milestone 5 — table extraction that works
on ~70-80% of receipts and honestly flags the rest beats one that
pretends. The review screen (Milestone 7) is the safety net.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.extraction.rules import (
    PAYMENT_NOISE, SUBTOTAL_KEYWORDS, TAX_KEYWORDS, TOTAL_KEYWORDS,
    Row, _amounts_in, _has_kw, build_rows,
)
from app.ocr.engine import OcrLine

HEADER_KEYWORDS = ["item", "description", "desc", "qty", "quantity",
                   "price", "rate", "amount", "amt", "t.price", "total"]
# rows that end the item section even without amounts
END_KEYWORDS = TOTAL_KEYWORDS + SUBTOTAL_KEYWORDS + TAX_KEYWORDS + [
    "rndoff", "rounding", "discount", "service charge",
]


@dataclass
class LineItem:
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None
    confidence: float = 0.5
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"description": self.description, "quantity": self.quantity,
                "unit_price": self.unit_price, "line_total": self.line_total,
                "confidence": round(self.confidence, 2), "flags": self.flags}


@dataclass
class TableResult:
    items: list[LineItem] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def to_dicts(self) -> list[dict]:
        return [i.to_dict() for i in self.items]


def _is_header(row: Row) -> bool:
    low = row.text.lower()
    hits = sum(1 for kw in HEADER_KEYWORDS if re.search(rf"(?<![a-z]){re.escape(kw)}", low))
    return hits >= 2 and not _amounts_in(row.text, decimals_only=True)


def _is_end(row: Row) -> bool:
    return _has_kw(row.text, END_KEYWORDS) is not None or _has_kw(row.text, PAYMENT_NOISE) is not None


def _strip_amounts(text: str) -> str:
    """Description = row text minus amount tokens and currency litter."""
    from app.extraction.rules import CURRENCY_GLUE_RE
    text = CURRENCY_GLUE_RE.sub(r"\1 ", text)
    text = re.sub(r"(?<![A-Za-z0-9.#])(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+\.\d{1,2})(?![0-9A-Za-z])", " ", text)
    text = re.sub(r"\b(RM|BDT|USD|INR|Rs\.?|SGD|MYR)\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", text).strip(" .:-|")


LEADING_CODE_RE = re.compile(r"^\s*0*\d{2,}\s+[A-Za-z]")


def _row_amounts(row: Row) -> list[float]:
    """Amounts for item parsing, minus leading product codes ('2973 ITEM...')."""
    amounts = _amounts_in(row.text)
    if amounts and LEADING_CODE_RE.match(row.text):
        # first numeric token is an item code, not money
        first = amounts[0]
        if first == int(first):
            amounts = amounts[1:]
    return amounts


def _classify_amounts(amounts: list[float]) -> tuple[float | None, float | None, float | None]:
    """(qty, unit_price, line_total) from a row's amount sequence."""
    if not amounts:
        return None, None, None
    if len(amounts) == 1:
        return None, None, amounts[0]
    if len(amounts) == 2:
        a, b = amounts
        # "qty price" where total is implied, or "price total" pairs:
        # a small leading integer with a larger partner reads as qty.
        if a == int(a) and a <= 20 and b > a:
            return a, b, None if b != a else b
        return None, a, b
    # 3+: assume trailing triplet [.., qty, price, total] when the first of
    # them looks like a small integer count; else [price, ..., total]
    a, b, c = amounts[-3], amounts[-2], amounts[-1]
    if a == int(a) and a <= 20 and a < b:
        return a, b, c
    return None, b, c


def extract_table(lines: list[OcrLine]) -> TableResult:
    rows = build_rows(lines)
    result = TableResult()
    if not rows:
        return result

    # -- table bounds --
    start_idx = None
    for i, row in enumerate(rows):
        if _is_header(row):
            start_idx = i + 1
            break
    if start_idx is None:
        # no header: begin after the top meta-block (first row with a
        # decimal amount that isn't an end-section row)
        for i, row in enumerate(rows):
            if _amounts_in(row.text, decimals_only=True) and not _is_end(row):
                start_idx = i
                break
    if start_idx is None:
        result.flags.append("no table region found")
        return result

    end_idx = len(rows)
    for i in range(start_idx, len(rows)):
        if _is_end(rows[i]):
            end_idx = i
            break

    # -- parse rows --
    table_rows = rows[start_idx:end_idx]
    pending_desc: str | None = None
    for pos, row in enumerate(table_rows):
        amounts = _row_amounts(row)
        desc = _strip_amounts(row.text)
        nxt = table_rows[pos + 1] if pos + 1 < len(table_rows) else None
        nxt_amounts = _row_amounts(nxt) if nxt is not None else []
        nxt_desc = _strip_amounts(nxt.text) if nxt is not None else ""

        if not amounts:
            if len(desc) < 2:
                continue
            # Look AHEAD to decide what a text-only row is: the name half
            # of a split item when the next row is amounts-only (Pinewood
            # "BOTTLE OF WATER" / "20 20"); a modifier of the previous
            # item when the next row carries its own name AND amounts
            # (Beefaroo "Buffalo Sauce" before "Onion Rings 3.09").
            if nxt is not None and nxt_amounts and not nxt_desc:
                pending_desc = ((pending_desc + " ") if pending_desc else "") + desc
            elif result.items and not pending_desc:
                result.items[-1].description += f" ({desc})"
            else:
                pending_desc = ((pending_desc + " ") if pending_desc else "") + desc
            continue

        qty, price, line_total = _classify_amounts(amounts)
        if pending_desc:
            desc = (pending_desc + " " + desc).strip()
            pending_desc = None

        # Split-row continuation (Pinewood "CHICKEN CHEESE T 309" then
        # "BURGER 309"): a short-name row repeating the previous item's
        # sole amount is the second half of the same item, not a new one.
        if (result.items and desc and len(desc.split()) <= 2
                and line_total is not None and qty is None
                and result.items[-1].line_total == line_total
                and result.items[-1].quantity is None):
            prev = result.items[-1]
            prev.description = f"{prev.description} {desc}".strip()
            prev.flags.append("merged split row")
            continue

        if not desc:
            if result.items and result.items[-1].line_total is None and \
                    result.items[-1].quantity is None:
                prev = result.items[-1]
                prev.quantity, prev.unit_price, prev.line_total = qty, price, line_total
                _validate_item(prev)
                continue
            desc = "(unlabeled item)"

        item = LineItem(description=desc, quantity=qty,
                        unit_price=price, line_total=line_total,
                        confidence=0.8 * row.confidence)
        _validate_item(item)
        result.items.append(item)

    # name-only trailing item (never got amounts)
    if pending_desc and len(pending_desc) >= 2:
        result.items.append(LineItem(description=pending_desc, confidence=0.3,
                                     flags=["no amounts found"]))

    _validate_table(result, rows, end_idx)
    return result


def _validate_item(item: LineItem) -> None:
    if None not in (item.quantity, item.unit_price, item.line_total):
        expected = item.quantity * item.unit_price
        if abs(expected - item.line_total) > max(0.02, item.line_total * 0.02):
            item.flags.append(f"qty x price = {expected:.2f} != line total {item.line_total:.2f}")
            item.confidence *= 0.6
        else:
            item.confidence = min(1.0, item.confidence + 0.15)
    if item.line_total is None and item.unit_price is not None:
        # single price with qty: derive
        if item.quantity is not None:
            item.line_total = round(item.quantity * item.unit_price, 2)
        else:
            item.line_total, item.unit_price = item.unit_price, None


def _validate_table(result: TableResult, rows: list[Row], end_idx: int) -> None:
    if not result.items:
        result.flags.append("no line items parsed")
        return
    totals = [i.line_total for i in result.items if i.line_total is not None]
    if not totals:
        return
    items_sum = sum(totals)
    # compare against the subtotal/total printed below the table
    printed = None
    for row in rows[end_idx:]:
        if _has_kw(row.text, SUBTOTAL_KEYWORDS + TOTAL_KEYWORDS) and \
                not _has_kw(row.text, PAYMENT_NOISE):
            amts = _amounts_in(row.text, decimals_only=False)
            if amts:
                printed = amts[-1]
                break
    if printed is not None and abs(items_sum - printed) > max(0.02, printed * 0.02):
        result.flags.append(
            f"items sum {items_sum:.2f} != printed subtotal/total {printed:.2f} — review"
        )
