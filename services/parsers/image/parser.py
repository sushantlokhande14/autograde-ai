"""Image parser: Tesseract OCR for text-in-image; figure artifact."""

from __future__ import annotations

import os
from io import BytesIO

import pytesseract
from PIL import Image

from autograde_core.models import ArtifactType, FigureContent
from services.parsers.base import ParsedArtifact, Parser

_IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff")
_DEFAULT_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _configure_tesseract() -> None:
    cmd = os.environ.get("TESSERACT_CMD")
    if not cmd and os.path.exists(_DEFAULT_TESSERACT):
        cmd = _DEFAULT_TESSERACT
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


class ImageParser(Parser):
    name = "image"

    def handles(self, filename: str) -> bool:
        return filename.lower().endswith(_IMG_EXT)

    def parse(self, filename: str, data: bytes) -> list[ParsedArtifact]:
        _configure_tesseract()
        img = Image.open(BytesIO(data))
        try:
            ocr = pytesseract.image_to_string(img).strip()
        except Exception:  # noqa: BLE001  (missing binary etc.; degrade gracefully)
            ocr = ""
        content = FigureContent(image_ref=filename, ocr_text=ocr or None)
        meta = {"size": list(img.size), "format": img.format}
        return [ParsedArtifact(ArtifactType.FIGURE, content, meta)]
