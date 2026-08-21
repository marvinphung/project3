#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

environment_file=".env.example"
if [[ -f .env ]]; then
  environment_file=".env"
fi

compose=(docker compose --env-file "$environment_file" -f docker-compose.v2.yml)

"${compose[@]}" up -d --wait kafka mongodb
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

"${compose[@]}" ps
