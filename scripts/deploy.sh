#!/bin/sh
set -eu
# Deploy current checked-out revision. First deployment uses compose up directly.
sh scripts/backup.sh
docker compose stop api worker
docker compose build api frontend
docker compose run --rm migrate
docker compose up -d --no-deps api worker frontend caddy
docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5)"
