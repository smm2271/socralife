# SocraLife deployment runbook

## First deployment

Ensure the external Nginx Proxy Manager network `npm_default` exists, then run
from the repository root. On Linux:

```sh
cp .env.example .env
chmod 600 .env
${EDITOR:-vi} .env
sh scripts/deploy.sh
```

On Windows with Docker Desktop:

```powershell
Copy-Item .env.example .env
notepad .env
.\scripts\deploy.ps1
```

The scripts validate the environment, check Compose, start PostgreSQL and
ClamAV, waits for health checks, runs Alembic, builds the API and Angular
images, starts the worker and Caddy, then polls `/api/v1/health`.

## Production

Set `ENVIRONMENT=production`, `AI_PROVIDER=compatible`, HTTPS `APP_ORIGIN`, Google OIDC values, model
credentials, durable file storage, and encrypted Restic credentials. Validate
and deploy with:

```sh
sh scripts/validate-env.sh --production
sh scripts/deploy.sh
```

Or on Windows:

```powershell
.\scripts\validate-env.ps1 -Production
.\scripts\deploy.ps1 -Production
```

Existing deployments are backed up before migration when Restic is configured.
Use `-SkipBackup` only for a deliberate emergency deployment.

If remote backup is temporarily unavailable, production is rejected unless
`ALLOW_UNBACKED_PRODUCTION=true` is explicitly set. This accepts the risk of
permanent data loss. Configure Nginx Proxy Manager with forward hostname
`socralife-caddy`, port `80`, WebSocket support, and the public TLS certificate.

## Operations

```powershell
docker compose ps
docker compose logs --tail=200 api worker caddy
.\scripts\backup.ps1
.\scripts\restore.ps1 -Snapshot <restic-snapshot-id>
```

Restore requires API and worker downtime. It restores database, files and the
deletion ledger, replays deletion records, then starts services. Keep database
and file volumes private and expose only Caddy ports. Schedule daily backups
and test a restore before accepting real user data.
