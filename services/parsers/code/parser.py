"""Code parser: tree-sitter extraction of imports, functions, entry points."""

from __future__ import annotations

from autograde_core.models import ArtifactType, CodeContent
from services.parsers.base import ParsedArtifact, Parser, analyze_python


class CodeParser(Parser):
    name = "code"

    def handles(self, filename: str) -> bool:
        return filename.lower().endswith(".py")

    def parse(self, filename: str, data: bytes) -> list[ParsedArtifact]:
        source = data.decode("utf-8", errors="replace")
        imports, functions, entry_points = analyze_python(source)
        content = CodeContent(
            language="python",
            source=source,
            imports=imports,
            functions=functions,
            entry_points=entry_points,
        )
        return [ParsedArtifact(ArtifactType.CODE, content, {"lines": source.count(chr(10)) + 1})]
