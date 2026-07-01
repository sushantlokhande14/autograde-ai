"""Shared parser interface and analysis helpers.

A parser turns one source file's bytes into one or more `ParsedArtifact`s (a
type + typed content + metadata). The registry (registry.py) picks a parser by
filename; the ingestion worker and the gRPC servicer both go through it.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from autograde_core.models import ArtifactContent, ArtifactType


@dataclass
class ParsedArtifact:
    artifact_type: ArtifactType
    content: ArtifactContent
    metadata: dict = field(default_factory=dict)


class Parser(ABC):
    name: str

    @abstractmethod
    def handles(self, filename: str) -> bool:
        ...

    @abstractmethod
    def parse(self, filename: str, data: bytes) -> list[ParsedArtifact]:
        ...


_STEP_RE = re.compile(r"^\s*(step\s*\d|\(\d+\)|\d+[\.\)])", re.IGNORECASE | re.MULTILINE)


def classify_text(text: str) -> ArtifactType:
    """Distinguish a step-by-step derivation from prose theory.

    Derivation if the text reads as enumerated steps that manipulate equations;
    otherwise theory. Deterministic so it is testable against ground truth.
    """
    steps = _STEP_RE.findall(text)
    if len(steps) >= 2 and "=" in text:
        return ArtifactType.DERIVATION
    return ArtifactType.THEORY


def split_steps(text: str) -> list[str]:
    """Extract enumerated step lines from a derivation."""
    return [line.strip() for line in text.splitlines() if _STEP_RE.match(line)]


def analyze_python(source: str) -> tuple[list[str], list[str], list[str]]:
    """Return (imports, function names, entry points) via tree-sitter.

    Best-effort: on any parse failure returns empty lists so ingestion never
    dies on a malformed file.
    """
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser as TSParser

        parser = TSParser(Language(tspython.language()))
        tree = parser.parse(source.encode())
    except Exception:  # noqa: BLE001
        return [], [], []

    imports: list[str] = []
    functions: list[str] = []
    entry_points: list[str] = []

    def text(node) -> str:
        return source.encode()[node.start_byte : node.end_byte].decode(errors="replace")

    def walk(node) -> None:
        if node.type in ("import_statement", "import_from_statement"):
            imports.append(text(node).strip())
        elif node.type == "function_definition":
            name = node.child_by_field_name("name")
            if name is not None:
                functions.append(text(name))
        elif node.type == "if_statement" and "__name__" in text(node) and "__main__" in text(node):
            entry_points.append("__main__")
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return imports, functions, entry_points
