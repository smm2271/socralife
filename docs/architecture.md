# SocraLife architecture and ownership

Status: v0.1 implementation contract. Public Google registration, private personal data.

## Boundaries

`contracts/openapi.yaml` (JSON, valid YAML) is the source for HTTP and domain types.
`contracts/ui.schema.json` is the version 1.0 UI whitelist. Run
`python scripts/generate_contracts.py` to generate Python DTOs and TypeScript types.
Generated files are committed and checked for drift in CI. Only the integration
agent edits contracts. Backend agent owns all SQLAlchemy models and migrations.

Frontend owns `frontend/`; backend owns `backend/` except `app/ai/` and generated
contracts; AI agent owns `backend/app/ai/` and AI tests/fixtures. Work is performed
in separate worktrees and integrated by the primary agent.

## Runtime

Angular -> same-origin `/api/v1` -> FastAPI -> PostgreSQL/pgvector. A separate
Python worker consumes durable PostgreSQL jobs. Caddy terminates HTTPS. Files
remain quarantined until MIME verification and ClamAV scanning succeed.
Local storage and S3 implement identical put/get/delete methods. AI adapters
never write to the database.

## AI integration interface (frozen)

`app.ai.service.AIService(settings=None, charge=None)` accepts a settings object
or mapping. `charge` is an optional async callable `(kind: str) -> None`; runtime
must supply it to atomically reserve each external model/embedding/rerank call.

`await service.respond(request: dict) -> dict`:

- input: `message`, `history` (role/content), `context` (ContextItem[]),
  `consecutive_questions`, `session_id`, `trace_id`.
- output: `intent`, `stage`, `text`, `ui` (validated UIComponent[]),
  `hypothesis` (null or statement/evidence_refs/counter_evidence_refs/uncertainty),
  `observation` (null or statement/evidence_refs), `reflection` (null or
  question/core_conflict/evidence_refs/counter_evidence_refs/current_understanding/
  unknowns/actions), `consecutive_questions`, `metadata`.
- Hypotheses, observations, reflections and evidence IDs are persisted ONLY by
  backend orchestration. A provider response never confirms an insight.
- UI hypothesis cards emitted by AI use `hypothesis_id: null`; backend replaces
  it with the persisted ID and version before publishing `ui.ready`.

`await service.embed(texts: list[str]) -> list[list[float]]`;
`await service.rerank(query: str, semantic: list[dict], temporal: list[dict]) -> list[dict]`;
`service.embedding_identity -> dict` containing provider/model/dimension.
`app.ai.ui.validate_ui(component: dict) -> dict` validates or raises ValueError.
`app.ai.extraction.extract_text(content: bytes, mime_type: str) -> str` supports
TXT/Markdown, textual PDF and DOCX only; other supported files return empty text.

Settings names: AI_PROVIDER=fake|compatible, CHAT_BASE_URL, CHAT_MODEL, VISION_MODEL,
CHAT_API_KEY, EMBEDDING_BASE_URL, EMBEDDING_MODEL, EMBEDDING_API_KEY,
EMBEDDING_DIMENSION, MODEL_TIMEOUT_SECONDS, MAX_OUTPUT_TOKENS. Production fails
startup if fake AI/dev auth is enabled. Fake is deterministic and explicitly
labelled in the client.

## Protocol invariants

- UUID IDs; UTC timestamps; date-only event boundaries plus date_precision.
- All ownership is derived from server-side auth. No user_id accepted in writes.
- Versioned updates use request `version`; stale updates return 409.
- Cross-owner reads/mutations/SSE/downloads return 404.
- Error body: `{code,message,trace_id,details}`. Cursor pages: `{items,next_cursor}`.
- Mutation CSRF: `X-CSRF-Token`, retrieved from GET `/me` response.
- Idempotency-Key is required for message submission, feedback, artifact save
  and conversion to blog; same key+different payload returns 409.
- Google OIDC code flow uses state/nonce and validates issuer/audience/expiry.
  Google `sub` maps to internal user UUID. Session cookie HttpOnly, Secure in
  production, SameSite=Lax. No Google tokens exposed to client or logs.
- POST messages returns 202 with message_id/run_id/stream_url. One active run
  per account and session. Event replay NEVER starts model generation.
- Events: stage.changed/text.delta/ui.ready/artifact.ready/run.completed/
  run.failed/run.cancelled. Envelope: schema_version/event_id/run_id/sequence/
  occurred_at/payload. Persist before send. `Last-Event-ID` resumes ordered events.
- Backend state machine enforces at most three consecutive text questions.
- Hypothesis feedback agree creates CONFIRMED insight; partial requires edited
  statement and creates REVISED hypothesis + insight; reject creates none;
  explore leaves PROPOSED. Feedback checks source evidence versions.
- Insight revision creates a new row linked through supersedes; never rewrites
  history. Withdrawn/archived/needs-review insights are not current truths.
- Source edits mark evidence STALE; source deletion removes excerpts/index,
  marks derived artifacts source_removed and confirmed insights NEEDS_REVIEW.
- Slots: AVAILABLE/PENDING/EXPECTED/MISSING/NOT_REQUIRED/ARCHIVED. AVAILABLE
  requires a same-owner CLEAN file. Unlink/delete clean file -> MISSING.
- Coverage excludes NOT_REQUIRED/ARCHIVED; zero denominator has no percentage.
- Public registration is unrestricted; default per-user daily generations 30,
  storage 500 MiB, file 50 MiB, global daily external model calls 1000, output
  2000 tokens. Reserve quota atomically before external side effects.
- Account deletion disables auth immediately and queues erasure within 24h;
  backup retention 30d. Restores reapply deletion ledger.

## Delivery gates

M0 contracts/build; M1 memory/chronicle; M2 exploration loop; M3 P1 views,
versions/templates; M4 quotas/deletion/export/backup/production configuration.
Tests use synthetic data and fake model, never real life records. Production
secrets, domain, VM and a live model are operator configuration dependencies.
