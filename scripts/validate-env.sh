#!/bin/sh
set -eu

production_requested=false
if [ "${1:-}" = "--production" ]; then
    production_requested=true
elif [ "$#" -gt 0 ]; then
    echo "Usage: $0 [--production]" >&2
    exit 2
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$repo_dir/.env"
[ -f "$env_file" ] || { echo 'Missing .env. Copy .env.example to .env first.' >&2; exit 1; }
if find "$env_file" -perm /077 -print -quit | grep -q .; then
    echo '.env must not be readable or writable by group/others; run chmod 600 .env.' >&2
    exit 1
fi

env_value() {
    awk -v wanted="$1" '
        /^[[:space:]]*#/ { next }
        {
            line=$0
            sub(/^[[:space:]]*/, "", line)
            eq=index(line, "=")
            if (!eq) next
            key=substr(line, 1, eq-1)
            gsub(/[[:space:]]/, "", key)
            if (key != wanted) next
            value=substr(line, eq+1)
            sub(/^[[:space:]]*/, "", value)
            sub(/[[:space:]]*$/, "", value)
            if ((substr(value,1,1)=="\"" && substr(value,length(value),1)=="\"") ||
                (substr(value,1,1)=="\047" && substr(value,length(value),1)=="\047")) {
                value=substr(value,2,length(value)-2)
            }
            print value
            exit
        }
    ' "$env_file"
}

require_value() {
    value=$(env_value "$1")
    [ -n "$value" ] || { echo "Missing required .env value: $1" >&2; exit 1; }
}

require_value POSTGRES_PASSWORD
require_value SECRET_KEY
secret_key=$(env_value SECRET_KEY)
[ "${#secret_key}" -ge 32 ] || { echo 'SECRET_KEY must contain at least 32 characters.' >&2; exit 1; }

environment=$(env_value ENVIRONMENT)
if [ "$production_requested" = true ] || [ "$environment" = production ]; then
    [ "$(env_value ENVIRONMENT)" = production ] || { echo 'Production deployment requires ENVIRONMENT=production.' >&2; exit 1; }
    [ "$(env_value ENABLE_DEV_AUTH)" != true ] || { echo 'ENABLE_DEV_AUTH=true is forbidden in production.' >&2; exit 1; }
    [ "$(env_value AI_PROVIDER)" = compatible ] || { echo 'Production requires AI_PROVIDER=compatible.' >&2; exit 1; }
    [ "$(env_value STORAGE_PROVIDER)" = local ] || { echo 'This deployment requires STORAGE_PROVIDER=local.' >&2; exit 1; }
    for name in APP_ORIGIN GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_REDIRECT_URI CHAT_BASE_URL CHAT_MODEL CHAT_API_KEY EMBEDDING_BASE_URL EMBEDDING_MODEL EMBEDDING_API_KEY; do
        require_value "$name"
    done
    case "$(env_value APP_ORIGIN)" in https://*) ;; *) echo 'Production APP_ORIGIN must use https://.' >&2; exit 1;; esac
    case "$(env_value GOOGLE_REDIRECT_URI)" in https://*) ;; *) echo 'Production GOOGLE_REDIRECT_URI must use https://.' >&2; exit 1;; esac

    restic_repository=$(env_value RESTIC_REPOSITORY)
    restic_password=$(env_value RESTIC_PASSWORD)
    if [ -z "$restic_repository" ] || [ -z "$restic_password" ]; then
        if [ "$(env_value ALLOW_UNBACKED_PRODUCTION)" != true ]; then
            echo 'Production requires Restic credentials, or explicit ALLOW_UNBACKED_PRODUCTION=true.' >&2
            exit 1
        fi
        echo 'WARNING: production has no remote backup; loss of this server or its Docker volumes can permanently destroy all data.' >&2
    fi
fi

echo "Environment validation passed ($environment)."
