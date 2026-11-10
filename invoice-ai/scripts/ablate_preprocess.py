"""Preprocessing ablation (Milestone 4 diagnosis).

Runs OCR on a small subset of files under several pipeline configurations
— baseline (no preprocessing), each step alone, and the full pipeline —
and reports vendor/total hits per config so we can see which steps help,
which hurt, and on which kinds of images.

Usage (from project root):
    python scripts/ablate_preprocess.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from app.ocr.engine import get_engine, lines_to_text  # noqa: E402
from app.preprocessing.pipeline import preprocess  # noqa: E402
from app.utils import files as file_utils  # noqa: E402

# problem files + controls; edit freely
SUBSET = [
    "sroie_X51005268408.jpg",   # vendor miss, faded dot-matrix (target)
    "sroie_X51005337867.jpg",   # vendor miss (target)
    "photo_beefaroo.jpg",       # regressed under full pipeline
    "photo_pinewood.jpg",       # control: photo that was fine
    "sroie_X51005230605.jpg",   # control: scan that was fine
]

OFF = {"resize": False, "grayscale": False, "denoise": False,
       "contrast": False, "adaptive_threshold": False, "deskew": False}

CONFIGS: dict[str, dict | None] = {
    "baseline (none)": None,
    "resize only": {**OFF, "resize": True, "max_edge_px": 2000},
    "contrast only": {**OFF, "grayscale": True, "contrast": True},
    "denoise only": {**OFF, "grayscale": True, "denoise": True},
    "threshold only": {**OFF, "grayscale": True, "adaptive_threshold": True},
    "deskew only": {**OFF, "deskew": True},
    "full pipeline": dict(config.PREPROCESS),
}


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def vendor_found(vendor: str, text: str) -> bool:
    if not vendor:
        return False
    nt = normalize(text)
    if normalize(vendor) in nt:
        return True
    words = [w for w in re.split(r"\W+", vendor) if len(w) >= 4]
    return any(normalize(w) in nt for w in sorted(words, key=len, reverse=True)[:1])


def total_found(total, text: str) -> bool:
    if total is None:
        return False
    variants = {f"{total:.2f}", f"{total:g}", f"{total:,.2f}"}
    squashed = text.replace(" ", "")
    return any(v in squashed for v in variants)


def main() -> int:
    gt = json.loads((config.TEST_DATA_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    print("Loading OCR engine...")
    engine = get_engine()

    images = {}
    for fname in SUBSET:
        fpath = config.TEST_DATA_DIR / fname
        if fpath.exists():
            images[fname] = file_utils.load_preview(fpath, 0)
        else:
            print(f"  ! missing, skipped: {fname}")

    col_w = max(len(c) for c in CONFIGS) + 2
    header = "config".ljust(col_w) + "  ".join(f[:12].ljust(13) for f in images)
    print("\n" + header)
    print("-" * len(header))
    print(" " * col_w + "  ".join("[VT] marks".ljust(13) for _ in images))

    for cfg_name, cfg in CONFIGS.items():
        marks = []
        for fname, image in images.items():
            img = image if cfg is None else preprocess(image, cfg)
            lines = engine.extract(img)
            text = lines_to_text(lines)
            conf = sum(l.confidence for l in lines) / len(lines) if lines else 0
            v = "V" if vendor_found(gt[fname].get("vendor", ""), text) else "-"
            t = "T" if total_found(gt[fname].get("total"), text) else "-"
            marks.append(f"[{v}{t}] {conf:.0%}".ljust(13))
        print(cfg_name.ljust(col_w) + "  ".join(marks))

    print("\nRead it column by column: a step earns its place only if it flips a "
          "'-' to a letter somewhere without flipping a letter to '-' elsewhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
