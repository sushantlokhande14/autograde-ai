"""Deterministic text chunking.

Split on markdown headings first, then pack paragraphs into ~target_words
windows with overlap. Chunk ids are uuid5 over (source, seq, text hash) so
re-indexing the same document upserts the same points — no duplicates, ever.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, UUID, uuid5

_CHUNK_NS = uuid5(NAMESPACE_URL, "autograde-ai:chunk")

TARGET_WORDS = 350
OVERLAP_WORDS = 50

_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)


@dataclass
class Chunk:
    chunk_id: UUID
    source: str
    seq: int
    text: str
    heading: str | None = None
    metadata: dict = field(default_factory=dict)


def _sections(text: str) -> list[tuple[str | None, str]]:
    """Split markdown into (heading, body) sections; None heading for preamble."""
    lines = text.splitlines()
    sections: list[tuple[str | None, list[str]]] = []
    current: tuple[str | None, list[str]] = (None, [])
    for line in lines:
        if _HEADING_RE.match(line):
            if current[1] and any(s.strip() for s in current[1]):
                sections.append(current)
            current = (line.lstrip("# ").strip(), [])
        else:
            current[1].append(line)
    if current[1] and any(s.strip() for s in current[1]):
        sections.append(current)
    return [(h, "\n".join(body).strip()) for h, body in sections]


def _pack(words: list[str], target: int, overlap: int) -> list[list[str]]:
    if len(words) <= target:
        return [words] if words else []
    windows: list[list[str]] = []
    start = 0
    while start < len(words):
        end = min(start + target, len(words))
        windows.append(words[start:end])
        if end == len(words):
            break
        start = end - overlap
    return windows


def chunk_text(
    source: str,
    text: str,
    *,
    target_words: int = TARGET_WORDS,
    overlap_words: int = OVERLAP_WORDS,
    metadata: dict | None = None,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    seq = 0
    for heading, body in _sections(text):
        for window in _pack(body.split(), target_words, overlap_words):
            piece = " ".join(window)
            digest = hashlib.sha256(piece.encode()).hexdigest()
            chunks.append(
                Chunk(
                    chunk_id=uuid5(_CHUNK_NS, f"{source}:{seq}:{digest}"),
                    source=source,
                    seq=seq,
                    text=piece if heading is None else f"{heading}\n{piece}",
                    heading=heading,
                    metadata=dict(metadata or {}),
                )
            )
            seq += 1
    return chunks
