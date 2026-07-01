import io

import nbformat
from docx import Document
from PIL import Image
from reportlab.pdfgen import canvas

from autograde_core.models import ArtifactType, CodeContent, TheoryContent
from services.parsers.registry import parse_file, select_parser


def _pdf(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for line in text.split("\n"):
        c.drawString(50, y, line)
        y -= 16
    c.save()
    return buf.getvalue()


def test_pdf_theory_vs_derivation() -> None:
    theory = parse_file("q1.pdf", _pdf("Call by value evaluates arguments first as prose."))
    assert theory[0].artifact_type is ArtifactType.THEORY
    assert isinstance(theory[0].content, TheoryContent)

    deriv = parse_file("q3.pdf", _pdf("Step 1: a = b\nStep 2: b = c\nStep 3: a = c"))
    assert deriv[0].artifact_type is ArtifactType.DERIVATION
    assert deriv[0].content.steps


def test_code_extracts_symbols() -> None:
    src = (
        b"import os\nfrom sys import argv\n\n"
        b"def cps(a, k):\n    return k(a)\n\n"
        b"if __name__ == '__main__':\n    cps(1, print)\n"
    )
    art = parse_file("cps.py", src)[0]
    assert art.artifact_type is ArtifactType.CODE
    assert isinstance(art.content, CodeContent)
    assert "cps" in art.content.functions
    assert any("import os" in imp for imp in art.content.imports)
    assert "__main__" in art.content.entry_points


def test_notebook_is_code() -> None:
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Q2"),
        nbformat.v4.new_code_cell("def f():\n    return 1\n"),
    ]
    art = parse_file("q2.ipynb", nbformat.writes(nb).encode())[0]
    assert art.artifact_type is ArtifactType.CODE
    assert "f" in art.content.functions


def test_docx_is_theory() -> None:
    doc = Document()
    doc.add_paragraph("Some prose answer about evaluation order.")
    buf = io.BytesIO()
    doc.save(buf)
    art = parse_file("answer.docx", buf.getvalue())[0]
    assert art.artifact_type is ArtifactType.THEORY


def test_png_is_figure() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buf, format="PNG")
    art = parse_file("plot.png", buf.getvalue())[0]
    assert art.artifact_type is ArtifactType.FIGURE
    assert art.content.image_ref == "plot.png"


def test_unknown_extension() -> None:
    art = parse_file("weird.xyz", b"\x00\x01binary")[0]
    assert art.artifact_type is ArtifactType.UNKNOWN


def test_registry_routing() -> None:
    assert select_parser("a.pdf").name == "pdf"
    assert select_parser("a.ipynb").name == "notebook"
    assert select_parser("a.py").name == "code"
    assert select_parser("a.PNG").name == "image"
    assert select_parser("a.rtf").name == "fallback"
