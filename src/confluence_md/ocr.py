"""Optional OCR via pytesseract. Fails soft: returns ('', 0.0) if pytesseract or the
tesseract binary is unavailable, so the rest of the pipeline works without OCR installed.
"""
from __future__ import annotations

from pathlib import Path


def is_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_text(image_path: Path) -> tuple[str, float]:
    """Return (text, mean_confidence). Confidence is 0.0–1.0; 0.0 if OCR unavailable or no text."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", 0.0

    try:
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception:
        return "", 0.0

    words: list[str] = []
    confs: list[float] = []
    for word, conf in zip(data.get("text", []), data.get("conf", [])):
        word = (word or "").strip()
        if not word:
            continue
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if c < 0:
            continue
        words.append(word)
        confs.append(c)

    text = " ".join(words)
    mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return text, mean_conf
