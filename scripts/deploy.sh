#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

timeout_seconds=300
skip_backup=false
pull_images=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-backup) skip_backup=true ;;
        --pull) pull_images=true ;;
        --timeout) shift; timeout_seconds=${1:?--timeout requires seconds} ;;
        *) echo "Usage: $0 [--skip-backup] [--pull] [--timeout SECONDS]" >&2; exit 2 ;;
    esac
    shift
done

command -v docker >/dev/null 2>&1 || { echo 'Docker CLI not found.' >&2; exit 1; }
sh scripts/validate-env.sh --production
docker version >/dev/null
docker network inspect npm_default >/dev/null 2>&1 || { echo 'Required external Docker network npm_default does not exist.' >&2; exit 1; }
docker compose config --quiet

env_value() {
    awk -F= -v wanted="$1" '$1 == wanted { value=substr($0,index($0,"=")+1); gsub(/^[[:space:]]+|[[:space:]]+$/, "", value); print value; exit }' .env
}

existing_api=$(docker compose ps -q api 2>/dev/null || true)
if [ "$skip_backup" = false ] && [ -n "$existing_api" ] && [ -n "$(env_value RESTIC_REPOSITORY)" ] && [ -n "$(env_value RESTIC_PASSWORD)" ]; then
    sh scripts/backup.sh
elif [ "$skip_backup" = false ] && [ -n "$existing_api" ]; then
    echo 'WARNING: skipping pre-deployment backup because RESTIC_REPOSITORY is not configured.' >&2
fi

if [ "$pull_images" = true ]; then
    docker compose pull db clamav caddy
fi
docker compose build --pull api frontend

echo 'Checking configured chat and embedding endpoints from the application container...'
docker compose run --rm --no-deps api python -c "import os, urllib.request; pairs=[('CHAT_BASE_URL','CHAT_API_KEY'),('EMBEDDING_BASE_URL','EMBEDDING_API_KEY')]; [(lambda r: urllib.request.urlopen(r, timeout=10).close())(urllib.request.Request(os.environ[u].rstrip('/') + '/models', headers={'Authorization':'Bearer ' + os.environ[k]})) for u,k in pairs]"

docker compose up -d db clamav

wait_for_health() {
    service=$1
    deadline=$(( $(date +%s) + timeout_seconds ))
    while :; do
        container_id=$(docker compose ps -q "$service")
        state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)
        [ "$state" = healthy ] && return 0
        if [ "$(date +%s)" -ge "$deadline" ]; then
            docker compose ps
            docker compose logs --tail=100 "$service"
            echo "$service did not become healthy within ${timeout_seconds}s." >&2
            return 1
        fi
        sleep 3
    done
}

wait_for_health db
wait_for_health clamav
docker compose run --rm migrate
docker compose up -d api worker frontend caddy
wait_for_health api
wait_for_health caddy

docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5)"
docker compose exec -T caddy wget -qO- http://127.0.0.1/api/v1/health >/dev/null
docker compose ps
echo 'SocraLife is ready on Docker network npm_default at http://socralife-caddy:80.'
