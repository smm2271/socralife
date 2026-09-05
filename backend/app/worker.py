"""Durable jobs. Run a single generation worker; PostgreSQL locks allow API concurrency."""
import asyncio, hashlib, json, logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import select, delete, text
from .config import Settings
from .db import database
from .models import User, Resource, Job, SearchDocument, StreamEvent, now, uid
from .domain import owned, rows, create, change, reserve, event, serialize, purge_user, Problem
from .storage import storage, scan

log = logging.getLogger("socralife.worker")

def text_content(r):
    d = r.data
    return d.get("content") or d.get("description") or d.get("statement") or "\n".join([d.get("question", ""), d.get("current_understanding", "")])

def indexable(r, db):
    if r.kind == "insight": return r.data["status"] == "ACTIVE"
    if r.kind == "reflection": return r.data["confirmed"] and not r.data.get("source_removed")
    if r.kind == "record" and r.data.get("source_reflection_id"):
        ref = db.get(Resource, r.data["source_reflection_id"])
        return bool(ref and ref.data.get("confirmed") and not ref.data.get("source_removed"))
    return True

def service(settings, factory):
    from .ai.service import AIService
    async def charge(kind):
        with factory() as db:
            reserve(db, f"model:{date.today().isoformat()}", settings.global_model_limit); db.commit()
    # AI adapters accept a mapping with uppercase environment-style names.
    return AIService({k.upper(): v for k, v in settings.model_dump().items()}, charge)

async def index_resource(factory, settings, job):
    with factory() as db:
        r = db.get(Resource, job.resource_id)
        if not r or r.user_id != job.user_id: return
        if not indexable(r, db):
            db.execute(delete(SearchDocument).where(SearchDocument.source_id == r.id)); db.commit(); return
        version, content = r.version, text_content(r)
        context = {"id": r.id, "source_id": r.id, "source_type": r.kind, "source_version": r.version, "title": r.data.get("title") or r.data.get("question") or r.data.get("statement", "")[:100], "excerpt": content[:5000], "occurred_at": r.data.get("occurred_at") or r.data.get("started_at"), "confirmed": r.kind == "insight" or bool(r.data.get("confirmed")), "status": r.data.get("status", "ORIGINAL"), "counter_evidence": False}
    ai = service(settings, factory)
    full_text = content or context["title"]
    chunks = [full_text[start:start+5000] for start in range(0, len(full_text), 4500)] or [""]
    vectors = await ai.embed(chunks)
    identity = json.dumps(ai.embedding_identity, sort_keys=True)
    with factory() as db:
        r = db.get(Resource, job.resource_id)
        if not r or r.version != version or not indexable(r, db): return
        db.execute(delete(SearchDocument).where(SearchDocument.source_id == r.id))
        for chunk, vector in zip(chunks, vectors):
            doc_id = uid()
            db.add(SearchDocument(id=doc_id, user_id=r.user_id, source_id=r.id, source_version=version, identity=identity, embedding=vector, context=dict(context, id=doc_id, excerpt=chunk)))
        db.commit()

async def retrieve(factory, settings, user_id, message, ai):
    identity = json.dumps(ai.embedding_identity, sort_keys=True)
    vector = (await ai.embed([message]))[0]
    with factory() as db:
        query = select(SearchDocument).where(SearchDocument.user_id == user_id, SearchDocument.identity == identity)
        candidates = list(db.scalars(query))
        candidates = [c for c in candidates if (r := db.get(Resource, c.source_id)) and r.user_id == user_id and r.version == c.source_version and indexable(r, db)]
        if db.bind.dialect.name == "postgresql":
            # Parameterized vector cast; ownership is applied before retrieval.
            ids = list(db.scalars(text("SELECT id FROM search_documents WHERE user_id=:owner AND identity=:identity ORDER BY embedding <=> CAST(:vector AS vector) LIMIT 20"), {"owner": user_id, "identity": identity, "vector": str(vector)}))
            mapping = {c.id: c for c in candidates}; semantic = [mapping[i].context for i in ids if i in mapping]
        else:
            def cosine(c):
                import math
                v = c.embedding
                norm = math.sqrt(sum(x*x for x in vector)*sum(x*x for x in v))
                return sum(a*b for a,b in zip(vector, v))/norm if norm else 0
            semantic = [c.context for c in sorted(candidates, key=cosine, reverse=True)[:20]]
        temporal = [c.context for c in sorted(candidates, key=lambda c: c.context.get("occurred_at") or "", reverse=True)[:20]]
    try: result = await ai.rerank(message, semantic, temporal)
    except Exception:
        result = []; seen = set()
        for pair in zip(semantic + [None]*20, temporal + [None]*20):
            for c in pair:
                if c and c["id"] not in seen: result.append(c); seen.add(c["id"])
    valid = {c["id"]: c for c in semantic + temporal}
    return [valid[c["id"]] for c in result if c.get("id") in valid][:8]

