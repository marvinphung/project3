#!/usr/bin/env bash
set -euo pipefail

compose=(docker compose)

"${compose[@]}" ps --status running

curl --fail --silent --show-error \
  "http://127.0.0.1:${MOCK_NEWS_SOURCE_HOST_PORT:-18080}/health" |
  grep -q '^ok$'
curl --fail --silent --show-error \
  "http://127.0.0.1:${MOCK_NEWS_SOURCE_HOST_PORT:-18080}/rss.xml" |
  grep -q '<guid isPermaLink="false">transfer-1-v1</guid>'

"${compose[@]}" exec -T kafka \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic article.discovered.v1

smoke_message="phase0-smoke-$(date +%s)"
printf '%s\n' "$smoke_message" |
  "${compose[@]}" exec -T kafka \
    /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka:9092 \
    --topic phase0.infrastructure.smoke.v1

consumed=$(
  "${compose[@]}" exec -T kafka \
    /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 \
    --topic phase0.infrastructure.smoke.v1 \
    --from-beginning \
    --timeout-ms 10000
)
grep -q "$smoke_message" <<<"$consumed"

"${compose[@]}" exec -T mongodb mongosh --quiet --eval '
  if (!db.hello().isWritablePrimary) {
    throw new Error("MongoDB replica set is not writable");
  }
  const session = db.getMongo().startSession();
  session.startTransaction();
  session.getDatabase("footballpulse_article").phase0_smoke.insertOne(
    {_id: "transaction-check", checked_at: new Date()}
  );
  session.commitTransaction();
  session.endSession();
  db.getSiblingDB("footballpulse_article").phase0_smoke.deleteOne(
    {_id: "transaction-check"}
  );
'

"${compose[@]}" exec -T postgres psql \
  -U "${POSTGRES_USER:-footballpulse}" \
  -d "${POSTGRES_DB:-footballpulse}" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT schema_name FROM information_schema.schemata
      WHERE schema_name IN (
        'source_schema',
        'intelligence_schema',
        'ai_content_schema',
        'content_schema',
        'identity_schema'
      );"

"${compose[@]}" exec -T redis redis-cli \
  --no-auth-warning \
  -a "${REDIS_PASSWORD:-footballpulse-local-redis}" \
  ping |
  grep -q PONG

echo "FootballPulse Phase 0 infrastructure smoke test passed"
