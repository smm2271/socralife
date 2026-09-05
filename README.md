# SocraLife

SocraLife is a private, evidence-based life reflection workspace. The v0.1
implementation contains the Angular client, FastAPI API, PostgreSQL/pgvector
memory store, durable worker, provider-agnostic AI service, event Chronicle,
file quarantine pipeline, and Docker deployment files.

## Run locally

Copy `.env.example` to `.env`, keep `ENVIRONMENT=development`, and start Docker
Desktop. Then run:

```powershell
docker compose up --build
```

Open `http://localhost:8080`. Google OAuth is configured through the variables in
`.env`; for an isolated local smoke test, enable the explicit development login
and visit `http://localhost:8080/?dev=1`. Development login is rejected when
`ENVIRONMENT=production`.

Run the API tests without Docker with the project virtual environment:

```powershell
$env:PYTHONPATH = "backend"
.venv\Scripts\python.exe -m pytest backend/tests -q
```

Build the frontend with `npm.cmd ci` followed by `npm.cmd run build` in
`frontend/`. `python scripts/check_contract.py` and
`python scripts/generate_contracts.py --check` verify the shared contracts.

## Production checklist

Set a real HTTPS `APP_ORIGIN`, a 32-character `SECRET_KEY`, Google OIDC
credentials and redirect URI, compatible chat/embedding endpoints, an S3 or
durable file volume, and an encrypted Restic repository. Do not enable fake AI
or development login. `scripts/deploy.sh` runs the backup, migration, health
check, and rolling service startup sequence; the backup and restore scripts
require the API and worker to be stopped while data is being replaced.

The canonical interfaces are [contracts/openapi.yaml](contracts/openapi.yaml),
[contracts/ui.schema.json](contracts/ui.schema.json), and
[docs/architecture.md](docs/architecture.md). Generated DTOs must be refreshed
with `python scripts/generate_contracts.py` after a contract change.
