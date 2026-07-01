"""Generate a synthetic course-materials corpus for the RAG layer.

Eight topical markdown documents covering the four cs152-hw3 question topics,
two distractor documents (present in every real course folder, relevant to no
rubric question), and four reference answers flagged ``reference_answer: true``
so the leak-exclusion path is exercised. Emits a manifest with per-document
payload metadata and the ground-truth question mapping used by the retrieval
hit-rate test.

Usage:
    uv run python scripts/seed_course_materials.py --out data/materials
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ASSIGNMENT_KEY = "cs152-hw3"

# source filename -> (question_ids it grounds, reference_answer flag, content)
DOCS: dict[str, tuple[list[str], bool, str]] = {
    "lecture_evaluation_strategies.md": (
        ["q1"],
        False,
        """# Evaluation Strategies: Call-by-Value and Call-by-Name

Under call-by-value, the argument expression is evaluated exactly once, before
the function is entered, and the resulting value is bound to the parameter.
Every subsequent use of the parameter refers to that already-computed value.
This is the strategy of ML, Scheme, and Java.

Under call-by-name, the argument expression is substituted, unevaluated, into
the function body. It is evaluated anew each time the parameter is used, and
never evaluated if the parameter is unused. Algol 60 popularized this; lazy
languages refine it into call-by-need by memoizing the first evaluation.

## Divergence as the discriminating example

Consider `const(x, y) = x` applied as `const(1, loop())` where `loop()` never
terminates. Call-by-value diverges: it must evaluate `loop()` before entering
`const`. Call-by-name returns 1: the second argument is never used, so it is
never evaluated. Side effects give a second discriminator: if the argument
prints, call-by-name may print zero or many times, call-by-value exactly once.

## Cost model

Call-by-name can duplicate work when a parameter is used repeatedly; each use
re-evaluates the expression. Call-by-need shares the first result. Strictness
analysis lets compilers of lazy languages fall back to call-by-value where it
is safe, recovering predictable cost without changing observable behavior.
""",
    ),
    "textbook_lambda_calculus.md": (
        ["q1"],
        False,
        """# Reduction Orders in the Lambda Calculus

A redex is an application of an abstraction to an argument. Normal-order
reduction contracts the leftmost-outermost redex first; applicative-order
reduction contracts the leftmost-innermost redex first. Applicative order
corresponds to call-by-value: arguments are reduced before the call.
Normal order corresponds to call-by-name: the function is entered first.

The standardization theorem gives normal order its importance: if any
reduction sequence reaches a normal form, the normal-order sequence does.
Applicative order can diverge on terms that have a normal form, precisely
because it insists on evaluating arguments that the function will discard.

## Omega and K

Let omega = (\\x. x x)(\\x. x x), which reduces only to itself, and
K = \\x. \\y. x. The term K z omega has normal form z under normal order,
but applicative order loops on omega forever. This is the textbook witness
separating the two strategies.
""",
    ),
    "lecture_cps.md": (
        ["q2"],
        False,
        """# Continuation-Passing Style Transformation

A CPS transformation makes control flow explicit: every function receives an
extra argument, its continuation, and instead of returning, it calls that
continuation with the result. No function in CPS output ever returns; every
call is a tail call.

## Transforming an arithmetic AST

For an AST of integer literals and binary operations, the transformation is:
a literal `n` becomes `k(n)`; a node `(op, a, b)` becomes a CPS traversal of
`a` whose continuation receives `va`, then of `b` whose continuation receives
`vb`, finally calling `k(apply(op, va, vb))`. In Python:

    def cps(ast, k):
        if isinstance(ast, int):
            return k(ast)
        op, a, b = ast
        return cps(a, lambda va: cps(b, lambda vb: k(apply(op, va, vb))))

The evaluation order of operands is now syntactically fixed by the nesting of
continuations — the transformation chooses left-to-right here — which is why
compilers use CPS: order of effects becomes explicit and optimizable.

## Common implementation mistakes

