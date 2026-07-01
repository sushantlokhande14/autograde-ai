from uuid import UUID

from autograde_core.hashing import (
    artifact_id_for,
    sha256_bytes,
    student_hash,
    submission_id_for,
)


def test_student_hash_is_deterministic_and_sensitive() -> None:
    h1 = student_hash("cs152-hw3", "12345", secret="s")
    assert h1 == student_hash("cs152-hw3", "12345", secret="s")
    assert len(h1) == 64
    assert student_hash("cs152-hw3", "99999", secret="s") != h1
    assert student_hash("cs152-hw3", "12345", secret="other") != h1


def test_ids_are_stable_uuid5() -> None:
    sid = submission_id_for("cs152-hw3", "abc")
    assert sid == submission_id_for("cs152-hw3", "abc")
    assert isinstance(sid, UUID)

    aid = artifact_id_for(sid, "hw.py", "deadbeef")
    assert aid == artifact_id_for(sid, "hw.py", "deadbeef")
    assert aid != artifact_id_for(sid, "other.py", "deadbeef")
    assert aid != artifact_id_for(sid, "hw.py", "cafe")


def test_sha256_bytes() -> None:
    assert sha256_bytes(b"abc") == sha256_bytes(b"abc")
    assert len(sha256_bytes(b"abc")) == 64
