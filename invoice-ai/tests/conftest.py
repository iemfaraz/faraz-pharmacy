"""Shared test fixtures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.ocr.engine import OcrLine


@pytest.fixture
def L():
    """OcrLine factory used across extraction tests."""
    def make(text, y=0, x=0, conf=0.95, w=100, h=14):
        return OcrLine(text=text, confidence=conf,
                       bbox=[[x, y], [x + w, y], [x + w, y + h], [x, y + h]])
    return make
