"""Extraction debugger: see exactly what the rules engine sees.

Usage:
    python scripts/debug_extract.py photo_beefaroo.jpg

Prints the ROW view (after y-clustering) with per-row keyword hits and
detected amounts, then the final extraction. This is how we diagnose
"why did it pick THAT?" without guessing.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from app.extraction import rules  # noqa: E402
from app.ocr.engine import get_engine  # noqa: E402
from app.utils import files as file_utils  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    fpath = config.TEST_DATA_DIR / sys.argv[1]
    if not fpath.exists():
        fpath = Path(sys.argv[1])
    if not fpath.exists():
        print(f"Not found: {sys.argv[1]}")
        return 1

    print("Loading OCR engine...")
    engine = get_engine()
    lines = engine.extract(file_utils.load_preview(fpath, 0))
    rows = rules.build_rows(lines)

    print(f"\n=== {fpath.name}: {len(lines)} lines -> {len(rows)} rows ===\n")
    for i, row in enumerate(rows):
        tags = []
        if rules._has_kw(row.text, rules.TOTAL_KEYWORDS):
            tags.append("TOTAL")
        if rules._has_kw(row.text, rules.SUBTOTAL_KEYWORDS):
            tags.append("SUBTOT")
        if rules._has_kw(row.text, rules.TAX_KEYWORDS):
            tags.append("TAX")
        if rules._has_kw(row.text, rules.PAYMENT_NOISE):
            tags.append("NOISE")
        amounts = rules._amounts_in(row.text)
        amt = f" amounts={amounts}" if amounts else ""
        tag = f" <{','.join(tags)}>" if tags else ""
        print(f"  {i:3d} y={row.y:6.0f} conf={row.confidence:.0%} | {row.text}{tag}{amt}")

    print("\n=== extraction ===")
    result = rules.extract_fields(lines)
    for k, v in result.to_dict().items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
