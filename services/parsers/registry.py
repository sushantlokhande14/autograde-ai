"""Parser registry: pick a parser by filename and normalize a file."""

from __future__ import annotations

from services.parsers.base import ParsedArtifact, Parser
from services.parsers.code.parser import CodeParser
from services.parsers.fallback.parser import FallbackParser
from services.parsers.image.parser import ImageParser
from services.parsers.notebook.parser import NotebookParser
from services.parsers.pdf.parser import PdfParser

# Order matters: specific parsers first, catch-all fallback last.
PARSERS: list[Parser] = [
    PdfParser(),
    NotebookParser(),
    CodeParser(),
    ImageParser(),
    FallbackParser(),
]


def select_parser(filename: str) -> Parser:
    for parser in PARSERS:
        if parser.handles(filename):
            return parser
    return PARSERS[-1]


def parse_file(filename: str, data: bytes) -> list[ParsedArtifact]:
    return select_parser(filename).parse(filename, data)
