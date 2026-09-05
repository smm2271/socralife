#!/bin/sh
set -eu
snapshot=${1:?Usage: scripts/restore.sh SNAPSHOT_ID}
docker compose stop api worker
# Intentionally no restart trap: failure keeps personal data inaccessible.
docker compose --profile ops run --rm backup /ops/restore.sh "$snapshot"
docker compose run --rm --no-deps api python -m app.maintenance replay-deletions
docker compose start api worker
