"""Generate a realistic, messy submissions zip for local testing.

Reproduces the ingestion problem from PROJECT_PLAN §3: nested folders,
inconsistent filenames, and mixed formats (PDF, .ipynb, .py, .png, .txt,
.docx) whose answers span correct / partial / wrong. Emits three artifacts
under ``--out``:

  <assignment>_submissions.zip   the upload the pipeline ingests
  <assignment>_manifest.json     ground truth: real names + per-file true type/question
  <assignment>_rubric.json       the rubric (PROJECT_PLAN §7.6 shape)

Usage:
    uv run python scripts/seed_synthetic_data.py --students 25 --out data/uploads
"""

from __future__ import annotations

import argparse
import io
import json
import random
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import nbformat  # noqa: E402
from docx import Document  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

ASSIGNMENT_KEY = "cs152-hw3"
COURSE_CODE = "cs152"
TITLE = "CPS Transformation and Continuations"

RUBRIC = {
    "assignment_id": ASSIGNMENT_KEY,
    "title": TITLE,
    "grading_backend": "local",
    "questions": [
        {
            "question_id": "q1",
            "type": "theory",
            "weight": 10,
            "prompt": "Explain call-by-name vs call-by-value with an example.",
            "rubric_criteria": [
                {"criterion": "correct definition of call-by-name", "points": 3},
                {"criterion": "correct definition of call-by-value", "points": 3},
                {"criterion": "example demonstrating the difference", "points": 4},
            ],
        },
        {
            "question_id": "q2",
            "type": "code",
            "weight": 20,
            "prompt": "Implement a CPS transformation for the given arithmetic AST.",
            "style_criteria": ["idiomatic Python", "handles edge cases"],
        },
        {
            "question_id": "q3",
            "type": "derivation",
            "weight": 15,
            "prompt": "Derive the fixed point of the factorial functional step by step.",
        },
        {
            "question_id": "q4",
            "type": "figure",
            "weight": 10,
            "prompt": "Plot measured runtime versus input size for your implementation.",
        },
    ],
}

FIRST = ["Ava", "Liam", "Noah", "Mia", "Ethan", "Zoe", "Kai", "Isla", "Omar", "Nina",
         "Leo", "Aria", "Ravi", "Sofia", "Jin", "Maya", "Diego", "Lena", "Ivan", "Priya",
         "Yara", "Marco", "Hana", "Theo", "Elsa"]
LAST = ["Chen", "Patel", "Kim", "Garcia", "Nguyen", "Lopez", "Singh", "Ali", "Rossi",
        "Cohen", "Ivanov", "Silva", "Okafor", "Tanaka", "Mensah", "Haddad", "Novak",
        "Reyes", "Dubois", "Costa", "Park", "Meyer", "Fofana", "Sato", "Ahmed"]

# Prose used for theory (q1); "wrong" variants included so graders have signal.
THEORY_TEXTS = [
    "Call-by-value evaluates the argument before the call and binds the resulting "
    "value to the parameter. Call-by-name delays evaluation, substituting the "
    "unevaluated expression and evaluating it at each use. For example, with a "
    "function that ignores its argument, call-by-name skips a diverging computation "
    "that call-by-value would run first.",
    "In call-by-value the argument is computed first, then passed. Call-by-name passes "
    "the expression unevaluated. They differ when the argument has side effects or does "
    "not terminate.",
    "Call by value and call by name are the same in practice; both just pass the "
    "argument to the function and then run it.",  # wrong
]

DERIV_TEXTS = [
    "Step 1: fact = fix(F) where F(f)(n) = if n = 0 then 1 else n * f(n-1).\n"
    "Step 2: fix(F) = F(fix(F)) by the fixed-point property.\n"
    "Step 3: expand F(fix(F))(n) = if n = 0 then 1 else n * fix(F)(n-1).\n"
    "Step 4: therefore fact(n) = n * fact(n-1) with fact(0) = 1.",
    "Step 1: define F(f)(n) = if n=0 then 1 else n*f(n-1).\n"
    "Step 2: assume fact is a fixed point, fact = F(fact).\n"
    "Step 3: substitute to get fact(n) = n * fact(n-1).",
]

CODE_TEXTS = [
    "def cps(ast, k):\n"
    "    if isinstance(ast, int):\n"
    "        return k(ast)\n"
    "    op, a, b = ast\n"
    "    return cps(a, lambda va: cps(b, lambda vb: k(apply(op, va, vb))))\n",
    "def cps(ast, k):\n"
    "    # incomplete: does not thread the continuation\n"
    "    if isinstance(ast, int):\n"
    "        return ast\n"
    "    return cps(ast[1], k) + cps(ast[2], k)\n",  # buggy
]


