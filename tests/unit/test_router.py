from services.router.router import extract_canvas_id, group_by_student


def test_extract_canvas_id() -> None:
    assert extract_canvas_id("GarciaAva_915965") == "915965"
    assert extract_canvas_id("Smith_1234") == "1234"
    assert extract_canvas_id("no_digits_here") is None


def test_group_by_student() -> None:
    names = ["A_1234/q1.pdf", "A_1234/code/x.py", "B_5678/q2.py", "root.txt", "dir/"]
    groups = group_by_student(names)
    assert groups["A_1234"] == ["A_1234/q1.pdf", "A_1234/code/x.py"]
    assert groups["B_5678"] == ["B_5678/q2.py"]
    assert "root.txt" in groups[""]
    assert "dir/" not in [p for ps in groups.values() for p in ps]