def persist_refs(db, user_id, context, refs, cache):
    authorized = {c["id"]: c for c in context}
    out = []
    for ref in refs:
        if ref not in authorized: raise ValueError("AI referenced unauthorized context")
        if ref not in cache:
            c = authorized[ref]
            source = owned(db, user_id, c["source_id"], c["source_type"])
            status = "VALID" if source.version == c["source_version"] else "STALE"
            e = create(db, user_id, "evidence", {"source_type": c["source_type"], "source_id": c["source_id"], "source_version": c["source_version"], "excerpt": c["excerpt"], "context": c["title"], "occurred_at": c.get("occurred_at"), "status": status})
            cache[ref] = e.id
        out.append(cache[ref])
    return out

async def generate(factory, settings, job):
    ai = service(settings, factory)
    with factory() as db:
        run = owned(db, job.user_id, job.resource_id, "run", True)
        if run.data["status"] != "QUEUED": return
        user = db.get(User, job.user_id)
        if not user or user.disabled: return
        change(db, run, run.version, {"status": "RUNNING"}, False)
        event(db, run, "stage.changed", {"stage": "RETRIEVE"})
        session = owned(db, job.user_id, run.data["session_id"], "session")
        message = owned(db, job.user_id, run.data["message_id"], "message")
        history = sorted([r for r in rows(db, job.user_id, "message") if r.data["session_id"] == session.id and r.id != message.id and r.data["complete"]], key=lambda r: r.created_at)
        request = {"message": message.data["content"], "history": [{"role": r.data["role"], "content": r.data["content"]} for r in history[-30:]], "consecutive_questions": session.data["consecutive_questions"], "session_id": session.id, "trace_id": run.data["trace_id"]}
        db.commit()
    context = await retrieve(factory, settings, job.user_id, request["message"], ai)
    request["context"] = context
    result = await ai.respond(request)
    with factory() as db:
        run = owned(db, job.user_id, job.resource_id, "run", True)
        user = db.get(User, job.user_id)
        if run.data["status"] != "RUNNING" or not user or user.disabled: return
        session = owned(db, job.user_id, run.data["session_id"], "session", True)
        cache = {}
        hypothesis = observation = reflection = None
        def refs(items): return persist_refs(db, job.user_id, context, items, cache)
        if result.get("observation"):
            d = result["observation"]
            observation = create(db, job.user_id, "observation", {"statement": d["statement"], "evidence_refs": refs(d.get("evidence_refs", [])), "status": "ACTIVE"})
        if result.get("hypothesis"):
            d = result["hypothesis"]
            hypothesis = create(db, job.user_id, "hypothesis", {"session_id": session.id, "statement": d["statement"], "evidence_refs": refs(d.get("evidence_refs", [])), "counter_evidence_refs": refs(d.get("counter_evidence_refs", [])), "uncertainty": d.get("uncertainty", "尚待確認"), "status": "PROPOSED", "source_removed": False})
        if result.get("reflection"):
            d = result["reflection"]
            reflection = create(db, job.user_id, "reflection", {"session_id": session.id, "record_id": None, "question": d["question"], "core_conflict": d["core_conflict"], "evidence_refs": refs(d.get("evidence_refs", [])), "counter_evidence_refs": refs(d.get("counter_evidence_refs", [])), "current_understanding": d["current_understanding"], "unknowns": d.get("unknowns", []), "actions": d.get("actions", []), "confirmed": False, "source_removed": False})
        ui = result.get("ui", [])
        # Only whitelist validated UI, rewrite context IDs to persisted evidence IDs.
        from .ai.ui import validate_ui
        for component in ui:
            if component["type"] == "hypothesis_card" and hypothesis:
                component["hypothesis_id"] = hypothesis.id
                component["version"] = hypothesis.version
            if component["type"] == "reflection_card" and reflection:
                component["reflection_id"] = reflection.id
                component["confirmed"] = False
            for field in ("evidence_refs", "counter_evidence_refs"):
                if field in component: component[field] = refs(component[field])
            for child in component.get("items", []) + component.get("options", []):
                if "evidence_refs" in child: child["evidence_refs"] = refs(child["evidence_refs"])
            validate_ui(component)
        questions = [c for c in ui if c["type"] == "question"]
        if session.data["consecutive_questions"] >= 3 and questions:
            ui = [{"schema_version": "1.0", "type": "text", "text": "我們先整理目前的理解，接著由你決定要繼續探索或保存回顧。"}]
            result["text"] = ui[0]["text"]
            questions = []
        count = session.data["consecutive_questions"] + 1 if questions and all(c["type"] in ("question", "text") for c in ui) else 0
        change(db, session, session.version, {"intent": result["intent"], "stage": result["stage"], "consecutive_questions": min(count, 3)}, False)
        assistant = create(db, job.user_id, "message", {"session_id": session.id, "role": "assistant", "content": result["text"], "run_id": run.id, "ui": ui, "complete": True})
        # Persist conversation as a life record with explicit original-conversation type.
        create(db, job.user_id, "record", {"type": "conversation", "title": session.data["title"], "content": request["message"], "occurred_at": date.today().isoformat(), "source_reflection_id": None})
        event(db, run, "stage.changed", {"stage": result["stage"]})
        for start in range(0, len(result["text"]), 120): event(db, run, "text.delta", {"delta": result["text"][start:start+120]})
        event(db, run, "ui.ready", {"components": ui, "message_id": assistant.id})
        if reflection: event(db, run, "artifact.ready", {"reflection": serialize(reflection)})
        change(db, run, run.version, {"status": "COMPLETED"}, False)
        event(db, run, "run.completed", {"message_id": assistant.id})
        db.commit()

