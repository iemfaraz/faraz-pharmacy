"""Milestone 3 baseline benchmark: raw OCR vs ground truth.

Usage (from project root, venv active):
    python scripts/benchmark_ocr.py

For every labeled file in data/test_invoices/ it runs OCR and checks
whether the ground-truth vendor and total appear anywhere in the raw
text (a "containment" metric — field extraction doesn't exist yet, so
this measures whether OCR even captured the right characters).

Results print grouped by difficulty and append a row to benchmarks.md.
Re-run after Milestone 4 to measure what preprocessing changed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from app.ocr.engine import get_engine, lines_to_text  # noqa: E402
from app.utils import files as file_utils  # noqa: E402

GT_PATH = config.TEST_DATA_DIR / "ground_truth.json"
BENCH_PATH = PROJECT_ROOT / "benchmarks.md"


def normalize(s: str) -> str:
    """Lowercase, strip punctuation/whitespace for tolerant matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def vendor_found(vendor: str, text: str) -> bool:
    """Tolerant check: full normalized vendor, or its longest word (>=4 chars)."""
    if not vendor:
        return False
    norm_text = normalize(text)
    if normalize(vendor) in norm_text:
        return True
    words = [w for w in re.split(r"\W+", vendor) if len(w) >= 4]
    return any(normalize(w) in norm_text for w in sorted(words, key=len, reverse=True)[:1])


def total_found(total, text: str) -> bool:
    """Check the amount appears with or without thousands separators/decimals."""
    if total in (None, 0, 0.0) and total != 0:
        return False
    variants = {f"{total:.2f}", f"{total:g}", f"{total:,.2f}"}
    squashed = text.replace(" ", "")
    return any(v in squashed for v in variants)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preprocess", action="store_true",
                    help="run the Milestone 4 pipeline before OCR")
    args = ap.parse_args()
    stage = "milestone-4 preprocessed" if args.preprocess else "milestone-3 raw"

    if not GT_PATH.exists():
        print(f"No ground truth at {GT_PATH}")
        return 1
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))
    gt = {k: v for k, v in gt.items() if not k.startswith("_")}
    if not gt:
        print("ground_truth.json has no entries")
        return 1

    print(f"Loading OCR engine...")
    engine = get_engine()

    by_diff: dict[str, list[dict]] = defaultdict(list)
    for fname, truth in sorted(gt.items()):
        fpath = config.TEST_DATA_DIR / fname
        if not fpath.exists():
            print(f"  ! missing file, skipped: {fname}")
            continue
        image = file_utils.load_preview(fpath, 0)
        if args.preprocess:
            from app.preprocessing.pipeline import preprocess
            image = preprocess(image)
        lines = engine.extract(image)
        text = lines_to_text(lines)
        avg_conf = sum(l.confidence for l in lines) / len(lines) if lines else 0.0

        result = {
            "file": fname,
            "vendor_ok": vendor_found(truth.get("vendor", ""), text),
            "total_ok": total_found(truth.get("total"), text),
            "lines": len(lines),
            "avg_conf": avg_conf,
        }
        by_diff[truth.get("difficulty", "unknown")].append(result)
        v = "V" if result["vendor_ok"] else "-"
        t = "T" if result["total_ok"] else "-"
        print(f"  [{v}{t}] {fname:35s} lines={len(lines):3d} conf={avg_conf:.0%}")

    print("\n=== By difficulty ===")
    rows = []
    for diff, results in sorted(by_diff.items()):
        n = len(results)
        v_pct = sum(r["vendor_ok"] for r in results) / n
        t_pct = sum(r["total_ok"] for r in results) / n
        c_avg = sum(r["avg_conf"] for r in results) / n
        print(f"  {diff:10s} n={n:2d}  vendor {v_pct:.0%}  total {t_pct:.0%}  conf {c_avg:.0%}")
        rows.append((diff, n, v_pct, t_pct, c_avg))

    all_r = [r for rs in by_diff.values() for r in rs]
    n = len(all_r)
    line = (f"| {date.today()} | {stage} | n={n} "
            f"| vendor {sum(r['vendor_ok'] for r in all_r)/n:.0%} "
            f"| total {sum(r['total_ok'] for r in all_r)/n:.0%} "
            f"| conf {sum(r['avg_conf'] for r in all_r)/n:.0%} |")

    if not BENCH_PATH.exists():
        BENCH_PATH.write_text(
            "# OCR Benchmarks\n\n| Date | Stage | Samples | Vendor found | Total found | Avg conf |\n"
            "|---|---|---|---|---|---|\n", encoding="utf-8")
    with BENCH_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"\nAppended to {BENCH_PATH.name}: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())