#!/bin/sh
# Run from repository root. Schedule daily with cron; remote repository must exist.
set -eu
docker compose stop api worker
trap 'docker compose start api worker' EXIT
docker compose --profile ops run --rm backup /ops/backup.sh
