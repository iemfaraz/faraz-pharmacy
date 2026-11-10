"""Rules-based field extraction (Milestone 5, layer 1).

Input:  list[OcrLine] from the OCR engine (text + confidence + bbox).
Output: ExtractedFields — vendor/date/amounts with per-field confidence.

Key design points:
- ROWS, not lines: PaddleOCR returns one line per detected text box, so
  "Total:" and "980.00" usually arrive as two separate lines that share a
  y-coordinate. Everything here operates on rows built by clustering
  lines vertically (using the bboxes we kept since Milestone 3).
- Per-field confidence: every value carries a 0-1 score combining OCR
  confidence with how the value was found (keyword match > fallback
  heuristic). Milestone 7's review UI color-codes on these.
- No LLM here. This layer must work offline; the LLM layer wraps it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

from dateutil import parser as dateparser

import config
from app.ocr.engine import OcrLine

# --- keyword sets (config-extendable) --------------------------------------

TOTAL_KEYWORDS = list(dict.fromkeys(
    [k.lower() for k in getattr(config, "TOTAL_KEYWORDS", [])]
    + ["total", "amount due", "balance due", "grand total", "payable", "net total"]
))
TAX_KEYWORDS = list(dict.fromkeys(
    [k.lower() for k in getattr(config, "TAX_KEYWORDS", [])]
    + ["tax", "vat", "gst", "sales tax", "service tax"]
))
SUBTOTAL_KEYWORDS = list(dict.fromkeys(
    [k.lower() for k in getattr(config, "SUBTOTAL_KEYWORDS", [])]
    + ["subtotal", "sub-total", "sub total", "total sales"]
))
# rows that contain amounts we must NOT mistake for the total
PAYMENT_NOISE = ["cash", "change", "tender", "paid", "received", "card", "balance carried"]
# a "total" keyword hit is void if the row is actually about quantity
QTY_NOISE = ["qty", "quantity", "items", "item count", "no. of"]

CURRENCY_PATTERNS = [
    (r"\bBDT\b|৳", "BDT"), (r"\bRM\b", "MYR"), (r"₹|\bRs\.?\b|\bINR\b", "INR"),
    (r"\bUSD\b|\$", "USD"), (r"€|\bEUR\b", "EUR"), (r"£|\bGBP\b", "GBP"),
    (r"₩|\bKRW\b", "KRW"), (r"\bSGD\b", "SGD"),
]

AMOUNT_RE = re.compile(r"(?<![A-Za-z0-9.#])(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+\.\d{1,2})(?![0-9A-Za-z])")
DATE_HINT_RE = re.compile(
    r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|\d{1,2}[-/ ]?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/ ,]?\s?\d{2,4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/ ]\d{1,2},?[-/ ]\d{2,4})",
    re.IGNORECASE,
)


@dataclass
class Row:
    """Horizontally merged OCR lines sharing a baseline."""
    text: str
    y: float
    confidence: float
    parts: list[OcrLine] = field(default_factory=list)


@dataclass
class ExtractedFields:
    vendor: str | None = None
    date: str | None = None          # ISO YYYY-MM-DD
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    currency: str | None = None
    confidence: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor, "date": self.date, "subtotal": self.subtotal,
            "tax": self.tax, "total": self.total, "currency": self.currency,
            "confidence": {k: round(v, 2) for k, v in self.confidence.items()},
        }


# --- row building ----------------------------------------------------------

def build_rows(lines: list[OcrLine]) -> list[Row]:
    if not lines:
        return []
    heights = [max(p[1] for p in l.bbox) - min(p[1] for p in l.bbox) for l in lines]
    tol = max(6.0, median(heights) * 0.6)

    rows: list[Row] = []
    for line in sorted(lines, key=lambda l: l.top):
        placed = False
        for row in rows:
            if abs(line.top - row.y) <= tol:
                row.parts.append(line)
                placed = True
                break
        if not placed:
            rows.append(Row(text="", y=line.top, confidence=0.0, parts=[line]))

    for row in rows:
        row.parts.sort(key=lambda l: l.left)
        row.text = " ".join(p.text for p in row.parts)
        row.confidence = sum(p.confidence for p in row.parts) / len(row.parts)
    rows.sort(key=lambda r: r.y)
    return rows


# --- helpers ---------------------------------------------------------------

CURRENCY_GLUE_RE = re.compile(r"(BDT|USD|INR|SGD|EUR|GBP|KRW|MYR|RM|Rs\.?|\$|€|£|₹|₩|৳)(?=\d)", re.IGNORECASE)


def _unglue(text: str) -> str:
    """OCR often fuses currency and amount: 'BDT980.00' -> 'BDT 980.00'."""
    return CURRENCY_GLUE_RE.sub(r"\1 ", text)


def _amounts_in(text: str, decimals_only: bool = False) -> list[float]:
    text = _unglue(text)
    vals = []
    for m in AMOUNT_RE.finditer(text):
        raw = m.group(1)
        if decimals_only and "." not in raw:
            continue
        try:
            vals.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    return vals


_OCR_CONFUSIONS = str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b"})


def _has_kw(text: str, keywords: list[str]) -> str | None:
    low = text.lower()
    # second view with common OCR digit-for-letter confusions repaired,
    # so 'To Go Tota1' still matches 'total'
    repaired = low.translate(_OCR_CONFUSIONS)
    for kw in keywords:
        # word-boundary match: "total" must NOT match inside "subtotal"
        pat = rf"(?<![a-z]){re.escape(kw)}"
        if re.search(pat, low) or re.search(pat, repaired):
            return kw
    return None


def _looks_like_address_or_meta(text: str) -> bool:
    low = text.lower()
    if DATE_HINT_RE.search(text):
        return True
    meta = ["tel", "phone", "fax", "gst", "vat", "invoice", "receipt", "no.", "no:",
            "www.", ".com", "@", "order", "table", "cashier", "reg", "bin", "musak",
            "road", "street", "jalan", "floor", "avenue", "unit",
            "#", "token", "take out", "take-out", "takeout", "takeaway",
            "dine in", "dinein", "delivery", "self"]
    if any(m in low for m in meta):
        return True
    digits = sum(c.isdigit() for c in text)
    return digits > len(text) * 0.3


def _letter_ratio(text: str) -> float:
    """Letters vs letters+digits — symbols and reg numbers don't dilute."""
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    return letters / max(1, letters + digits)


