#!/usr/bin/env bash
# Autograde AI — create Kafka topics on the dev Redpanda broker.
# Idempotent: re-running is a no-op for topics that already exist.
# Topic list and partition counts match design spec §7.2 (dev scale).
set -euo pipefail

BROKER="${KAFKA_BROKERS:-localhost:9092}"
RPK=(docker exec autograde-redpanda rpk topic --brokers redpanda:29092)

echo "Creating topics on ${BROKER} ..."

create() {
    local name="$1" partitions="$2"
    if "${RPK[@]}" create "$name" -p "$partitions" 2>/dev/null; then
        echo "  created ${name} (${partitions} partitions)"
    else
        echo "  exists  ${name}"
    fi
}

create submission.uploaded 4
create artifact.registered 8
create artifact.parsed     8
create question.mapped     4
create grade.requested     8
create grade.completed     8
create review.requested    4
create review.completed    4
create export.ready        2

echo "Done. Current topics:"
"${RPK[@]}" list
