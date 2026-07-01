from autograde_rag.chunk import chunk_text

DOC = """# Section One

First paragraph about evaluation strategies with enough words to matter.

## Section Two

Second paragraph about continuations and control flow made explicit.
"""


def test_chunking_is_deterministic() -> None:
    a = chunk_text("doc.md", DOC)
    b = chunk_text("doc.md", DOC)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert len(a) == 2  # one chunk per heading section at this size


def test_ids_change_with_source_and_content() -> None:
    a = chunk_text("doc.md", DOC)
    renamed = chunk_text("other.md", DOC)
    edited = chunk_text("doc.md", DOC.replace("continuations", "coroutines"))
    assert {c.chunk_id for c in a}.isdisjoint({c.chunk_id for c in renamed})
    assert [c.chunk_id for c in a] != [c.chunk_id for c in edited]


def test_headings_prefix_chunk_text() -> None:
    chunks = chunk_text("doc.md", DOC)
    assert chunks[0].text.startswith("Section One")
    assert chunks[1].heading == "Section Two"


def test_long_section_splits_with_overlap() -> None:
    body = " ".join(f"word{i}" for i in range(900))
    chunks = chunk_text("long.md", f"# H\n\n{body}", target_words=400, overlap_words=50)
    assert len(chunks) == 3
    # consecutive windows share the overlap region
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert first_words[-50:] == second_words[1:51]  # [0] is the heading prefix


def test_metadata_propagates() -> None:
    chunks = chunk_text("d.md", DOC, metadata={"question_ids": ["q1"], "reference_answer": True})
    assert all(c.metadata["question_ids"] == ["q1"] for c in chunks)
    assert all(c.metadata["reference_answer"] for c in chunks)


def test_empty_input() -> None:
    assert chunk_text("e.md", "") == []
    assert chunk_text("e.md", "\n\n\n") == []
