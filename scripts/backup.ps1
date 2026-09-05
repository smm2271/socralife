[CmdletBinding()] param()
$ErrorActionPreference = 'Stop'; Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose stop api worker
try { docker compose --profile ops run --rm backup /ops/backup.sh } finally { docker compose start api worker }
