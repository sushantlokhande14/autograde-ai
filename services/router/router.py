"""Router: turn an uploaded zip into per-student registrations.

Deterministic (no LLM). Groups files by their top-level folder, extracts the
Canvas id, computes the student hash, writes the identity and submission rows,
copies each raw file into ``raw-submissions/``, and (optionally) publishes an
``artifact.registered`` event per file for the parser pool to consume.
"""

from __future__ import annotations

import mimetypes
import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from uuid import UUID

from autograde_core import storage
from autograde_core.events import Topic, get_producer, publish
from autograde_core.hashing import (
    assignment_id_for,
    sha256_bytes,
    student_hash,
    submission_id_for,
)
from autograde_core.models import Rubric
from autograde_db import repository as repo
from autograde_db.session import session_scope

_CANVAS_RE = re.compile(r"_(\d{4,})(?:$|/)")


@dataclass
class Registration:
    submission_id: UUID
    student_hash: str
    source_file: str          # raw-submissions/ key
    original_path: str        # path inside the upload
    filename: str
    sha256: str


@dataclass
class RouteResult:
    registrations: list[Registration] = field(default_factory=list)
    unrouted: list[str] = field(default_factory=list)


def extract_canvas_id(folder: str) -> str | None:
    m = _CANVAS_RE.search(folder + "/")
    return m.group(1) if m else None


def group_by_student(names: list[str]) -> dict[str, list[str]]:
    """Group file paths by their top-level folder. Root-level files -> ''."""
    groups: dict[str, list[str]] = {}
    for name in names:
        if name.endswith("/"):
            continue
        top = name.split("/", 1)[0] if "/" in name else ""
        groups.setdefault(top, []).append(name)
    return groups


def route(
    zip_bytes: bytes,
    *,
    assignment_key: str,
    roster: dict[str, str],
    rubric: Rubric | None = None,
    publish_events: bool = False,
) -> RouteResult:
    assignment_uuid = assignment_id_for(assignment_key)
    result = RouteResult()

    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf, session_scope() as session:
        if rubric is not None:
            repo.upsert_assignment(
                session,
                assignment_uuid=assignment_uuid,
                course_code=assignment_key.split("-")[0],
                title=rubric.title,
                rubric=rubric.model_dump(),
                grading_config={},
            )

        for folder, paths in group_by_student(zf.namelist()).items():
            canvas_id = extract_canvas_id(folder)
            if canvas_id is None:
                result.unrouted.extend(paths)
                continue

            sh = student_hash(assignment_key, canvas_id)
            sid = submission_id_for(assignment_key, sh)
            repo.upsert_identity(
                session,
                student_hash=sh,
                assignment_uuid=assignment_uuid,
                display_name=roster.get(canvas_id, folder),
                canvas_id=canvas_id,
            )
            repo.upsert_submission(
                session, submission_id=sid, assignment_uuid=assignment_uuid, student_hash=sh
            )

            for path in paths:
                data = zf.read(path)
                digest = sha256_bytes(data)
                rel = path.split("/", 1)[1] if "/" in path else path
                key = f"{assignment_key}/{sh}/{rel}"
                content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
                storage.put_bytes("raw-submissions", key, data, content_type)
                result.registrations.append(
                    Registration(
                        submission_id=sid,
                        student_hash=sh,
                        source_file=key,
                        original_path=path,
                        filename=rel.rsplit("/", 1)[-1],
                        sha256=digest,
                    )
                )

    if publish_events:
        producer = get_producer()
        for reg in result.registrations:
            publish(
                producer,
                Topic.ARTIFACT_REGISTERED,
                key=str(reg.submission_id),
                value={
                    "submission_id": str(reg.submission_id),
                    "source_file": reg.source_file,
                    "filename": reg.filename,
                    "sha256": reg.sha256,
                },
            )
        producer.flush(10)

    return result
