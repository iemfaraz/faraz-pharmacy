"""Logging (Milestone 11).

One logger for the whole app, writing to logs/invoice_ai.log with
rotation (1 MB x 5 files) plus console output. Import and use:

    from app.utils.logger import get_logger
    log = get_logger(__name__)
    log.info("OCR complete: %d lines", len(lines))

Why rotation: an OCR app processes big batches; unbounded logs on a
client machine are a support ticket waiting to happen.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config

LOG_DIR = config.BASE_DIR / "logs"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(exist_ok=True)
    root = logging.getLogger("invoice_ai")
    root.setLevel(logging.INFO)
    if not root.handlers:
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")
        fh = RotatingFileHandler(LOG_DIR / "invoice_ai.log",
                                 maxBytes=1_000_000, backupCount=5,
                                 encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch.setLevel(logging.WARNING)  # console: warnings+ only
        root.addHandler(ch)
    _configured = True


def get_logger(name: str = "app") -> logging.Logger:
    _configure()
    return logging.getLogger(f"invoice_ai.{name.removeprefix('invoice_ai.')}")