# --- field finders ---------------------------------------------------------

def find_vendor(rows: list[Row]) -> tuple[str | None, float]:
    """Topmost alpha-heavy row that isn't address/meta noise."""
    for row in rows[:6]:
        text = row.text.strip()
        if len(text) < 3 or _looks_like_address_or_meta(text):
            continue
        if _letter_ratio(text) < 0.5:
            continue
        # position bonus: row 0 most likely the header/brand
        position_factor = 1.0 if row is rows[0] else 0.85
        return text, row.confidence * position_factor
    return None, 0.0


def find_date(rows: list[Row]) -> tuple[str | None, float]:
    candidates: list[tuple[str, float, bool]] = []  # (raw, conf, near_date_kw)
    for row in rows:
        for m in DATE_HINT_RE.finditer(row.text):
            near_kw = "date" in row.text.lower()
            candidates.append((m.group(0), row.confidence, near_kw))
    # prefer candidates on a row containing "date", then earlier rows
    candidates.sort(key=lambda c: (not c[2],))
    for raw, conf, near_kw in candidates:
        parsed = _parse_date(raw)
        if parsed:
            base = 0.9 if near_kw else 0.7
            return parsed, base * conf
    return None, 0.0


def _parse_date(raw: str) -> str | None:
    """Parse with dayfirst preference; fall back to monthfirst.

    Also retries with the last two digits dropped: glued OCR text like
    '29-Mar-2301' is usually a 2-digit year fused with the time ('23' + '01:07').
    """
    candidates = [raw]
    if re.search(r"\d{4}$", raw):
        candidates.append(raw[:-2])
    for cand in candidates:
        for dayfirst in (True, False):
            try:
                dt = dateparser.parse(cand, dayfirst=dayfirst, fuzzy=False)
                if dt and 2000 <= dt.year <= 2100:
                    return dt.strftime("%Y-%m-%d")
            except (ValueError, OverflowError):
                continue
    return None


def _find_amount(rows: list[Row], keywords: list[str],
                 exclude_noise: bool = True,
                 extra_noise: list[str] | None = None) -> tuple[float | None, float, int]:
    """Best amount on a row matching keywords. Returns (value, conf, row_idx)."""
    best: tuple[float | None, float, int] = (None, 0.0, -1)
    for idx, row in enumerate(rows):
        if not _has_kw(row.text, keywords):
            continue
        if exclude_noise and _has_kw(row.text, PAYMENT_NOISE):
            continue
        if extra_noise and _has_kw(row.text, extra_noise):
            continue
        if _has_kw(row.text, QTY_NOISE) and len(_amounts_in(row.text)) <= 1:
            continue
        amounts = _amounts_in(row.text)
        if not amounts:
            continue
        value = amounts[-1]  # rightmost amount on the row is the money column
        conf = 0.9 * row.confidence
        # later rows win ties: totals live at the bottom, and e.g. a
        # "Total Sales" row above may be superseded by rounded "Total"
        if conf >= best[1] - 0.05:
            best = (value, conf, idx)
    return best


