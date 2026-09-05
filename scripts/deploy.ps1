[CmdletBinding()]
param([switch]$Production,[switch]$SkipBackup,[switch]$Pull,[int]$TimeoutSeconds = 300)
$ErrorActionPreference = 'Stop'; $repo = Split-Path -Parent $PSScriptRoot; Set-Location $repo
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI not found. Restart Docker Desktop and this terminal.' }
& "$PSScriptRoot/validate-env.ps1" -Production:$Production; docker version | Out-Null
if ($Pull) { docker compose pull db clamav caddy }; docker compose config --quiet
$existing = docker compose ps -q api 2>$null; $envText = Get-Content -Raw -LiteralPath (Join-Path $repo '.env')
if (-not $SkipBackup -and $existing -and $envText -match '(?m)^\s*RESTIC_REPOSITORY\s*=\s*[^\s]+') { & "$PSScriptRoot/backup.ps1" }
docker compose build --pull api frontend; docker compose up -d db clamav
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do { $state = docker compose ps -q db | ForEach-Object { docker inspect --format '{{.State.Health.Status}}' $_ }; if ($state -eq 'healthy') { break }; if ((Get-Date) -gt $deadline) { docker compose ps; throw 'PostgreSQL did not become healthy in time.' }; Start-Sleep 3 } while ($true)
docker compose run --rm migrate; docker compose up -d api worker frontend caddy
do { try { docker compose exec -T caddy wget -qO- http://127.0.0.1/api/v1/health | Out-Null; if ($LASTEXITCODE -eq 0) { break } } catch {}; if ((Get-Date) -gt $deadline) { docker compose ps; docker compose logs --tail=100 api worker caddy; throw 'SocraLife health check timed out.' }; Start-Sleep 3 } while ($true)
docker compose ps; Write-Host 'SocraLife is ready on Docker network npm_default at http://socralife-caddy:80.'
