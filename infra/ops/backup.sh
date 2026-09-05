#!/bin/sh
set -eu
: "${RESTIC_REPOSITORY:?Configure remote RESTIC_REPOSITORY}"
: "${RESTIC_PASSWORD:?Configure RESTIC_PASSWORD}"
if [ "${STORAGE_PROVIDER:-local}" != local ]; then
    echo 'S3 objects require an operator-managed versioned bucket backup; this local snapshot job refuses incomplete backups.' >&2
    exit 1
fi
mkdir -p /snapshot
pg_dump --format=custom --no-owner --file=/snapshot/database.dump
cp -a /files /snapshot/files
cp -a /deletions /snapshot/deletions
restic backup /snapshot --tag socralife --host socralife
restic forget --tag socralife --keep-within 30d --prune
restic check
