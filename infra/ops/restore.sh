#!/bin/sh
# Invoked only while API and worker are stopped; see scripts/ops.ps1 or runbook.
set -eu
: "${RESTIC_REPOSITORY:?Configure remote RESTIC_REPOSITORY}"
: "${RESTIC_PASSWORD:?Configure RESTIC_PASSWORD}"
snapshot=${1:?Pass an explicit snapshot ID}
mkdir -p /restore-staging /current-deletions
cp -a /deletions/. /current-deletions/
restic restore "$snapshot" --target /restore-staging
test -f /restore-staging/snapshot/database.dump
test -d /restore-staging/snapshot/files
pg_restore --clean --if-exists --no-owner --dbname="$PGDATABASE" /restore-staging/snapshot/database.dump
# Fixed container volume roots; never accept a user supplied deletion path.
test "$(readlink -f /files)" = /files
find /files -mindepth 1 -delete
cp -a /restore-staging/snapshot/files/. /files/
cp -a /restore-staging/snapshot/deletions/. /deletions/
if [ -f /current-deletions/deletions.jsonl ]; then
    cat /current-deletions/deletions.jsonl >> /deletions/deletions.jsonl
fi
chown -R 10001:10001 /files /deletions
echo 'Snapshot restored. Run maintenance replay-deletions before restarting API/worker.'
