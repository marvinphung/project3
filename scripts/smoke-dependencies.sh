#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

environment_file=".env.example"
if [[ -f .env ]]; then
  environment_file=".env"
fi

compose=(docker compose --env-file "$environment_file" --profile core)

"${compose[@]}" up -d --wait kafka mongodb postgres redis
"${compose[@]}" run --rm mongodb-init

"${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --if-not-exists \
  --topic footballpulse.wp11.smoke \
  --partitions 1 \
  --replication-factor 1

"${compose[@]}" exec -T mongodb mongosh --quiet --eval '
const session = db.getMongo().startSession();
const smokeDb = session.getDatabase("footballpulse_smoke");
smokeDb.transactions.deleteOne({_id: "wp11"});
session.startTransaction();
smokeDb.transactions.insertOne({_id: "wp11", verified: true});
session.commitTransaction();
if (!smokeDb.transactions.findOne({_id: "wp11"}).verified) { quit(1); }
smokeDb.transactions.deleteOne({_id: "wp11"});
print("MongoDB transaction committed");
'

"${compose[@]}" exec -T postgres psql \
  --username "${FOOTBALLPULSE_POSTGRES_USER:-footballpulse}" \
  --dbname "${FOOTBALLPULSE_POSTGRES_DB:-footballpulse}" \
  --tuples-only \
  --command "SELECT extversion FROM pg_extension WHERE extname = 'vector';"

"${compose[@]}" exec -T redis sh -c \
  'REDISCLI_AUTH="$FOOTBALLPULSE_REDIS_PASSWORD" redis-cli ping'

"${compose[@]}" ps
