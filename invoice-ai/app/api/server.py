"""HTTP API for the Faraz Pharmacy dashboard (Inventory -> "Extract from bill").

    POST /api/extract   multipart "file" (JPG / PNG / PDF, <= 5 MB, <= 3 pages)
    GET  /health

The pharmacy dashboard is a static site, so it cannot run Python. This
small FastAPI service wraps the existing Invoice AI pipeline (PaddleOCR ->
rules -> table extraction) and returns plain JSON that the dashboard turns
into an editable inventory draft. Nothing is saved to the inventory here;
the owner still reviews every row before stock is added.

Security model
- Every /api/extract call needs the owner's dashboard session token
  (Authorization: Bearer ...). The token is verified by asking the existing
  pharmacy backend (PHARMACY_API_URL) whether it can read the inventory.
  If that backend cannot be reached the request is refused (fail closed).
- CORS is limited to ALLOWED_ORIGINS.
- Uploaded bills are processed in memory and never written to disk or logged.

Run:  uvicorn app.api.server:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import time

import requests
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from PIL import Image

import config

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 3
MAX_PIXELS = 32_000_000
MAX_EDGE = 2800
PDF_DPI = 200

PHARMACY_API_URL = os.environ.get(
    "PHARMACY_API_URL",
    "https://faraz-pharmacy-orders.faraznawaz2014.chatgpt.site",
).rstrip("/")
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://iemfaraz.github.io,https://farazpharmacy.com,https://www.farazpharmacy.com",
    ).split(",") if o.strip()
]
TOKEN_CACHE_SECONDS = 300
OCR_QUEUE_TIMEOUT = 25  # seconds a request waits for the single OCR slot

Image.MAX_IMAGE_PIXELS = MAX_PIXELS

app = FastAPI(title="Faraz Pharmacy Invoice AI", docs_url=None, redoc_url=None,
              openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

_ocr_slot = asyncio.Semaphore(1)          # PaddleOCR is memory hungry: one at a time
_token_cache: dict[str, float] = {}        # sha256(token) -> verified-until


# --- auth -------------------------------------------------------------------

def _verify_owner_token(token: str) -> None:
    """Raise HTTPException unless the pharmacy backend accepts this token."""
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    if _token_cache.get(key, 0) > now:
        return
    try:
        r = requests.get(PHARMACY_API_URL + "/api/inventory",
                         headers={"Authorization": "Bearer " + token},
                         timeout=10)
    except requests.RequestException:
        raise HTTPException(503, "Could not verify your pharmacy session. Try again.")
    if r.status_code in (401, 403):
        raise HTTPException(401, "Your pharmacy session is not valid. Sign in again.")
    if r.status_code != 200:
        raise HTTPException(503, "Could not verify your pharmacy session. Try again.")
    for k in [k for k, exp in _token_cache.items() if exp <= now]:
        del _token_cache[k]
    if len(_token_cache) > 200:
        _token_cache.clear()
    _token_cache[key] = now + TOKEN_CACHE_SECONDS


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in to the pharmacy dashboard first.")
    token = authorization[7:].strip()
    if not token or len(token) > 4096:
        raise HTTPException(401, "Sign in to the pharmacy dashboard first.")
    return token


# --- OCR + extraction --------------------------------------------------------

def _get_engine():
    """Seam for tests: returns an object with .extract(PIL.Image) -> [OcrLine]."""
    from app.ocr.engine import get_engine
    return get_engine()


def _fit(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    scale = min(1.0, MAX_EDGE / max(img.size))
    if scale < 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)))
    return img


def _pages(data: bytes, content_type: str) -> list[Image.Image]:
    if data[:5] == b"%PDF-":
        import pymupdf
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            raise HTTPException(400, "This PDF could not be opened.")
        with doc:
            if doc.is_encrypted:
                raise HTTPException(400, "Password-protected PDFs are not supported.")
            if doc.page_count > MAX_PAGES:
                raise HTTPException(400, f"Please split the bill into PDFs of {MAX_PAGES} pages or fewer.")
            out = []
            for page in doc:
                pix = page.get_pixmap(dpi=PDF_DPI)
                out.append(_fit(Image.frombytes("RGB", (pix.width, pix.height), pix.samples)))
            return out
    is_webp = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if data[:3] != b"\xff\xd8\xff" and data[:8] != b"\x89PNG\r\n\x1a\n" and not is_webp:
        raise HTTPException(400, "Choose a JPEG, PNG or WebP photo, or a PDF.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        raise HTTPException(400, "This image could not be read.")
    return [_fit(img)]


_INVOICE_NO = re.compile(
    r"\b(?:invoice|bill|inv)(?:\s*(?:no\.?|number|#))?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/\-]{2,40})",
    re.IGNORECASE)


def _invoice_number(text: str) -> str | None:
    for m in _INVOICE_NO.finditer(text):
        v = m.group(1)
        if v.lower() not in ("date", "number", "total", "no") and any(c.isdigit() for c in v):
            return v
    return None


def run_extraction(pages: list[Image.Image]) -> dict:
    from app.extraction.rules import extract_fields
    from app.extraction.tables import extract_table

    engine = _get_engine()
    fields = None
    items, flags, texts, confs = [], [], [], []
    for n, img in enumerate(pages, 1):
        lines = engine.extract(img)
        if not lines:
            continue
        texts.append("\n".join(l.text for l in lines))
        confs.extend(l.confidence for l in lines)
        page_fields = extract_fields(lines)
        if fields is None:
            fields = page_fields
        else:  # later pages usually carry the totals
            for k in ("vendor", "date", "subtotal", "tax", "total", "currency"):
                if getattr(page_fields, k) is not None and (
                        k in ("subtotal", "tax", "total") or getattr(fields, k) is None):
                    setattr(fields, k, getattr(page_fields, k))
                    fields.confidence[k] = page_fields.confidence.get(k, 0.0)
        table = extract_table(lines)
        items.extend(table.items)
        flags.extend(table.flags)
    if fields is None:
        raise HTTPException(422, "No text could be read. Try a sharper, well-lit photo.")

    items_sum = sum(i.line_total for i in items if i.line_total is not None) or None
    warnings = list(dict.fromkeys(flags))
    if fields.total is None:
        warnings.append("No total was found on the bill.")
    elif items_sum and abs(items_sum - fields.total) > max(0.05, fields.total * 0.02) and (
            fields.subtotal is None or abs(items_sum - fields.subtotal) > max(0.05, fields.subtotal * 0.02)):
        warnings.append("Line items do not add up to the printed total; check every row.")
    if not items:
        warnings.append("No line items were detected. Enter the medicines manually.")

    text = "\n\n".join(texts)
    return {
        "vendor": fields.vendor,
        "invoice_number": _invoice_number(text),
        "date": fields.date,
        "subtotal": fields.subtotal,
        "tax": fields.tax,
        "total": fields.total,
        "currency": fields.currency,
        "confidence": {k: round(v, 2) for k, v in fields.confidence.items()},
        "ocr_confidence": round(sum(confs) / len(confs), 2) if confs else None,
        "items": [i.to_dict() for i in items],
        "warnings": warnings,
        "text": text[:20000],
    }


# --- routes -------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/extract")
async def extract(file: UploadFile = File(...),
                  authorization: str | None = Header(default=None)):
    token = _bearer(authorization)
    await run_in_threadpool(_verify_owner_token, token)

    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Choose a bill up to 5 MB.")

    try:
        await asyncio.wait_for(_ocr_slot.acquire(), OCR_QUEUE_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(429, "The bill reader is busy. Try again in a moment.")
    try:
        pages = await run_in_threadpool(_pages, data, file.content_type or "")
        return await run_in_threadpool(run_extraction, pages)
    finally:
        _ocr_slot.release()
