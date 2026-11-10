"""Image preprocessing pipeline (Milestone 4).

Composable OpenCV steps, each toggleable via config.PREPROCESS, applied
in a fixed order:

    resize -> grayscale -> contrast (CLAHE) -> denoise -> threshold -> deskew

Design notes:
- Every step is a pure function ndarray -> ndarray, so steps can be
  tested and benchmarked in isolation.
- CLAHE (adaptive contrast) is the key treatment for faded dot-matrix
  print: it darkens weak strokes locally without blowing out the paper.
- Adaptive thresholding is OFF by default: it helps degraded scans but
  can shred photos with uneven lighting. The benchmark decides.
- Deskew is conservative: only corrects angles in (0.5°, 15°]. Tiny
  angles aren't worth the interpolation blur; big ones are usually a
  sideways photo, which the OCR's angle classifier handles better.
- Output is always 3-channel RGB, because PaddleOCR expects color input
  regardless of what we did internally.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

import config


# --- individual steps ------------------------------------------------------

def resize(img: np.ndarray, max_edge: int) -> np.ndarray:
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest == 0 or longest == max_edge:
        return img
    scale = max_edge / longest
    if scale > 1 and longest >= 800:
        return img  # don't upscale already-reasonable images
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=interp)


def grayscale(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return img


def denoise(img: np.ndarray) -> np.ndarray:
    # h=5, not the common h=10: tested on faint dot-matrix print, h=10
    # erases the dots entirely (they look like noise to NLM). h=5 cleans
    # sensor noise while keeping weak strokes.
    return cv2.fastNlMeansDenoising(img, None, h=5, templateWindowSize=7, searchWindowSize=21)


def enhance_contrast(img: np.ndarray) -> np.ndarray:
    """CLAHE — local contrast boost; the faded-print rescuer."""
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(img)


def adaptive_threshold(img: np.ndarray) -> np.ndarray:
    return cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
        blockSize=31, C=15,
    )


def estimate_skew_angle(gray: np.ndarray) -> float:
    """Angle of the dominant text orientation, in degrees (-45, 45]."""
    # Dark pixels = ink. Otsu picks the split; invert so ink is white.
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dark_fraction = float((bw > 0).mean())
    # Guard: on photos with dark backgrounds the "ink" mask is mostly
    # background, and minAreaRect returns the background's angle, not the
    # text's. Real ink coverage on a receipt is a few percent; if "ink"
    # exceeds a third of the frame, the assumption is broken — skip.
    if dark_fraction > 0.35:
        return 0.0
    coords = cv2.findNonZero(bw)
    if coords is None or len(coords) < 100:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect's angle convention differs across OpenCV versions:
    # old builds return [-90, 0) (horizontal box = -90), newer (0, 90]
    # (horizontal box = 90). Normalize both into (-45, 45].
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90
    return float(angle)


def deskew(img: np.ndarray, min_angle: float = 0.5, max_angle: float = 15.0) -> np.ndarray:
    gray = grayscale(img)
    angle = estimate_skew_angle(gray)
    if not (min_angle < abs(angle) <= max_angle):
        return img
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        img, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255 if img.ndim == 2 else (255, 255, 255),
    )


# --- pipeline --------------------------------------------------------------

def preprocess(image: Image.Image | np.ndarray, settings: dict | None = None) -> np.ndarray:
    """Run the configured pipeline; returns RGB ndarray ready for OCR."""
    cfg = settings or config.PREPROCESS

    img = np.array(image.convert("RGB")) if isinstance(image, Image.Image) else image.copy()

    if cfg.get("resize", True):
        img = resize(img, cfg.get("max_edge_px", 2000))
    if cfg.get("grayscale", True):
        img = grayscale(img)
    if cfg.get("contrast", True) and img.ndim == 2:
        img = enhance_contrast(img)
    if cfg.get("denoise", True) and img.ndim == 2:
        img = denoise(img)
    if cfg.get("adaptive_threshold", False) and img.ndim == 2:
        img = adaptive_threshold(img)
    if cfg.get("deskew", True):
        img = deskew(img)

    if img.ndim == 2:  # back to 3-channel for PaddleOCR
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    return img


def preprocess_to_pil(image: Image.Image | np.ndarray, settings: dict | None = None) -> Image.Image:
    """Same pipeline, PIL output — for UI display."""
    return Image.fromarray(preprocess(image, settings))