import hashlib, json
from datetime import date
from sqlalchemy import select, update, delete, func
from .models import Resource, Link, SearchDocument, Job, Counter, Idempotency, StreamEvent, User, Login, DeletionLedger, now

class Problem(Exception):
    def __init__(self, status, code, message, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}

def rows(db, user_id, kind):
    return list(db.scalars(select(Resource).where(Resource.user_id == user_id, Resource.kind == kind)))

def owned(db, user_id, id, kind=None, lock=False):
    q = select(Resource).where(Resource.id == id, Resource.user_id == user_id)
    if kind: q = q.where(Resource.kind == kind)
    if lock: q = q.with_for_update()
    r = db.scalar(q)
    if r is None: raise Problem(404, "NOT_FOUND", "找不到資料")
    return r

def serialize(r):
    return dict(id=r.id, user_id=r.user_id, version=r.version, created_at=r.created_at, updated_at=r.updated_at, **r.data)

def create(db, user_id, kind, data, index=True):
    r = Resource(user_id=user_id, kind=kind, data=data)
    db.add(r); db.flush()
    if index and kind in ("record", "event", "reflection", "insight"):
        db.add(Job(user_id=user_id, kind="index", resource_id=r.id))
    return r

def change(db, r, version, values, invalidate=True):
    if version != r.version: raise Problem(409, "VERSION_CONFLICT", "資料已變更，請重新載入")
    data = dict(r.data, **values)
    result = db.execute(update(Resource).where(Resource.id == r.id, Resource.version == version).values(data=data, version=version + 1, updated_at=now()).execution_options(synchronize_session=False))
    if result.rowcount != 1: raise Problem(409, "VERSION_CONFLICT", "資料已變更")
    db.refresh(r)
    if invalidate and r.kind in ("record", "event", "reflection", "insight"):
        propagate(db, r, removed=False)
        db.add(Job(user_id=r.user_id, kind="index", resource_id=r.id))
    return r

def validate_dates(data):
    for key in ("started_at", "ended_at", "occurred_at", "expected_at"):
        if data.get(key):
            try: date.fromisoformat(data[key])
            except ValueError: raise Problem(422, "INVALID_DATE", "日期格式須為 YYYY-MM-DD")
    if data.get("started_at") and data.get("ended_at") and data["started_at"] > data["ended_at"]:
        raise Problem(422, "INVALID_DATE", "結束日期不得早於開始日期")

def validate_evidence(db, user_id, refs):
    for ref in refs:
        e = owned(db, user_id, ref, "evidence")
        if e.data["status"] != "VALID": raise Problem(409, "STALE_EVIDENCE", "來源已變更，請重新檢視證據")
        source = owned(db, user_id, e.data["source_id"], e.data["source_type"])
        if source.version != e.data["source_version"]: raise Problem(409, "STALE_EVIDENCE", "來源版本已變更")

def propagate(db, source, removed):
    refs = []
    for e in rows(db, source.user_id, "evidence"):
        if e.data["source_id"] == source.id:
            refs.append(e.id)
            change(db, e, e.version, {"status": "SOURCE_REMOVED" if removed else "STALE", **({"excerpt": "", "context": ""} if removed else {})}, False)
    db.execute(delete(SearchDocument).where(SearchDocument.source_id == source.id))
    if refs:
        for kind in ("hypothesis", "observation", "reflection", "insight"):
            for r in rows(db, source.user_id, kind):
                if set(refs).intersection(r.data.get("evidence_refs", []) + r.data.get("counter_evidence_refs", [])):
                    values = {"status": "NEEDS_REVIEW"} if kind == "insight" else ({"status": "SOURCE_REMOVED" if removed else "STALE"} if kind == "observation" else ({"source_removed": True} if removed else {}))
                    if values: change(db, r, r.version, values, False)
                    db.execute(delete(SearchDocument).where(SearchDocument.source_id == r.id))

def remove(db, r, settings):
    propagate(db, r, True)
    if r.kind == "file":
        from .storage import storage
        storage(settings).delete(r.id)
        if r.data.get("record_id"):
            source = db.get(Resource, r.data["record_id"])
            if source: remove(db, source, settings)
        for slot in rows(db, r.user_id, "slot"):
            if slot.data.get("linked_file_id") == r.id:
                change(db, slot, slot.version, {"linked_file_id": None, "status": "MISSING" if slot.data["status"] == "AVAILABLE" else slot.data["status"]}, False)
    if r.kind == "event":
        for slot in rows(db, r.user_id, "slot"):
            if slot.data["event_id"] == r.id: db.delete(slot)
    db.execute(delete(Link).where((Link.source_id == r.id) | (Link.target_id == r.id)))
    db.delete(r); db.flush()

def purge_user(db, user_id, settings):
    for r in rows(db, user_id, "file"):
        from .storage import storage
        storage(settings).delete(r.id)
    for model in (StreamEvent, SearchDocument, Link, Login, Idempotency, Job, Resource):
        db.execute(delete(model).where(model.user_id == user_id))
    db.execute(delete(User).where(User.id == user_id))
    ledger = db.get(DeletionLedger, user_id)
    if ledger: ledger.completed_at = now()

def reserve(db, key, limit):
    # PostgreSQL advisory transaction lock serializes insert+increment across workers.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": lock_id})
    c = db.get(Counter, key, with_for_update=True)
    if not c: c = Counter(key=key, value=0); db.add(c); db.flush()
    result = db.execute(update(Counter).where(Counter.key == key, Counter.value < limit).values(value=Counter.value + 1))
    if result.rowcount != 1: raise Problem(429, "QUOTA_EXCEEDED", "今日額度已用完")

def replay(db, user_id, key, scope, body):
    if not key or len(key) > 200: raise Problem(422, "IDEMPOTENCY_KEY_REQUIRED", "需要 Idempotency-Key")
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old = db.scalar(select(Idempotency).where(Idempotency.user_id == user_id, Idempotency.key == key, Idempotency.scope == scope))
    if old and old.digest != digest: raise Problem(409, "IDEMPOTENCY_CONFLICT", "相同操作識別碼不可使用不同內容")
    return old.response if old else None, digest

def remember(db, user_id, key, scope, digest, result):
    db.add(Idempotency(user_id=user_id, key=key, scope=scope, digest=digest, response=result))
    return result

def event(db, run, type, payload):
    sequence = (db.scalar(select(func.max(StreamEvent.sequence)).where(StreamEvent.run_id == run.id)) or 0) + 1
    e = StreamEvent(user_id=run.user_id, run_id=run.id, sequence=sequence, type=type, payload=payload)
    db.add(e); db.flush(); return e

def event_json(e):
    return {"schema_version": "1.0", "event_id": e.id, "run_id": e.run_id, "sequence": e.sequence, "occurred_at": e.occurred_at, "type": e.type, "payload": e.payload}
