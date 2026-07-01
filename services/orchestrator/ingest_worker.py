"""Ingestion worker: artifact.registered → parse → persist → map.

Consumes ``artifact.registered`` events (emitted by the Router), fetches the
raw file, normalizes it through the parser registry, stores the canonical
artifact JSON in MinIO, upserts ``grading.artifacts``, emits
``artifact.parsed``, then runs the QuestionMapper and emits ``question.mapped``
(or leaves the artifact gated for review).

This module is the Phase 3 seam: each step here becomes a Temporal activity;
the Kafka loop in ``run()`` is replaced by workflow dispatch with no logic
churn. Processing is idempotent — artifact ids are deterministic and writes
are upserts — so Kafka replay cannot double-ingest.
"""

from __future__ import annotations

import structlog

from autograde_core import storage
from autograde_core.events import Topic, consume, get_consumer, get_producer, publish
from autograde_core.hashing import artifact_id_for
from autograde_core.models import Artifact as ArtifactModel
from autograde_core.models import Rubric
from autograde_db import repository as repo
from autograde_db.models import Assignment
from autograde_db.session import session_scope
from autograde_llm import LLMClient
from services.parsers.registry import parse_file
from services.question_mapper.mapper import excerpt_for, map_artifact

log = structlog.get_logger()

_rubric_cache: dict[str, Rubric] = {}


def _rubric_for(assignment_key: str) -> Rubric | None:
    if assignment_key in _rubric_cache:
        return _rubric_cache[assignment_key]
    from autograde_core.hashing import assignment_id_for

    with session_scope() as session:
        row = session.get(Assignment, assignment_id_for(assignment_key))
        if row is None:
            return None
        rubric = Rubric.model_validate(row.rubric)
    _rubric_cache[assignment_key] = rubric
    return rubric


def process_registration(event: dict, *, client: LLMClient | None = None) -> list[dict]:
    """Handle one artifact.registered event. Returns per-artifact summaries."""
    from uuid import UUID

    source_file: str = event["source_file"]          # <assignment>/<student_hash>/<rel>
    submission_id = UUID(event["submission_id"])
    filename: str = event["filename"]
    sha256: str = event["sha256"]
    assignment_key, student_hash, *_ = source_file.split("/")

    rubric = _rubric_for(assignment_key)
    data = storage.get_bytes("raw-submissions", source_file)
    parsed = parse_file(filename, data)

    producer = get_producer()
    results: list[dict] = []
    with session_scope() as session:
        for index, part in enumerate(parsed):
            id_source = source_file if index == 0 else f"{source_file}#{index}"
            artifact_id = artifact_id_for(submission_id, id_source, sha256)

            mapping = None
            if rubric is not None:
                mapping = map_artifact(
                    filename=filename,
                    artifact_type=part.artifact_type,
                    text_excerpt=excerpt_for(part.content.model_dump()),
                    rubric=rubric,
                    client=client,
                )

            content_ref = f"{assignment_key}/{student_hash}/{artifact_id}.json"
            model = ArtifactModel(
                artifact_id=artifact_id,
                submission_id=submission_id,
                source_file=source_file,
                artifact_type=part.artifact_type,
                question_id=mapping.question_id if mapping and not mapping.needs_review else None,
                question_mapping_confidence=mapping.confidence if mapping else None,
                content_ref=content_ref,
                content=part.content,
                metadata=part.metadata,
            )
            storage.put_json("normalized-artifacts", content_ref, model.model_dump(mode="json"))
            repo.upsert_artifact(
                session,
                artifact_id=artifact_id,
                submission_id=submission_id,
                source_file=source_file,
                artifact_type=part.artifact_type.value,
                content_ref=content_ref,
                question_id=model.question_id,
                confidence=model.question_mapping_confidence,
                metadata=part.metadata,
            )

            publish(
                producer,
                Topic.ARTIFACT_PARSED,
                key=str(submission_id),
                value={
                    "artifact_id": str(artifact_id),
                    "submission_id": str(submission_id),
                    "artifact_type": part.artifact_type.value,
                    "content_ref": content_ref,
                },
            )
            if mapping is not None and not mapping.needs_review:
                publish(
                    producer,
                    Topic.QUESTION_MAPPED,
                    key=str(submission_id),
                    value={
                        "artifact_id": str(artifact_id),
                        "question_id": mapping.question_id,
                        "confidence": mapping.confidence,
                        "method": mapping.method,
                    },
                )

            results.append(
                {
                    "artifact_id": str(artifact_id),
                    "artifact_type": part.artifact_type.value,
                    "question_id": mapping.question_id if mapping else None,
                    "confidence": mapping.confidence if mapping else None,
                    "method": mapping.method if mapping else None,
                    "needs_review": mapping.needs_review if mapping else True,
                }
            )
    producer.flush(10)
    return results


def run(
    *,
    group: str = "ingestion-worker",
    max_events: int | None = None,
    idle_timeout_s: float | None = None,
    client: LLMClient | None = None,
) -> int:
    """Kafka loop: consume artifact.registered until max_events or idle timeout."""
    consumer = get_consumer(group, [Topic.ARTIFACT_REGISTERED])
    processed = 0
    try:
        for event in consume(consumer, timeout=1.0, idle_timeout=idle_timeout_s):
            processed += 1
            try:
                results = process_registration(event, client=client)
                log.info("ingested", source=event.get("source_file"), artifacts=len(results))
            except Exception as exc:  # noqa: BLE001 — fail isolated, not loud-crash the batch
                log.error("ingest_failed", source=event.get("source_file"), error=str(exc))
            if max_events is not None and processed >= max_events:
                break
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
    return processed


if __name__ == "__main__":
    run()