def find_totals(rows: list[Row]) -> dict[str, tuple[float | None, float]]:
    total, t_conf, t_idx = _find_amount(rows, TOTAL_KEYWORDS)
    sub, s_conf, s_idx = _find_amount(rows, SUBTOTAL_KEYWORDS)

    if sub is not None and s_idx == t_idx and t_idx >= 0:
        # One row matched both keyword sets (e.g. "Total Sales (Inclusive GST)").
        row_text = rows[t_idx].text.lower()
        if any(kw in row_text for kw in SUBTOTAL_KEYWORDS):
            # The specific subtotal phrase is present: treat the row as the
            # subtotal, and look for a distinct total elsewhere — a more
            # specific keyword row first, else the largest later amount
            # (e.g. a "Rounding 169.80" final figure).
            specific = [k for k in TOTAL_KEYWORDS if k != "total"]
            new_total, new_conf, new_idx = _find_amount(rows, specific)
            if new_total is not None and new_idx != t_idx:
                total, t_conf = new_total, new_conf
            else:
                total, t_conf = None, 0.0  # defer to fallback with floor=sub
        else:
            sub, s_conf = None, 0.0

    tax, x_conf, _ = _find_amount(rows, TAX_KEYWORDS, extra_noise=TOTAL_KEYWORDS
                                  + SUBTOTAL_KEYWORDS + ["inclusive", "incl."])

    # fallback total: largest amount on any non-noise row
    def _fallback_total(floor: float | None) -> tuple[float | None, float]:
        best_val, best_conf = None, 0.0
        for row in rows:
            if _has_kw(row.text, PAYMENT_NOISE):
                continue
            for v in _amounts_in(row.text, decimals_only=True):
                if floor is not None and v < floor:
                    continue
                if best_val is None or v > best_val:
                    best_val, best_conf = v, 0.4 * row.confidence
        return best_val, best_conf

    if total is None:
        total, t_conf = _fallback_total(sub)
        if total is None and sub is not None:
            total, t_conf = sub, s_conf * 0.8  # nothing larger exists; subtotal is it

    # Sanity: a total below the subtotal means the keyword row grabbed a
    # wrong number (split rows, discount amounts). Re-derive from the
    # largest decimal amount at or above the subtotal.
    if total is not None and sub is not None and total < sub - 0.01:
        rescued, r_conf = _fallback_total(sub)
        if rescued is not None:
            total, t_conf = rescued, min(r_conf + 0.2, 0.7)
    return {"total": (total, t_conf), "subtotal": (sub, s_conf), "tax": (tax, x_conf)}


def find_currency(rows: list[Row]) -> tuple[str | None, float]:
    votes: dict[str, int] = {}
    for row in rows:
        text = _unglue(row.text)
        for pattern, code in CURRENCY_PATTERNS:
            if re.search(pattern, text):
                votes[code] = votes.get(code, 0) + 1
    if not votes:
        return None, 0.0
    code = max(votes, key=votes.get)
    return code, min(0.9, 0.5 + 0.1 * votes[code])


# --- entry point -----------------------------------------------------------

def extract_fields(lines: list[OcrLine]) -> ExtractedFields:
    rows = build_rows(lines)
    out = ExtractedFields()
    if not rows:
        return out

    out.vendor, v_conf = find_vendor(rows)
    out.date, d_conf = find_date(rows)
    totals = find_totals(rows)
    out.total, t_conf = totals["total"]
    out.subtotal, s_conf = totals["subtotal"]
    out.tax, x_conf = totals["tax"]
    out.currency, c_conf = find_currency(rows)

    # consistency bonus: if subtotal + tax ≈ total, boost all three
    if None not in (out.subtotal, out.tax, out.total):
        if abs((out.subtotal + out.tax) - out.total) <= max(0.02, out.total * 0.02):
            t_conf = min(1.0, t_conf + 0.1)
            s_conf = min(1.0, s_conf + 0.1)
            x_conf = min(1.0, x_conf + 0.1)

    out.confidence = {"vendor": v_conf, "date": d_conf, "subtotal": s_conf,
                      "tax": x_conf, "total": t_conf, "currency": c_conf}
    return out