async def scan_file(factory, settings, job):
    with factory() as db:
        r = db.get(Resource, job.resource_id)
        if not r or r.user_id != job.user_id or r.data["status"] == "CLEAN": return
        change(db, r, r.version, {"status": "SCANNING"}, False); db.commit()
    content = storage(settings).get(job.resource_id)
    scan(content, settings)
    from .ai.extraction import extract_text, visual_pages
    with factory() as db:
        r = db.get(Resource, job.resource_id)
        if not r or r.user_id != job.user_id: return
        if hashlib.sha256(content).hexdigest() != r.data["checksum"]: raise ValueError("file checksum mismatch")
        mime = r.data["mime_type"]
        extracted = extract_text(content, mime)
        if not extracted.strip() and mime in ("application/pdf", "image/png", "image/jpeg"):
            pages = visual_pages(content, mime)
            if pages:
                from .ai.service import AIService
                vision = await AIService(settings).vision("Extract visible text, dates, entities, events and verifiable evidence. Return JSON with a concise text field. Do not invent unreadable content.", pages)
                extracted = vision.get("text", "")[:200000]
        record = create(db, job.user_id, "record", {"type": "file", "title": r.data["filename"], "content": extracted[:200000], "occurred_at": None, "source_reflection_id": None})
        change(db, r, r.version, {"status": "CLEAN", "error": None, "record_id": record.id}, False); db.commit()

def recover(factory):
    """Single worker startup: unfinished model calls are never automatically repeated."""
    with factory() as db:
        for job in db.scalars(select(Job).where(Job.status == "RUNNING")):
            if job.kind == "generate":
                run = db.get(Resource, job.resource_id)
                if run and run.data["status"] in ("RUNNING", "QUEUED"):
                    change(db, run, run.version, {"status": "FAILED", "error": "WORKER_INTERRUPTED"}, False)
                    event(db, run, "run.failed", {"code": "WORKER_INTERRUPTED", "retryable": True})
                job.status = "FAILED"
            else: job.status = "QUEUED"
        db.commit()

async def work_once(factory, settings):
    with factory() as db:
        job = db.scalar(select(Job).where(Job.status == "QUEUED").order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job: return False
        job.status, job.started_at = "RUNNING", now(); db.commit()
        job_id = job.id
    try:
        with factory() as db:
            user = db.get(User, job.user_id)
            allowed = job.kind == "purge" or (user and not user.disabled)
        if allowed:
            if job.kind == "generate": await generate(factory, settings, job)
            elif job.kind == "index": await index_resource(factory, settings, job)
            elif job.kind == "scan": await scan_file(factory, settings, job)
            elif job.kind == "purge":
                with factory() as db: purge_user(db, job.user_id, settings); db.commit()
        with factory() as db:
            current = db.get(Job, job_id)
            if current: current.status = "COMPLETED"; db.commit()
    except Exception as exc:
        log.warning("job_failed kind=%s id=%s error_type=%s", job.kind, job_id, type(exc).__name__)
        with factory() as db:
            current = db.get(Job, job_id)
            if current: current.status = "FAILED"; current.error = getattr(exc, "code", type(exc).__name__)
            r = db.get(Resource, job.resource_id)
            if r and job.kind == "generate" and r.data["status"] in ("RUNNING", "QUEUED"):
                change(db, r, r.version, {"status": "FAILED", "error": getattr(exc, "code", "GENERATION_FAILED")}, False)
                event(db, r, "run.failed", {"code": getattr(exc, "code", "GENERATION_FAILED"), "retryable": True})
            if r and job.kind == "scan": change(db, r, r.version, {"status": "REJECTED" if isinstance(exc, Problem) else "FAILED", "error": "掃描未完成或未通過，檔案不開放使用"}, False)
            db.commit()
    return True

async def run():
    settings = Settings(); settings.validate_runtime()
    engine, factory = database(settings.database_url)
    # Prevent two workers from treating each other's in-flight jobs as interrupted.
    lock = engine.connect()
    if engine.dialect.name == "postgresql":
        if not lock.scalar(text("SELECT pg_try_advisory_lock(73496512)")): raise RuntimeError("A worker is already active")
    recover(factory)
    try:
        while True:
            if not await work_once(factory, settings): await asyncio.sleep(1)
    finally: lock.close(); engine.dispose()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
