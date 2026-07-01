"""PDF parser: PyMuPDF text extraction, theory/derivation classification."""

from __future__ import annotations

import fitz  # pymupdf

from autograde_core.models import (
    ArtifactType,
    DerivationContent,
    FigureContent,
    TheoryContent,
)
from services.parsers.base import ParsedArtifact, Parser, classify_text, split_steps


class PdfParser(Parser):
    name = "pdf"

    def handles(self, filename: str) -> bool:
        return filename.lower().endswith(".pdf")

    def parse(self, filename: str, data: bytes) -> list[ParsedArtifact]:
        with fitz.open(stream=data, filetype="pdf") as doc:
            pages = doc.page_count
            text = "\n".join(page.get_text() for page in doc).strip()

        if not text:
            # Image-only PDF: treat as a figure to be looked at.
            return [
                ParsedArtifact(
                    ArtifactType.FIGURE,
                    FigureContent(image_ref=filename),
                    {"pages": pages, "reason": "no extractable text"},
                )
            ]

        atype = classify_text(text)
        if atype is ArtifactType.DERIVATION:
            content = DerivationContent(raw_text=text, steps=split_steps(text))
        else:
            content = TheoryContent(text=text)
        return [ParsedArtifact(atype, content, {"pages": pages})]
