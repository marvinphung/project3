#!/usr/bin/env bash
set -euo pipefail

KAFKA_TOPICS=/opt/kafka/bin/kafka-topics.sh
BOOTSTRAP_SERVER=kafka:9092

create_topic() {
  local topic=$1
  local partitions=$2
  local retention_ms=$3

  "$KAFKA_TOPICS" \
    --bootstrap-server "$BOOTSTRAP_SERVER" \
    --create \
    --if-not-exists \
    --topic "$topic" \
    --partitions "$partitions" \
    --replication-factor 1 \
    --config "retention.ms=$retention_ms"
}

create_topic article.discovered.v1 3 604800000
create_topic article.discovered.retry.v1 3 604800000
create_topic article.discovered.dlq.v1 1 2592000000
create_topic phase0.infrastructure.smoke.v1 1 86400000

"$KAFKA_TOPICS" --bootstrap-server "$BOOTSTRAP_SERVER" --list
