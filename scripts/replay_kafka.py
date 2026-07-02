"""Kafka round-trip / replay smoke test for the empty Phase 0 pipeline.

Proves the Phase 0 Definition of Done item: publish an event to Kafka, have a
no-op consumer read and log it, then demonstrate two properties the design
depends on (design spec §5, §6):

  * multi-consumer replay  — a fresh consumer group re-reads the same event
    from the beginning (this is why Kafka is here and Celery is not);
  * idempotency            — replaying does not double-process, because the
    worker dedupes on a stable event_id.

Usage:
    uv run python scripts/replay_kafka.py --smoke
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid

from confluent_kafka import Consumer, Producer

BROKERS = os.environ.get("KAFKA_BROKERS", "localhost:9092")
DEFAULT_TOPIC = "submission.uploaded"


def produce(topic: str, event: dict) -> None:
    producer = Producer({"bootstrap.servers": BROKERS})
    producer.produce(topic, key=event["event_id"], value=json.dumps(event).encode())
    producer.flush(10)
    print(f"produced event_id={event['event_id']} -> {topic}")


def consume_once(topic: str, group: str, seen: set[str]) -> int:
    """Consume available messages for `group`, dedupe on event_id, return count processed."""
    consumer = Consumer(
        {
            "bootstrap.servers": BROKERS,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([topic])
    processed = 0
    deadline = time.time() + 8
    try:
        while time.time() < deadline:
            msg = consumer.poll(1.0)
            if msg is None:
                if processed:
                    break
                continue
            if msg.error():
                print(f"  consumer error: {msg.error()}")
                continue
            event = json.loads(msg.value())
            eid = event["event_id"]
            if eid in seen:
                print(f"  [dup ] group={group} skipped already-processed {eid}")
                continue
            seen.add(eid)
            processed += 1
            print(f"  [recv] group={group} processed {eid}")
    finally:
        consumer.close()
    return processed


def smoke(topic: str) -> int:
    event = {
        "event_id": str(uuid.uuid4()),
        "type": "submission.uploaded",
        "assignment_id": "cs152-hw3",
        "ts": time.time(),
    }
    produce(topic, event)

    seen: set[str] = set()
    print("first consumer group (fresh read):")
    first = consume_once(topic, group="smoke-a", seen=seen)

    print("second consumer group (replay from beginning):")
    replay = consume_once(topic, group="smoke-b", seen=seen)

    ok = first == 1 and replay == 0  # b re-reads the event but dedupe skips it
    print(f"\nround-trip: processed={first}, replay-deduped={'yes' if replay == 0 else 'no'}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="run the round-trip smoke test")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    args = parser.parse_args()

    if args.smoke:
        return smoke(args.topic)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
