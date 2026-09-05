[CmdletBinding()] param([Parameter(Mandatory=$true)][string]$Snapshot)
$ErrorActionPreference = 'Stop'; Set-Location (Split-Path -Parent $PSScriptRoot)
docker compose stop api worker; docker compose --profile ops run --rm backup /ops/restore.sh $Snapshot
docker compose run --rm --no-deps api python -m app.maintenance replay-deletions; docker compose start api worker
Write-Host 'Restore complete; run scripts/deploy.ps1 to perform the final health check.'