Forgetting to thread the continuation through recursive calls (calling
`cps(a, k)` for both operands) evaluates operands with the final continuation
and loses the combination step. Returning values instead of calling `k`
reintroduces implicit control flow and breaks tail-call structure.
""",
    ),
    "textbook_continuations.md": (
        ["q2"],
        False,
        """# Continuations as First-Class Values

A continuation reifies "the rest of the computation" as a function. Operators
like call/cc capture the current continuation and hand it to the programmer;
CPS is the whole-program transformation that makes every continuation
explicit without needing runtime support.

CPS terms enjoy a strong invariant: all calls are tail calls, so a CPS
interpreter needs no call stack — an iterative loop with a current function
and argument suffices. This is the basis of stackless implementations and of
compilers (Rabbit, Orbit, SML/NJ) that use CPS as their intermediate form.

## Administrative redexes

Naive CPS transformations produce administrative redexes — beta-redexes
introduced by the transformation itself rather than the source program.
Higher-order (one-pass) CPS transformations contract these at transformation
time, producing compact output. When asked to CPS-transform by hand, the
expected output is usually the administratively-normalized form.
""",
    ),
    "lecture_fixed_points.md": (
        ["q3"],
        False,
        """# Fixed Points and Recursion

Recursion can be explained without self-reference: define a functional F that
takes "the recursive function so far" and returns an improved version, then
take the fixed point of F. For factorial:

    F(f)(n) = if n = 0 then 1 else n * f(n - 1)

A fixed point of F is a function fact with fact = F(fact). Unfolding once:
fact(n) = if n = 0 then 1 else n * fact(n - 1) — the familiar definition.

## Deriving the fixed point step by step

Step 1: postulate fact = fix(F), where fix satisfies fix(F) = F(fix(F)).
Step 2: apply the fixed-point property once: fact = F(fact).
Step 3: expand F at an argument n: fact(n) = if n = 0 then 1 else n * fact(n-1).
Step 4: verify the base case fact(0) = 1 and induct for n > 0.

The derivation is finite even though the unfolding is conceptually infinite;
each unfolding is invoked only as far as the argument demands, which is why
fix is definable in a lazy language directly and needs the eta-expanded Z
combinator under call-by-value.
""",
    ),
    "textbook_y_combinator.md": (
        ["q3"],
        False,
        """# The Y Combinator

Curry's Y combinator, Y = \\f. (\\x. f (x x)) (\\x. f (x x)), satisfies
Y F = F (Y F) for every term F: it manufactures fixed points syntactically.
Applying Y to the factorial functional yields a term that behaves exactly as
the recursive factorial, without any self-referential definition.

Under call-by-value, Y diverges — evaluating (x x) loops before F is ever
entered. The Z combinator eta-expands the self-application,
Z = \\f. (\\x. f (\\v. x x v)) (\\x. f (\\v. x x v)), delaying it behind a
lambda so the fixed point can be taken strictly.

## Uniqueness caveats

Fixed points of a functional need not be unique; the least fixed point in the
domain-theoretic order is the one computed by recursion. For factorial the
least fixed point is total on the naturals, so the distinction is invisible,
but functionals like F(f)(n) = f(n) have many fixed points, of which the
least is the everywhere-undefined function.
""",
    ),
    "lab_benchmarking.md": (
        ["q4"],
        False,
        """# Lab: Benchmarking and Runtime Plots

A runtime-versus-input-size plot answers one question: how does cost grow?
Measure wall-clock time for inputs spaced geometrically (n, 2n, 4n, ...), take
the median of at least five repetitions per size to suppress scheduler noise,
and plot size on the x-axis against time on the y-axis.

## What a good plot shows

Axis labels with units (input size; runtime in milliseconds), a marker per
measured point, and either a log-log scale — where a polynomial cost curve
becomes a straight line whose slope is the exponent — or a fitted reference
curve. Error bars or a shaded band communicate variance; a single unlabeled
jagged line communicates nothing.

Common faults: timing a single run (noise dominates), including JIT or cache
warm-up in the first measurement, plotting means over outlier-heavy samples
instead of medians, and truncating the y-axis to exaggerate differences.
""",
    ),
    "guide_matplotlib.md": (
        ["q4"],
        False,
        """# Plotting Measured Data