def make_pdf(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for line in _wrap(text, 90):
        c.drawString(50, y, line)
        y -= 16
        if y < 60:
            c.showPage()
            y = 780
    c.save()
    return buf.getvalue()


def make_docx(text: str) -> bytes:
    doc = Document()
    for para in text.split("\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_ipynb(code: str, md: str) -> bytes:
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell(md), nbformat.v4.new_code_cell(code)]
    return nbformat.writes(nb).encode()


def make_png(rng: random.Random) -> bytes:
    xs = [2**i for i in range(1, 8)]
    ys = [x * (1.0 + rng.uniform(-0.1, 0.1)) for x in xs]
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel("input size")
    ax.set_ylabel("runtime (ms)")
    ax.set_title("runtime vs input size")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            if len(line) + len(word) + 1 > width:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        out.append(line)
    return out


def _theory_name(rng: random.Random, qid: str) -> tuple[str, str]:
    fmt = rng.choice(["pdf", "docx", "txt"])
    clear = rng.random() < 0.5
    stem = f"{qid}" if clear else rng.choice(["answer", "writeup", "solution", "part1"])
    return f"{stem}.{fmt}", fmt


def build(students: int, seed: int, out: Path) -> dict:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"{ASSIGNMENT_KEY}_submissions.zip"
    manifest: dict = {"assignment_id": ASSIGNMENT_KEY, "course_code": COURSE_CODE,
                      "title": TITLE, "students": []}

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        used_ids: set[str] = set()
        for i in range(students):
            first = FIRST[i % len(FIRST)]
            last = LAST[(i * 7 + 3) % len(LAST)]
            canvas_id = str(100000 + rng.randint(0, 899999))
            while canvas_id in used_ids:
                canvas_id = str(100000 + rng.randint(0, 899999))
            used_ids.add(canvas_id)
            folder = f"{last}{first}_{canvas_id}"
            files: list[dict] = []

            # q1 theory (usually present)
            if rng.random() < 0.92:
                name, fmt = _theory_name(rng, "q1")
                text = rng.choice(THEORY_TEXTS)
                data = {"pdf": make_pdf, "docx": make_docx,
                        "txt": lambda t: t.encode()}[fmt](text)
                path = f"{folder}/{name}"
                zf.writestr(path, data)
                files.append({"path": path, "true_type": "theory", "true_question": "q1"})

            # q2 code (usually present) — nested a level sometimes
            if rng.random() < 0.9:
                use_nb = rng.random() < 0.5
                code = rng.choice(CODE_TEXTS)
                if use_nb:
                    clear = rng.random() < 0.5
                    name = "q2.ipynb" if clear else rng.choice(["notebook.ipynb", "hw3.ipynb"])
                    data = make_ipynb(code, "# Q2: CPS transformation")
                else:
                    clear = rng.random() < 0.5
                    name = "q2.py" if clear else rng.choice(["cps.py", "final.py", "solution.py"])
                    data = code.encode()
                sub = "code/" if rng.random() < 0.3 else ""
                path = f"{folder}/{sub}{name}"
                zf.writestr(path, data)
                files.append({"path": path, "true_type": "code", "true_question": "q2"})

            # q3 derivation
            if rng.random() < 0.8:
                fmt = rng.choice(["pdf", "txt"])
                text = rng.choice(DERIV_TEXTS)
                data = make_pdf(text) if fmt == "pdf" else text.encode()
                clear = rng.random() < 0.5
                name = (f"q3.{fmt}" if clear
                        else rng.choice([f"derivation.{fmt}", f"proof.{fmt}", f"part3.{fmt}"]))
                path = f"{folder}/{name}"
                zf.writestr(path, data)
                files.append({"path": path, "true_type": "derivation", "true_question": "q3"})

            # q4 figure
            if rng.random() < 0.8:
                clear = rng.random() < 0.5
                name = "q4.png" if clear else rng.choice(["plot.png", "scan.png", "figure.png"])
                path = f"{folder}/{name}"
                zf.writestr(path, make_png(rng))
                files.append({"path": path, "true_type": "figure", "true_question": "q4"})

            manifest["students"].append(
                {"display_name": f"{first} {last}", "canvas_id": canvas_id,
                 "folder": folder, "files": files}
            )

    (out / f"{ASSIGNMENT_KEY}_manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / f"{ASSIGNMENT_KEY}_rubric.json").write_text(json.dumps(RUBRIC, indent=2))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=25)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", default="data/uploads")
    args = parser.parse_args()

    manifest = build(args.students, args.seed, Path(args.out))
    total_files = sum(len(s["files"]) for s in manifest["students"])
    by_type: dict[str, int] = {}
    for s in manifest["students"]:
        for f in s["files"]:
            by_type[f["true_type"]] = by_type.get(f["true_type"], 0) + 1
    print(f"generated {len(manifest['students'])} submissions, {total_files} files")
    print("by true_type:", by_type)
    print(f"zip: {Path(args.out) / (ASSIGNMENT_KEY + '_submissions.zip')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
