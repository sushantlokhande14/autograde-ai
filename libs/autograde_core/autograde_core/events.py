"""Kafka (Redpanda in dev) event helpers.

Small conveniences over confluent-kafka: topic names in one place, JSON
publish, and a consumer factory. Events are plain JSON dicts keyed for ordering
per PROJECT_PLAN §7.2.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from confluent_kafka import Consumer, Message, Producer

from autograde_core.config import get_settings


class Topic:
    SUBMISSION_UPLOADED = "submission.uploaded"
    ARTIFACT_REGISTERED = "artifact.registered"
    ARTIFACT_PARSED = "artifact.parsed"
    QUESTION_MAPPED = "question.mapped"
    GRADE_REQUESTED = "grade.requested"
    GRADE_COMPLETED = "grade.completed"
    REVIEW_REQUESTED = "review.requested"
    REVIEW_COMPLETED = "review.completed"
    EXPORT_READY = "export.ready"


def get_producer() -> Producer:
    return Producer({"bootstrap.servers": get_settings().kafka_brokers})


def publish(producer: Producer, topic: str, key: str, value: dict[str, Any]) -> None:
    producer.produce(topic, key=key, value=json.dumps(value).encode())
    producer.poll(0)


def get_consumer(group: str, topics: list[str], from_beginning: bool = True) -> Consumer:
    consumer = Consumer(
        {
            "bootstrap.servers": get_settings().kafka_brokers,
            "group.id": group,
            "auto.offset.reset": "earliest" if from_beginning else "latest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe(topics)
    return consumer


def consume(consumer: Consumer, timeout: float = 1.0) -> Iterator[dict[str, Any]]:
    """Yield decoded JSON payloads until interrupted. Skips messages on error."""
    while True:
        msg: Message | None = consumer.poll(timeout)
        if msg is None:
            continue
        if msg.error():
            continue
        yield json.loads(msg.value())
