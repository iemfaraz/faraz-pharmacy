"""Milestone 5 benchmark: field extraction accuracy vs ground truth.

Usage:
    python scripts/benchmark_fields.py

Per file: OCR -> extract_fields -> compare vendor/date/total (and
subtotal/tax where labeled). Prints per-file marks, per-difficulty
summary, and appends to benchmarks.md.

Matching:
- vendor: normalized containment either way (extracted within truth or
  truth within extracted) — "99 SPEED MART S/B" vs "...(519537-X)" is a hit
- date: exact ISO match
- amounts: within 0.01
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
from app.extraction.rules import extract_fields  # noqa: E402
from app.ocr.engine import get_engine  # noqa: E402
from app.utils import files as file_utils  # noqa: E402

GT_PATH = config.TEST_DATA_DIR / "ground_truth.json"
BENCH_PATH = PROJECT_ROOT / "benchmarks.md"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def vendor_match(extracted: str | None, truth: str) -> bool:
    if not extracted or not truth:
        return False
    a, b = norm(extracted), norm(truth)
    return (a in b or b in a) and min(len(a), len(b)) >= 4


def amount_match(extracted: float | None, truth) -> bool | None:
    if truth is None:
        return None  # unlabeled — not scored
    if extracted is None:
        return False
    return abs(extracted - float(truth)) <= 0.01


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="hybrid: rules + LLM merge")
    args = ap.parse_args()
    stage = "milestone-5 hybrid" if args.llm else "milestone-5 rules"
    if args.llm:
        from app.extraction.llm import extract_with_llm, llm_available
        if not llm_available():
            print("ANTHROPIC_API_KEY not set — aborting --llm run")
            return 1

    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))
    gt = {k: v for k, v in gt.items() if not k.startswith("_")}
    print("Loading OCR engine...")
    engine = get_engine()

    by_diff = defaultdict(list)
    for fname, truth in sorted(gt.items()):
        fpath = config.TEST_DATA_DIR / fname
        if not fpath.exists():
            continue
        lines = engine.extract(file_utils.load_preview(fpath, 0))
        f = extract_fields(lines)
        if args.llm:
            f = extract_with_llm(lines, f)

        marks = {
            "V": vendor_match(f.vendor, truth.get("vendor", "")),
            "D": f.date == truth.get("date"),
            "T": amount_match(f.total, truth.get("total")),
            "S": amount_match(f.subtotal, truth.get("subtotal")),
            "X": amount_match(f.tax, truth.get("tax")),
        }
        by_diff[truth.get("difficulty", "unknown")].append(marks)
        tag = "".join(k if v else ("." if v is None else "-") for k, v in marks.items())
        detail = "" if marks["V"] else f"  vendor->{f.vendor!r}"
        detail += "" if marks["D"] else f"  date->{f.date!r}"
        detail += "" if marks["T"] in (True, None) else f"  total->{f.total!r}"
        print(f"  [{tag}] {fname:35s}{detail}")

    def pct(results, key):
        scored = [r[key] for r in results if r[key] is not None]
        return (sum(scored) / len(scored)) if scored else None

    print("\n=== By difficulty (V=vendor D=date T=total S=subtotal X=tax, .=unlabeled) ===")
    for diff, results in sorted(by_diff.items()):
        parts = []
        for key, label in [("V", "vendor"), ("D", "date"), ("T", "total"),
                           ("S", "subtotal"), ("X", "tax")]:
            p = pct(results, key)
            parts.append(f"{label} {p:.0%}" if p is not None else f"{label} n/a")
        print(f"  {diff:10s} n={len(results):2d}  " + "  ".join(parts))

    all_r = [r for rs in by_diff.values() for r in rs]
    v, d, t = pct(all_r, "V"), pct(all_r, "D"), pct(all_r, "T")
    line = (f"| {date.today()} | {stage} | n={len(all_r)} "
            f"| vendor {v:.0%} | date {d:.0%} | total {t:.0%} |")
    with BENCH_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(f"\nAppended: {line}")
    print("Note: this row measures FIELD EXTRACTION (exact values), a harder "
          "test than the M3/M4 rows (text containment) — numbers aren't comparable across stages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
    