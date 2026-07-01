"""Fallback parser: .txt/.md/.docx to text; everything else to unknown."""

from __future__ import annotations

from io import BytesIO

from docx import Document

from autograde_core.models import (
    ArtifactType,
    DerivationContent,
    TheoryContent,
    UnknownContent,
)
from services.parsers.base import ParsedArtifact, Parser, classify_text, split_steps


class FallbackParser(Parser):
    name = "fallback"

    def handles(self, filename: str) -> bool:
        return True  # catch-all; must be registered last

    def parse(self, filename: str, data: bytes) -> list[ParsedArtifact]:
        low = filename.lower()
        if low.endswith(".docx"):
            doc = Document(BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs).strip()
        elif low.endswith((".txt", ".md")):
            text = data.decode("utf-8", errors="replace").strip()
        else:
            ext = low.rsplit(".", 1)[-1] if "." in low else "?"
            return [
                ParsedArtifact(
                    ArtifactType.UNKNOWN,
                    UnknownContent(note=f"unhandled .{ext}"),
                    {"bytes": len(data)},
                )
            ]

        if not text:
            return [ParsedArtifact(ArtifactType.UNKNOWN, UnknownContent(note="empty text"), {})]

        atype = classify_text(text)
        if atype is ArtifactType.DERIVATION:
            content = DerivationContent(raw_text=text, steps=split_steps(text))
        else:
            content = TheoryContent(text=text)
        return [ParsedArtifact(atype, content, {})]
