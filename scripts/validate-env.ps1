[CmdletBinding()]
param([switch]$Production)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repo '.env'
if (-not (Test-Path -LiteralPath $envFile)) { throw "Missing .env. Copy .env.example to .env first." }
$values = @{}
Get-Content -LiteralPath $envFile | ForEach-Object { if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { $values[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'") } }
function Require([string]$name) { if ([string]::IsNullOrWhiteSpace($values[$name])) { throw "Missing required .env value: $name" } }
Require 'POSTGRES_PASSWORD'; Require 'SECRET_KEY'
if ($values['SECRET_KEY'].Length -lt 32) { throw 'SECRET_KEY must contain at least 32 characters.' }
$environment = $values['ENVIRONMENT']
if ($Production -or $environment -eq 'production') {
  if ($values['ENABLE_DEV_AUTH'] -eq 'true') { throw 'ENABLE_DEV_AUTH=true is forbidden in production.' }
  if ($values['AI_PROVIDER'] -ne 'compatible') { throw 'Production requires AI_PROVIDER=compatible.' }
  if ($values['STORAGE_PROVIDER'] -ne 'local') { throw 'This deployment requires STORAGE_PROVIDER=local.' }
  Require 'APP_ORIGIN'; Require 'GOOGLE_CLIENT_ID'; Require 'GOOGLE_CLIENT_SECRET'; Require 'GOOGLE_REDIRECT_URI'; Require 'CHAT_BASE_URL'; Require 'CHAT_MODEL'; Require 'CHAT_API_KEY'; Require 'EMBEDDING_BASE_URL'; Require 'EMBEDDING_MODEL'; Require 'EMBEDDING_API_KEY'
  if (-not $values['APP_ORIGIN'].StartsWith('https://')) { throw 'Production APP_ORIGIN must use https://.' }
  if (-not $values['GOOGLE_REDIRECT_URI'].StartsWith('https://')) { throw 'Production GOOGLE_REDIRECT_URI must use https://.' }
  if ([string]::IsNullOrWhiteSpace($values['RESTIC_REPOSITORY']) -or [string]::IsNullOrWhiteSpace($values['RESTIC_PASSWORD'])) {
    if ($values['ALLOW_UNBACKED_PRODUCTION'] -ne 'true') { throw 'Production requires Restic credentials, or explicit ALLOW_UNBACKED_PRODUCTION=true.' }
    Write-Warning 'Production has no remote backup; loss of this server or its Docker volumes can permanently destroy all data.'
  }
}
Write-Host "Environment validation passed ($environment)."
