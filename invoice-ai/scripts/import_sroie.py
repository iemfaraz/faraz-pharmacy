"""Convert SROIE label files into data/test_invoices/ground_truth.json.

Usage:
    python scripts/import_sroie.py <path-to-sroie-folder> [--limit 15]

SROIE datasetv2 layout (Kaggle "urbikn/sroie-datasetv2"):
    SROIE2019/train/img/X00016469612.jpg
    SROIE2019/train/entities/X00016469612.txt   <- JSON: company/date/address/total

The script:
  1. Finds image+label pairs
  2. Copies up to --limit images into data/test_invoices/
  3. Writes/merges ground_truth.json entries (date normalized to YYYY-MM-DD)

Your own phone photos still need manual entries — add them to the JSON
afterwards with "difficulty": "photo".
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from dateutil import parser as dateparser

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = PROJECT_ROOT / "data" / "test_invoices"
GT_PATH = TEST_DIR / "ground_truth.json"


def find_pairs(sroie_root: Path):
    """Yield (image_path, label_path) pairs found anywhere under sroie_root."""
    labels = {}
    for txt in sroie_root.rglob("*.txt"):
        labels[txt.stem] = txt
    for img in sorted(sroie_root.rglob("*.jpg")):
        if img.stem in labels:
            yield img, labels[img.stem]


def parse_label(label_path: Path) -> dict | None:
    try:
        raw = json.loads(label_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return None

    date_iso = ""
    if raw.get("date"):
        try:
            date_iso = dateparser.parse(raw["date"], dayfirst=True).strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            date_iso = raw["date"]  # keep original if unparseable; fix by hand

    total = 0.0
    if raw.get("total"):
        try:
            total = float(str(raw["total"]).replace(",", "").replace("$", "").strip())
        except ValueError:
            pass

    return {
        "vendor": raw.get("company", "").strip(),
        "date": date_iso,
        "subtotal": None,   # SROIE doesn't label these; fill manually if needed
        "tax": None,
        "total": total,
        "difficulty": "scan",
        "source": "SROIE (benchmark use only - do not publish image)",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sroie_root", type=Path, help="Extracted SROIE dataset folder")
    ap.add_argument("--limit", type=int, default=15, help="Max receipts to import")
    args = ap.parse_args()

    if not args.sroie_root.exists():
        print(f"Folder not found: {args.sroie_root}")
        return 1

    TEST_DIR.mkdir(parents=True, exist_ok=True)
    ground_truth: dict = {}
    if GT_PATH.exists():
        try:
            ground_truth = json.loads(GT_PATH.read_text(encoding="utf-8"))
            ground_truth.pop("_instructions", None)
            ground_truth.pop("sample_001.jpg", None)  # drop the placeholder
        except json.JSONDecodeError:
            print("Warning: existing ground_truth.json unreadable, starting fresh")

    imported = 0
    for img, label in find_pairs(args.sroie_root):
        if imported >= args.limit:
            break
        entry = parse_label(label)
        if entry is None or not entry["vendor"] or not entry["total"]:
            continue  # skip incomplete labels
        dest_name = f"sroie_{img.stem}.jpg"
        shutil.copy2(img, TEST_DIR / dest_name)
        ground_truth[dest_name] = entry
        imported += 1
        print(f"  + {dest_name}: {entry['vendor'][:40]} | {entry['date']} | {entry['total']}")

    GT_PATH.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nImported {imported} receipts -> {TEST_DIR}")
    print(f"Ground truth entries: {len(ground_truth)} -> {GT_PATH}")
    print("\nNext: add 3-5 of your own phone photos and label them manually "
          "with \"difficulty\": \"photo\".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
