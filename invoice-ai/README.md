# Invoice AI 🧾

**OCR-powered invoice & receipt data extraction.** Upload an invoice or a whole batch (JPG / PNG / PDF), let the pipeline pull out vendor, date, tax, totals and line items, review anything it's unsure about, then save to a searchable database and export to Excel / CSV / JSON.

> Built as a production-style pipeline with benchmark-driven engineering. Every accuracy number below is measured against a labeled test set, and every design decision — including the counterintuitive ones — has data behind it.


**🔗 [Try the quick live demo] -- https://invoice-ai-ruwz3i3jqdta9avuvhfnt2.streamlit.app

*(The hosted demo runs on precomputed OCR to fit its free-tier host. Run locally — see Setup — for live OCR on your own uploads.)*

---

## What it does

- **Reads any receipt or invoice** — retail receipts, restaurant bills, and invoices across multiple countries and currencies (tested on Bangladeshi, Indian, Malaysian, and US formats).
- **Extracts structured data** — vendor, date, subtotal, tax, total, currency, and itemized line items, each with a confidence score.
- **Flags what needs a human** — low-confidence fields and math discrepancies are surfaced for review; the machine never silently "fixes" your data.
- **Processes in bulk** — drop in a stack of receipts, auto-approve the ones whose numbers reconcile, review only the flagged minority.
- **Stores, searches, analyzes, exports** — SQLite persistence with full-text and filtered search, a currency-aware dashboard, and Excel/CSV/JSON export.

---

## The pipeline

```
Upload (JPG / PNG / PDF) — single or batch
  └─> OCR (PaddleOCR PP-OCRv4, bounding boxes preserved)
       └─> Field extraction  (rules engine + optional LLM refinement)
       └─> Table extraction  (geometric row/column clustering)
            └─> Review & Edit (confidence-coded form, live validation)
                 └─> SQLite (search, duplicates, audit trail)
                      └─> Dashboard (currency-aware analytics)
                      └─> Export (Excel / CSV / JSON, filter-aware)
```

---

## Engineering highlights

**Preprocessing: built, measured, turned off.** The classic OpenCV pipeline (deskew, denoise, CLAHE, thresholding) was implemented, then ablation-tested per-step against a labeled set of scans and phone photos. Result: with modern PP-OCRv4, every step was neutral-to-harmful — the model already normalizes internally. Preprocessing ships **off by default**, available as an opt-in for genuinely degraded scans. The full ablation lives in `benchmarks.md`.

**Hybrid extraction with honest confidence.** A rules engine — row clustering from OCR bounding boxes, keyword matching with OCR-damage tolerance ("Tota1" still matches "total"), currency un-gluing, sanity guards — provides a fast, fully offline baseline. An optional LLM layer refines low-confidence fields with strict JSON validation and graceful degradation: no API key, no network, or a malformed response all fall back to rules silently. Every field carries a confidence score, and the review screen color-codes them.

**Validation flags, never silently corrects.** Real receipts round, discount, and use inclusive tax. When subtotal + tax ≠ total, or line items don't sum to the printed subtotal, the app *warns* the reviewer rather than "correcting" the numbers.

**Batch processing with confidence-based triage.** Upload a stack of receipts and the app splits them into *clean* (numbers reconcile — subtotal + tax = total, or line items sum to total) and *needs review* (low confidence or a math discrepancy). Clean invoices approve in one click; attention goes only where the data warrants it. This scales the human-in-the-loop model to volume without burying errors in the database.

**Currency-aware analytics.** Totals are never summed across currencies (or across unknown currencies) — the dashboard groups by currency and explains why.

---

## Measured accuracy

Labeled test set: SROIE scanned receipts + real phone photos, across four countries.

| Stage                                | Vendor    | Date    | Total    |
| ------------------------------------ | --------- | ------- | -------- |
| Rules extraction (exact field match) | 68%       | 95%     | 68%      |
| — phone-photo subset                 | 100%      | 100%    | 100%     |
| **Hybrid (rules + LLM)**             | **68%\*** | **95%** | **100%** |

