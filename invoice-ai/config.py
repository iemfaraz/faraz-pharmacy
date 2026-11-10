"""Central configuration for Invoice AI.

Every tunable lives here so behavior can be changed without touching
pipeline code. Later milestones import from this module only.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEST_DATA_DIR = BASE_DIR / "data" / "test_invoices"
DB_PATH = BASE_DIR / "invoices.db"

for _d in (UPLOAD_DIR, OUTPUT_DIR, TEST_DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Upload constraints (Milestone 2)
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_FILE_SIZE_MB = 10

# ---------------------------------------------------------------------------
# OCR (Milestone 3)
# ---------------------------------------------------------------------------
OCR_LANG = "en"          # PaddleOCR language model
PDF_RENDER_DPI = 200     # rasterization DPI for PDF pages

# ---------------------------------------------------------------------------
# Preprocessing toggles (Milestone 4) — each step can be switched off
# ---------------------------------------------------------------------------
# Milestone 4 ablation verdict: preprocessing is neutral-to-harmful with
# PP-OCRv4 (see benchmarks.md) — OFF by default, available as an opt-in
# tool for genuinely degraded client scans.
PREPROCESS_DEFAULT_ON = False

PREPROCESS = {
    "resize": True,
    "max_edge_px": 2000,
    "grayscale": True,
    "contrast": True,             # CLAHE — rescues faded/dot-matrix print
    "denoise": True,              # gentle (h=5); runs AFTER contrast on purpose
    "adaptive_threshold": False,  # off by default: hurts photos, gate per-image
    "deskew": True,
}

# ---------------------------------------------------------------------------
# Extraction (Milestone 5)
# ---------------------------------------------------------------------------
USE_LLM_EXTRACTION = False  # rules-only by default; app must work offline
LLM_MODEL = "claude-sonnet-4-6"
TOTAL_KEYWORDS = ["total", "amount due", "balance due", "grand total"]
TAX_KEYWORDS = ["tax", "vat", "gst", "sales tax"]
SUBTOTAL_KEYWORDS = ["subtotal", "sub-total", "sub total"]