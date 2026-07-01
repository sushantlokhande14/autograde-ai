"""Notebook parser: nbformat cell split, Python analysis of code cells."""

from __future__ import annotations

import nbformat

from autograde_core.models import ArtifactType, CodeContent
from services.parsers.base import ParsedArtifact, Parser, analyze_python


class NotebookParser(Parser):
    name = "notebook"

    def handles(self, filename: str) -> bool:
        return filename.lower().endswith(".ipynb")

    def parse(self, filename: str, data: bytes) -> list[ParsedArtifact]:
        nb = nbformat.reads(data.decode("utf-8", errors="replace"), as_version=4)
        code_cells = [c.source for c in nb.cells if c.cell_type == "code"]
        markdown_cells = [c.source for c in nb.cells if c.cell_type == "markdown"]
        source = "\n\n".join(code_cells)
        imports, functions, entry_points = analyze_python(source)
        content = CodeContent(
            language="python",
            source=source,
            imports=imports,
            functions=functions,
            entry_points=entry_points,
        )
        meta = {"code_cells": len(code_cells), "markdown_cells": len(markdown_cells)}
        return [ParsedArtifact(ArtifactType.CODE, content, meta)]
