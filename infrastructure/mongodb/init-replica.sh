#!/usr/bin/env bash
set -euo pipefail

if mongosh --host mongodb:27017 --quiet --eval "rs.status().ok" >/dev/null 2>&1; then
  echo "MongoDB replica set already initialized"
  exit 0
fi

mongosh --host mongodb:27017 --quiet --eval \
  "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'mongodb:27017'}]})"

for _ in $(seq 1 30); do
  if mongosh --host mongodb:27017 --quiet --eval \
    "quit(db.hello().isWritablePrimary ? 0 : 1)"; then
    echo "MongoDB replica set is writable"
    exit 0
  fi
  sleep 1
done

echo "MongoDB replica set did not become writable" >&2
exit 1
