"""LLM field extraction (Milestone 5, layer 2).

Sends raw OCR text to Claude and asks for strict JSON. The result is
VALIDATED (parse, types, sanity) and then MERGED with the rules-layer
output — the LLM fills gaps and arbitrates low-confidence fields; it
never runs alone, and any failure (no key, network, bad JSON) degrades
silently to the rules result.

Why an LLM at all: the rules baseline plateaued at ~68% on damaged
scans. The remaining misses are semantic — recognizing that 'CROSS
CHANNEL NEIWORK SDN.BHD' is a vendor despite OCR damage, or which of
several numbers is the real total. That's language understanding, not
pattern matching.

Requires: ANTHROPIC_API_KEY in the environment (or a .env file loaded
by the caller). Never hardcode keys; never commit them.
"""

from __future__ import annotations

import json
import os
import re

import requests

import config
from app.extraction.rules import ExtractedFields
from app.ocr.engine import OcrLine, lines_to_text

API_URL = "https://api.anthropic.com/v1/messages"
TIMEOUT_S = 30

PROMPT = """You are an invoice/receipt field extractor. Below is raw OCR text \
from a receipt. OCR errors are common (e.g. 'Involce' for 'Invoice', '0' for 'O', \
merged words) — use context to correct them.

Return ONLY a JSON object, no markdown, no explanation, with exactly these keys:
{{"vendor": string or null, "date": "YYYY-MM-DD" or null, "subtotal": number or null, \
"tax": number or null, "total": number or null, "currency": ISO code string or null}}

Rules:
- vendor is the business name as printed (correct obvious OCR damage)
- total is the final amount payable (not cash tendered, not change)
- if tax is included in the total (e.g. "inclusive of VAT"), still report the tax \
amount if printed, and leave subtotal null unless separately printed
- use null when a value is genuinely absent; do not guess amounts

OCR TEXT:
{ocr_text}"""


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call_api(ocr_text: str) -> dict | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": getattr(config, "LLM_MODEL", "claude-sonnet-4-6"),
                "max_tokens": 500,
                "messages": [{"role": "user",
                              "content": PROMPT.format(ocr_text=ocr_text[:6000])}],
            },
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        content = resp.json().get("content", [])
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        return _parse_json(text)
    except (requests.RequestException, KeyError, ValueError):
        return None


def _parse_json(text: str) -> dict | None:
    """Extract and parse the JSON object, tolerating markdown fences."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _validate(raw: dict) -> dict:
    """Type-check every field; drop anything malformed rather than trust it."""
    out: dict = {}
    v = raw.get("vendor")
    if isinstance(v, str) and 2 <= len(v.strip()) <= 100:
        out["vendor"] = v.strip()
    d = raw.get("date")
    if isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        year = int(d[:4])
        if 2000 <= year <= 2100:
            out["date"] = d
    for k in ("subtotal", "tax", "total"):
        val = raw.get(k)
        if isinstance(val, (int, float)) and 0 <= val < 10_000_000:
            out[k] = float(val)
    c = raw.get("currency")
    if isinstance(c, str) and re.fullmatch(r"[A-Z]{3}", c.strip().upper()):
        out["currency"] = c.strip().upper()
    # sanity: if all three amounts present and wildly inconsistent, drop
    # subtotal/tax (keep total — it's the field that matters most)
    if all(k in out for k in ("subtotal", "tax", "total")):
        if abs((out["subtotal"] + out["tax"]) - out["total"]) > out["total"] * 0.5:
            out.pop("subtotal"), out.pop("tax")
    return out


LLM_CONF = 0.85          # validated LLM answer
AGREE_CONF = 0.97        # LLM and rules independently agree
RULES_TRUST = 0.90       # rules above this keep their answer


def extract_with_llm(lines: list[OcrLine], rules_result: ExtractedFields) -> ExtractedFields:
    """Merge LLM extraction over the rules result. Never raises."""
    validated = None
    if llm_available():
        raw = _call_api(lines_to_text(lines))
        if raw is not None:
            validated = _validate(raw)
    if not validated:
        return rules_result  # graceful degradation

    merged = ExtractedFields(**{k: getattr(rules_result, k) for k in
                                ("vendor", "date", "subtotal", "tax", "total", "currency")})
    merged.confidence = dict(rules_result.confidence)

    for field_name in ("vendor", "date", "subtotal", "tax", "total", "currency"):
        llm_val = validated.get(field_name)
        if llm_val is None:
            continue
        rules_val = getattr(rules_result, field_name)
        rules_conf = rules_result.confidence.get(field_name, 0.0)

        if _agrees(field_name, rules_val, llm_val):
            merged.confidence[field_name] = AGREE_CONF
        elif rules_val is None or rules_conf < RULES_TRUST:
            setattr(merged, field_name, llm_val)
            merged.confidence[field_name] = LLM_CONF
        # else: high-confidence rules answer stands; disagreement caps its
        # confidence so the review UI flags it
        else:
            merged.confidence[field_name] = min(rules_conf, 0.75)
    return merged


def _agrees(field_name: str, rules_val, llm_val) -> bool:
    if rules_val is None:
        return False
    if field_name in ("subtotal", "tax", "total"):
        return abs(float(rules_val) - float(llm_val)) <= 0.01
    if field_name == "vendor":
        a = re.sub(r"[^a-z0-9]", "", str(rules_val).lower())
        b = re.sub(r"[^a-z0-9]", "", str(llm_val).lower())
        return bool(a and b) and (a in b or b in a)
    return str(rules_val).strip().lower() == str(llm_val).strip().lower()