\* Hybrid vendor accuracy is understated by labeling convention: on manual audit, several "misses" are the LLM returning the correct storefront brand (e.g. "McDonald's") where the ground-truth label uses the registered legal entity. **Total-amount extraction reached 100%** across all test receipts under hybrid extraction.

Raw OCR text-capture baseline: ~94–96% confidence, 100% of totals present in the text. The hard part is the gap between "text captured" and "field correctly extracted" — see `benchmarks.md` for the full progression and `scripts/` for the reproducible benchmark harness.

---

## Setup

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements-full.txt      # full stack incl. PaddleOCR (local)
streamlit run app.py
```

> **Python 3.11 or 3.12** required — PaddlePaddle does not yet support 3.13+.
> First OCR run downloads models (~20 MB) and takes ~30s to initialize.
>
> `requirements.txt` is the lightweight deploy manifest (no PaddleOCR, for the hosted demo). For local development with live OCR, install `requirements-full.txt` as shown above.

**Optional LLM refinement:** set `ANTHROPIC_API_KEY` in your environment and `USE_LLM_EXTRACTION = True` in `config.py`. The app is fully functional offline without it.

---

## Tests & benchmarks

```bash
pytest                                   # 45 tests, ~2s
python scripts/benchmark_ocr.py          # raw OCR vs ground truth
python scripts/benchmark_fields.py       # field-extraction accuracy
python scripts/benchmark_fields.py --llm # hybrid accuracy (needs API key)
python scripts/ablate_preprocess.py      # per-step preprocessing ablation
python scripts/debug_extract.py FILE     # row-level extraction trace
```

Test data: place labeled invoices in `data/test_invoices/` with a `ground_truth.json` (see `scripts/import_sroie.py` for SROIE import). SROIE images are research-licensed — used for benchmarking only, never redistributed or displayed.

---

## Docker

```bash
docker build -t invoice-ai .
docker run -p 8501:8501 -v invoice_data:/app/data invoice-ai
```

---

## Project structure

```
app/
├── ocr/            PaddleOCR wrapper (normalized OcrLine output)
├── preprocessing/  OpenCV pipeline (opt-in, ablation-tested)
├── extraction/     rules.py + llm.py (fields), tables.py (line items)
├── review/         confidence-coded review & edit screen
├── database/       SQLAlchemy models + repository (UI never touches the ORM)
├── export/         Excel / CSV / JSON exporters
├── batch.py        batch triage (reconciliation-based clean/review split)
├── demo.py         demo mode for memory-limited hosting
└── utils/          file handling, rotating logs
scripts/            benchmarks, ablation, debugging tools
tests/              45 regression tests, each from a real-receipt failure case
```

---

## Tech stack

Python · PaddleOCR (PP-OCRv4) · OpenCV · Streamlit · SQLAlchemy / SQLite · Pandas · Anthropic API (optional) · Docker

---

## License & data note

Application code is available for review as a portfolio project. The SROIE dataset used for benchmarking is research-licensed and is not redistributed here; sample images shown in the demo are the author's own receipts.

---

## Faraz Pharmacy integration

This copy lives inside the `faraz-pharmacy` repo and powers **Dashboard -> Medicine inventory -> Extract from bill (Invoice AI)**.

- `app/api/server.py` — FastAPI wrapper: `POST /api/extract` (JPG/PNG/PDF up to 5 MB, 3 pages) returns vendor, invoice number, date, totals and line items as JSON. Nothing is stored; the dashboard turns the result into an editable draft and the owner reviews every row before stock is added.
- Auth: each request needs the owner's dashboard session token, which the API verifies against the existing pharmacy backend (`PHARMACY_API_URL`). CORS is limited to `ALLOWED_ORIGINS`.
- Deploy on Render with `render.yaml` (Docker, `Dockerfile.api`). PaddleOCR needs roughly 1–2 GB RAM, so use at least the Standard plan.
- Then set the service URL in `invoice-ai-config.js` at the repo root (`window.INVOICE_AI_URL`).
- The SROIE benchmark images and ground truth were intentionally not copied (research-licensed, not for redistribution).

Local run: `pip install -r requirements-api.txt && uvicorn app.api.server:app --port 8000`
