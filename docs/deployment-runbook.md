# SocraLife deployment runbook

## First deployment

Install Docker Desktop, start the Linux engine, open a new PowerShell window,
then run from the repository root:

```powershell
Copy-Item .env.example .env
notepad .env
.\scripts\deploy.ps1
```

The script validates the environment, checks Compose, starts PostgreSQL and
ClamAV, waits for health checks, runs Alembic, builds the API and Angular
images, starts the worker and Caddy, then polls `/api/v1/health`.

## Production

Set `ENVIRONMENT=production`, HTTPS `APP_ORIGIN`, Google OIDC values, model
credentials, durable file storage, and encrypted Restic credentials. Validate
and deploy with:

```powershell
.\scripts\validate-env.ps1 -Production
.\scripts\deploy.ps1 -Production
```

Existing deployments are backed up before migration when Restic is configured.
Use `-SkipBackup` only for a deliberate emergency deployment.

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
