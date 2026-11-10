"""PaddleOCR wrapper.

Design goals:
- Initialize the model exactly once (loading takes ~10-30s); callers get
  a shared instance via get_engine().
- Normalize PaddleOCR's nested output into flat OcrLine records so the
  rest of the codebase never touches Paddle's raw format. If we ever swap
  OCR backends, only this file changes.
- Keep bounding boxes: Milestone 6 (table extraction) clusters lines into
  rows/columns using their coordinates.

Note: on first ever run, PaddleOCR downloads its detection/recognition
models (~20 MB) to ~/.paddleocr. Requires internet once.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

import config


@dataclass
class OcrLine:
    """One recognized text line."""
    text: str
    confidence: float          # 0.0 - 1.0
    bbox: list[list[float]]    # 4 corner points [[x,y] * 4], clockwise from top-left

    @property
    def top(self) -> float:
        return min(p[1] for p in self.bbox)

    @property
    def left(self) -> float:
        return min(p[0] for p in self.bbox)


class OcrEngine:
    def __init__(self, lang: str | None = None):
        # Import here so merely importing this module stays fast and
        # non-OCR code paths (e.g. tests of other modules) don't pay the cost.
        from paddleocr import PaddleOCR

        lang = lang or config.OCR_LANG
        try:
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        except TypeError:
            # some paddleocr builds renamed/removed show_log
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang)

    def extract(self, image: Image.Image | np.ndarray | str | Path) -> list[OcrLine]:
        """Run OCR on an image (PIL, numpy array, or file path).

        Returns lines sorted top-to-bottom, left-to-right — natural
        reading order, which Milestone 5's rules depend on.
        """
        if isinstance(image, Image.Image):
            image = np.array(image.convert("RGB"))
        elif isinstance(image, (str, Path)):
            image = np.array(Image.open(image).convert("RGB"))

        raw = self._ocr.ocr(image, cls=True)

        lines: list[OcrLine] = []
        # raw is a list with one entry per image; entry is None if nothing found
        for page in raw or []:
            for item in page or []:
                bbox, (text, conf) = item
                text = text.strip()
                if text:
                    lines.append(OcrLine(text=text, confidence=float(conf), bbox=bbox))

        lines.sort(key=lambda l: (round(l.top / 10), l.left))  # row-ish, then x
        return lines


_engine: OcrEngine | None = None


def get_engine() -> OcrEngine:
    """Shared engine instance (module-level singleton)."""
    global _engine
    if _engine is None:
        _engine = OcrEngine()
    return _engine


def lines_to_text(lines: list[OcrLine]) -> str:
    """Raw text block, one recognized line per row."""
    return "\n".join(l.text for l in lines)