For measurement plots, prefer explicit figures: create a figure and axes,
plot x against y with markers, label both axes with units, add a title
stating what was measured, and save at a readable size.

    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot(sizes, times_ms, marker="o")
    ax.set_xlabel("input size")
    ax.set_ylabel("runtime (ms)")

Use `ax.set_xscale("log"); ax.set_yscale("log")` for growth-rate analysis.
When comparing implementations, plot them on the same axes with a legend;
when showing variance, use `ax.errorbar` or `ax.fill_between` on the
inter-quartile range. Export with `fig.savefig(path, dpi=150)` so the figure
is legible in a report.
""",
    ),
    "lecture_type_inference.md": (
        [],
        False,
        """# Hindley–Milner Type Inference (distractor)

Algorithm W infers principal types for the lambda calculus with let-
polymorphism. Unification solves equality constraints between types;
generalization quantifies type variables free in a let-bound body but not in
the environment. The occurs check prevents infinite types like a = a -> b.

Soundness states that well-typed programs do not go wrong; completeness of W
states that every typeable term receives its principal type. Neither topic is
assessed in this assignment; this handout accompanies a different week.
""",
    ),
    "syllabus_admin.md": (
        [],
        False,
        """# Course Administration (distractor)

Office hours are Tuesdays 2–4pm in ENG 283. Homework is due Fridays at 23:59
in the submission portal; the late policy allows three slip days across the
semester, applied automatically. Regrade requests open 24 hours after grades
are released and close one week later. The final exam is cumulative, closed
book, with one hand-written page of notes permitted.
""",
    ),
    "ref_q1_answer.md": (
        ["q1"],
        True,
        """# Reference Answer — q1

Call-by-value evaluates the argument once, before the call, binding the value;
call-by-name substitutes the unevaluated expression, evaluating at each use —
zero times if unused. Discriminating example: const(1, loop()) returns 1 under
call-by-name and diverges under call-by-value. Full credit requires both
definitions and an example whose observable behavior differs.
""",
    ),
    "ref_q2_answer.md": (
        ["q2"],
        True,
        """# Reference Answer — q2

    def cps(ast, k):
        if isinstance(ast, int):
            return k(ast)
        op, a, b = ast
        return cps(a, lambda va: cps(b, lambda vb: k(apply(op, va, vb))))

Continuation threaded through both operand traversals; literals call k
directly; combination happens innermost with left-to-right operand order.
""",
    ),
    "ref_q3_answer.md": (
        ["q3"],
        True,
        """# Reference Answer — q3

Step 1: F(f)(n) = if n = 0 then 1 else n * f(n-1). Step 2: fact = fix(F) and
fix(F) = F(fix(F)). Step 3: substitute: fact(n) = if n = 0 then 1 else
n * fact(n-1). Step 4: base case fact(0) = 1; induction gives totality.
""",
    ),
    "ref_q4_answer.md": (
        ["q4"],
        True,
        """# Reference Answer — q4

Geometrically spaced input sizes, median of repeated runs, labeled axes with
units, markers at measured points, log-log or fitted reference curve for
growth rate. Deductions for single-run timing, missing units, or truncated
axes.
""",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/materials")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest = {"assignment_id": ASSIGNMENT_KEY, "documents": []}
    for name, (question_ids, is_ref, content) in DOCS.items():
        (out / name).write_text(content, encoding="utf-8")
        manifest["documents"].append(
            {"source": name, "question_ids": question_ids, "reference_answer": is_ref}
        )
    (out / "materials_manifest.json").write_text(json.dumps(manifest, indent=2))

    topical = sum(1 for d in manifest["documents"] if d["question_ids"] and not d["reference_answer"])
    refs = sum(1 for d in manifest["documents"] if d["reference_answer"])
    distractors = sum(1 for d in manifest["documents"] if not d["question_ids"])
    print(f"wrote {len(manifest['documents'])} docs -> {out}")
    print(f"  topical: {topical}, reference answers: {refs}, distractors: {distractors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
