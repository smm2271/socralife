import asyncio, hashlib, io, json, secrets, zipfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from fastapi import FastAPI, Request, Response, UploadFile, File, Depends
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, delete, text
from sqlalchemy.exc import IntegrityError
from . import contracts as C
from .config import Settings
from .db import database
from .models import Base, Resource, User, Login, Link, Job, Counter, StreamEvent, DeletionLedger, now, uid
from .domain import Problem, rows, owned, serialize, create, change, remove, validate_dates, validate_evidence, replay, remember, reserve, event, event_json
from .auth import authenticate, establish, google_start, google_finish
from .storage import storage, validate_file

TEMPLATES = [
    {"id": "hackathon", "name": "競賽／Hackathon", "description": "保存合作過程與成果", "slots": [{"name": n, "status": "EXPECTED", "required": False} for n in ["參賽證明", "簡報", "作品", "心得"]]},
    {"id": "learning", "name": "課程／學習", "description": "記錄學習過程", "slots": [{"name": n, "status": "EXPECTED", "required": False} for n in ["課程筆記", "作業", "學習心得"]]},
    {"id": "project", "name": "個人專案", "description": "累積實作與回顧", "slots": [{"name": n, "status": "EXPECTED", "required": False} for n in ["專案說明", "成果", "回顧"]]},
]

def create_app(settings=None):
    settings = settings or Settings()
    engine, factory = database(settings.database_url)
    @asynccontextmanager
    async def lifespan(app):
        settings.validate_runtime()
        if settings.database_url.startswith("sqlite") and settings.environment == "test": Base.metadata.create_all(engine)
        yield
        engine.dispose()
    app = FastAPI(title="SocraLife", version="0.1.0", lifespan=lifespan)
    app.state.settings, app.state.engine, app.state.factory = settings, engine, factory

    @app.middleware("http")
    async def trace(request, call_next):
        request.state.trace_id = uid()
        response = await call_next(request)
        response.headers["X-Trace-ID"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Problem)
    async def problem(request, exc):
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "trace_id": request.state.trace_id, "details": exc.details})
    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={"code": "VALIDATION_ERROR", "message": "輸入格式不正確", "trace_id": request.state.trace_id, "details": {"fields": [str(e["loc"]) for e in exc.errors()]}})
    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"code": "CONFLICT", "message": "資料已變更，請重試", "trace_id": request.state.trace_id, "details": {}})

    def db_dep():
        with factory() as db:
            try: yield db; db.commit()
            except Exception: db.rollback(); raise
    def actor(request: Request, db=Depends(db_dep)):
        user, login = authenticate(request, db)
        request.state.user, request.state.login = user, login
        return user
    def lock_user(db, user):
        db.scalar(select(User).where(User.id == user.id).with_for_update())
    def idem(request, db, user, body):
        lock_user(db, user)
        key, scope = request.headers.get("Idempotency-Key"), request.url.path
        old, digest = replay(db, user.id, key, scope, body)
        return key, scope, old, digest
    def output(db, r):
        result = serialize(r)
        if r.kind == "event":
            slots = [s for s in rows(db, r.user_id, "slot") if s.data["event_id"] == r.id]
            result.update(available_slots=sum(s.data["status"] == "AVAILABLE" for s in slots), total_slots=sum(s.data["status"] not in ("NOT_REQUIRED", "ARCHIVED") for s in slots), evidence_count=sum(e.data["source_id"] == r.id and e.data["status"] == "VALID" for e in rows(db, r.user_id, "evidence")))
            links = list(db.scalars(select(Link).where(Link.source_id == r.id, Link.user_id == r.user_id)))
            result["record_ids"] = [l.target_id for l in links if l.relation == "record"]
            result["file_ids"] = list(dict.fromkeys([l.target_id for l in links if l.relation == "file"] + [s.data["linked_file_id"] for s in slots if s.data.get("linked_file_id")]))
        return result
    def page(db, user, kind, request, predicate=None):
        items = [output(db, r) for r in rows(db, user.id, kind)]
        if predicate: items = [r for r in items if predicate(r)]
        q = request.query_params.get("q", "").casefold()
        if q: items = [r for r in items if q in json.dumps(r, ensure_ascii=False).casefold()]
        for field in ("session_id", "source_id", "status", "type"):
            value = request.query_params.get(field)
            if value: items = [r for r in items if r.get(field) == value]
        view = request.query_params.get("view")
        if kind == "event" and view in ("pending", "incomplete", "needs_attention"):
            items = [r for r in items if r["available_slots"] < r["total_slots"]]
        if kind == "event" and view in ("no_evidence", "without_evidence"):
            items = [r for r in items if r["evidence_count"] == 0]
        items.sort(key=lambda r: (r["created_at"], r["id"]))
        cursor = request.query_params.get("cursor")
        if cursor:
            found = next((i for i, r in enumerate(items) if r["id"] == cursor), None)
            if found is None: raise Problem(422, "INVALID_CURSOR", "分頁游標無效")
            items = items[found+1:]
        try: limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
        except ValueError: raise Problem(422, "INVALID_LIMIT", "分頁數量無效")
        return {"items": items[:limit], "next_cursor": items[limit-1]["id"] if len(items) > limit else None}

    @app.get("/api/v1/health", response_model=C.Health)
    def health(db=Depends(db_dep)):
        db.execute(text("SELECT 1")); return {"status": "ok", "version": "0.1.0"}
    @app.post("/api/v1/auth/dev", response_model=C.User)
    def dev(body: C.DevLogin, response: Response, db=Depends(db_dep)):
        if settings.environment not in ("development", "test") or not settings.enable_dev_auth: raise Problem(404, "NOT_FOUND", "找不到資料")
        sub = "dev:" + body.email.strip().lower()
        user = db.scalar(select(User).where(User.google_sub == sub))
        if not user: user = User(google_sub=sub, email=body.email, name=body.name or "開發使用者"); db.add(user); db.flush()
        if user.disabled: raise Problem(401, "ACCOUNT_DISABLED", "帳號已停用")
        return establish(db, user, response, settings)
    @app.get("/api/v1/auth/google")
    def google(db=Depends(db_dep)):
        response = RedirectResponse("/", status_code=302)
        response.headers["location"] = google_start(db, response, settings)
        return response
    @app.get("/api/v1/auth/google/callback")
    async def callback(request: Request, db=Depends(db_dep)):
        user = await google_finish(request, db, settings)
        response = RedirectResponse(settings.public_url, status_code=302)
        establish(db, user, response, settings); response.delete_cookie("socralife_oauth")
        return response
    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(request: Request, response: Response, user=Depends(actor), db=Depends(db_dep)):
        db.delete(request.state.login); response.delete_cookie("socralife_session")
    @app.get("/api/v1/me", response_model=C.User)
    def me(request: Request, user=Depends(actor)):
        return {"id": user.id, "email": user.email, "name": user.name, "csrf_token": request.state.login.csrf, "ai_mode": settings.ai_provider}
    @app.get("/api/v1/me/usage", response_model=C.Usage)
    def usage(user=Depends(actor), db=Depends(db_dep)):
        day = date.today().isoformat()
        daily, global_ = db.get(Counter, f"generation:{user.id}:{day}"), db.get(Counter, f"model:{day}")
        return {"daily_generations": daily.value if daily else 0, "daily_limit": settings.daily_generation_limit, "global_model_calls": global_.value if global_ else 0, "global_limit": settings.global_model_limit, "storage_bytes": sum(r.data["size"] for r in rows(db, user.id, "file")), "storage_limit_bytes": settings.storage_limit_bytes}
    @app.delete("/api/v1/me", status_code=202)
    def delete_account(response: Response, user=Depends(actor), db=Depends(db_dep)):
        lock_user(db, user); user.disabled = True
        db.execute(delete(Login).where(Login.user_id == user.id))
        if not db.get(DeletionLedger, user.id): db.add(DeletionLedger(user_id=user.id))
        path = Path(settings.deletion_ledger_path); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"user_id": user.id, "deleted_at": now()}) + "\n"); f.flush()
            import os; os.fsync(f.fileno())
        db.add(Job(user_id=user.id, kind="purge", resource_id=user.id))
        response.delete_cookie("socralife_session")
        return {"status": "deletion_scheduled"}
    @app.get("/api/v1/me/export")
    def export(user=Depends(actor), db=Depends(db_dep)):
        buffer = io.BytesIO()
        resources = list(db.scalars(select(Resource).where(Resource.user_id == user.id)))
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("data.json", json.dumps([dict(kind=r.kind, **serialize(r)) for r in resources], ensure_ascii=False, indent=2))
            for r in resources:
                if r.kind == "record": z.writestr(f"records/{r.id}.md", f"# {r.data['title']}\n\n{r.data['content']}")
                if r.kind == "file" and r.data["status"] == "CLEAN": z.writestr(f"files/{r.id}/{Path(r.data['filename']).name}", storage(settings).get(r.id))
        return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="socralife-export.zip"'})

    def register_crud(path, kind, create_schema, update_schema, response_schema, defaults, fixed=None):
        def listing(request: Request, user=Depends(actor), db=Depends(db_dep)):
            return page(db, user, kind, request, (lambda r: r.get("type") == "blog") if path == "blogs" else None)
        def get(id: str, user=Depends(actor), db=Depends(db_dep)):
            r = owned(db, user.id, id, kind)
            if path == "blogs" and r.data.get("type") != "blog": raise Problem(404, "NOT_FOUND", "找不到資料")
            return output(db, r)
        async def post(request: Request, user=Depends(actor), db=Depends(db_dep)):
            try: body = create_schema.model_validate(await request.json())
            except Exception: raise Problem(422, "VALIDATION_ERROR", "輸入格式不正確")
            data = dict(defaults, **body.model_dump(exclude_none=True), **(fixed or {}))
            validate_dates(data)
            for key, refkind in (("session_id", "session"), ("reflection_id", "reflection"), ("source_reflection_id", "reflection")):
                if data.get(key): owned(db, user.id, data[key], refkind)
            r = create(db, user.id, kind, data)
            return output(db, r)
        async def patch(id: str, request: Request, user=Depends(actor), db=Depends(db_dep)):
            try: body = update_schema.model_validate(await request.json())
            except Exception: raise Problem(422, "VALIDATION_ERROR", "輸入格式不正確")
            r = owned(db, user.id, id, kind, True)
            if path == "blogs" and r.data.get("type") != "blog": raise Problem(404, "NOT_FOUND", "找不到資料")
            values = body.model_dump(exclude_unset=True); version = values.pop("version")
            if fixed: values.update(fixed)
            validate_dates(dict(r.data, **values))
            if values.get("source_reflection_id"): owned(db, user.id, values["source_reflection_id"], "reflection")
            change(db, r, version, values)
            if kind == "action" and "result" in values:
                content = values["result"] or ""
                if r.data.get("result_record_id"):
                    rec = owned(db, user.id, r.data["result_record_id"], "record")
                    change(db, rec, rec.version, {"title": r.data["title"], "content": content})
                elif content:
                    rec = create(db, user.id, "record", {"type": "manual", "title": r.data["title"], "content": content, "occurred_at": date.today().isoformat(), "source_reflection_id": r.data.get("reflection_id")})
                    change(db, r, r.version, {"result_record_id": rec.id}, False)
            return output(db, r)
        def destroy(id: str, user=Depends(actor), db=Depends(db_dep)):
            r = owned(db, user.id, id, kind, True)
            if path == "blogs" and r.data.get("type") != "blog": raise Problem(404, "NOT_FOUND", "找不到資料")
            remove(db, r, settings); return Response(status_code=204)
        app.add_api_route(f"/api/v1/{path}", listing, methods=["GET"])
        app.add_api_route(f"/api/v1/{path}/{{id}}", get, methods=["GET"], response_model=response_schema)
        if create_schema: app.add_api_route(f"/api/v1/{path}", post, methods=["POST"], status_code=201, response_model=response_schema)
        if update_schema: app.add_api_route(f"/api/v1/{path}/{{id}}", patch, methods=["PATCH"], response_model=response_schema)
        if kind in ("record", "event", "action", "file"): app.add_api_route(f"/api/v1/{path}/{{id}}", destroy, methods=["DELETE"], status_code=204)

    register_crud("records", "record", C.RecordCreate, C.RecordUpdate, C.Record, {"occurred_at": None, "source_reflection_id": None})
    register_crud("blogs", "record", C.RecordCreate, C.RecordUpdate, C.Record, {"occurred_at": None, "source_reflection_id": None}, {"type": "blog"})
    register_crud("events", "event", C.EventCreate, C.EventUpdate, C.Event, {"description": "", "event_type": "", "date_precision": "unknown", "tags": [], "user_verified": False, "started_at": None, "ended_at": None})
    register_crud("actions", "action", C.ActionCreate, C.ActionUpdate, C.Action, {"status": "PLANNED", "result": "", "result_record_id": None, "session_id": None, "reflection_id": None})
    register_crud("sessions", "session", C.SessionCreate, None, C.Session, {"title": "新的探索", "stage": "UNDERSTAND", "intent": None, "consecutive_questions": 0})
    for path, kind, model in [("files", "file", C.File), ("evidences", "evidence", C.Evidence), ("observations", "observation", C.Observation), ("hypotheses", "hypothesis", C.Hypothesis), ("insights", "insight", C.Insight), ("reflections", "reflection", C.Reflection), ("runs", "run", C.Run)]:
        register_crud(path, kind, None, None, model, {})

    @app.get("/api/v1/event-templates", response_model=C.EventTemplatePage)
    def templates(user=Depends(actor)): return {"items": TEMPLATES, "next_cursor": None}
    def slot_data(db, user, data):
        validate_dates(data)
        file_id = data.get("linked_file_id")
        if file_id:
            f = owned(db, user.id, file_id, "file")
            if f.data["status"] != "CLEAN": raise Problem(409, "FILE_NOT_CLEAN", "檔案尚未通過掃描")
            data["status"] = "AVAILABLE"
        elif data.get("status") == "AVAILABLE": raise Problem(422, "FILE_REQUIRED", "可用狀態必須連結檔案")
        return data
    def add_slot(db, user, event_id, body):
        data = {"name": "", "status": "EXPECTED", "required": False, "category": "", "expected_at": None, "linked_file_id": None, **body.model_dump(exclude_none=True), "event_id": event_id}
        return create(db, user.id, "slot", slot_data(db, user, data))
    @app.get("/api/v1/events/{id}/file-slots", response_model=C.FileSlotPage)
    def slots(id: str, request: Request, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "event"); return page(db, user, "slot", request, lambda r: r["event_id"] == id)
    @app.post("/api/v1/events/{id}/file-slots", status_code=201, response_model=C.FileSlot)
    def new_slot(id: str, body: C.SlotCreate, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "event"); return serialize(add_slot(db, user, id, body))
    @app.patch("/api/v1/events/{id}/file-slots/{slot_id}", response_model=C.FileSlot)
    def edit_slot(id: str, slot_id: str, body: C.SlotUpdate, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "event"); r = owned(db, user.id, slot_id, "slot", True)
        if r.data["event_id"] != id: raise Problem(404, "NOT_FOUND", "找不到資料")
        values = body.model_dump(exclude_unset=True); version = values.pop("version")
        if "linked_file_id" in values and not values["linked_file_id"] and r.data["status"] == "AVAILABLE": values.setdefault("status", "MISSING")
        data = slot_data(db, user, dict(r.data, **values))
        return serialize(change(db, r, version, data, False))
    @app.delete("/api/v1/events/{id}/file-slots/{slot_id}", status_code=204)
    def delete_slot(id: str, slot_id: str, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "event"); r = owned(db, user.id, slot_id, "slot")
        if r.data["event_id"] != id: raise Problem(404, "NOT_FOUND", "找不到資料")
        db.delete(r)
    @app.post("/api/v1/events/{id}/template", status_code=201, response_model=C.FileSlotPage)
    def apply_template(id: str, body: C.TemplateApply, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "event")
        return {"items": [serialize(add_slot(db, user, id, s)) for s in body.slots], "next_cursor": None}
    @app.api_route("/api/v1/events/{id}/links", methods=["POST", "DELETE"])
    def links(id: str, body: C.EventLink, request: Request, user=Depends(actor), db=Depends(db_dep)):
        r = owned(db, user.id, id, "event", True)
        if bool(body.record_id) == bool(body.file_id): raise Problem(422, "INVALID_LINK", "請指定一筆紀錄或檔案")
        kind, target_id = ("record", body.record_id) if body.record_id else ("file", body.file_id)
        target = owned(db, user.id, target_id, kind)
        if kind == "file" and target.data["status"] != "CLEAN": raise Problem(409, "FILE_NOT_CLEAN", "檔案尚未通過掃描")
        old = db.scalar(select(Link).where(Link.source_id == id, Link.target_id == target_id, Link.relation == kind))
        if request.method == "POST" and not old: db.add(Link(user_id=user.id, source_id=id, target_id=target_id, relation=kind))
        if request.method == "DELETE" and old: db.delete(old)
        db.flush(); return output(db, r)

    @app.post("/api/v1/files", status_code=202, response_model=C.File)
    async def upload(file: UploadFile = File(...), user=Depends(actor), db=Depends(db_dep)):
        content = await file.read(settings.max_file_bytes + 1)
        if len(content) > settings.max_file_bytes: raise Problem(413, "FILE_TOO_LARGE", "檔案超過大小上限")
        filename = Path((file.filename or "file").replace("\\", "/")).name[:255]
        mime = validate_file(filename, file.content_type, content)
        lock_user(db, user)
        if sum(r.data["size"] for r in rows(db, user.id, "file")) + len(content) > settings.storage_limit_bytes: raise Problem(429, "STORAGE_LIMIT", "儲存空間已滿")
        r = create(db, user.id, "file", {"filename": filename, "mime_type": mime, "size": len(content), "checksum": hashlib.sha256(content).hexdigest(), "status": "QUARANTINED", "error": None, "record_id": None})
        storage(settings).put(r.id, content)
        db.add(Job(user_id=user.id, kind="scan", resource_id=r.id))
        return serialize(r)
    @app.get("/api/v1/files/{id}/download")
    def download(id: str, user=Depends(actor), db=Depends(db_dep)):
        from urllib.parse import quote
        r = owned(db, user.id, id, "file")
        if r.data["status"] != "CLEAN": raise Problem(409, "FILE_NOT_CLEAN", "檔案尚未通過掃描")
        return Response(storage(settings).get(id), media_type=r.data["mime_type"], headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(r.data["filename"])})

    @app.post("/api/v1/evidences", status_code=201, response_model=C.Evidence)
    def evidence(body: C.EvidenceCreate, user=Depends(actor), db=Depends(db_dep)):
        source = owned(db, user.id, body.source_id, body.source_type)
        if source.version != body.source_version: raise Problem(409, "STALE_EVIDENCE", "來源版本已变更")
        if body.excerpt not in json.dumps(source.data, ensure_ascii=False) and body.excerpt not in "\n".join(str(v) for v in source.data.values()): raise Problem(422, "INVALID_EXCERPT", "證據節錄須來自原始資料")
        data = body.model_dump(); data.update(context=body.context or "", status="VALID")
        validate_dates(data)
        return serialize(create(db, user.id, "evidence", data))

    @app.post("/api/v1/hypotheses/{id}/feedback", response_model=C.FeedbackResult)
    def feedback(id: str, body: C.HypothesisFeedback, request: Request, user=Depends(actor), db=Depends(db_dep)):
        key, scope, old, digest = idem(request, db, user, body.model_dump())
        if old is not None: return old
        r = owned(db, user.id, id, "hypothesis", True)
        if body.version != r.version: raise Problem(409, "VERSION_CONFLICT", "資料已變更")
        if r.data["status"] != "PROPOSED": raise Problem(409, "ALREADY_REVIEWED", "此假設已回應")
        insight = None
        if body.decision in ("agree", "partial"):
            validate_evidence(db, user.id, r.data["evidence_refs"] + r.data["counter_evidence_refs"])
            if r.data.get("source_removed"): raise Problem(409, "STALE_EVIDENCE", "來源已移除")
            statement = body.statement.strip() if body.statement else ""
            if body.decision == "partial" and not statement: raise Problem(422, "STATEMENT_REQUIRED", "請填入修正後的理解")
            statement = statement if body.decision == "partial" else r.data["statement"]
            insight = create(db, user.id, "insight", {"statement": statement, "evidence_refs": r.data["evidence_refs"], "source_hypothesis_id": r.id, "valid_from": now(), "last_confirmed_at": now(), "supersedes": None, "status": "ACTIVE"})
            change(db, r, body.version, {"statement": statement, "status": "REVISED" if body.decision == "partial" else "CONFIRMED"}, False)
        elif body.decision == "reject": change(db, r, body.version, {"status": "REJECTED"}, False)
        result = {"hypothesis": serialize(r), "insight": serialize(insight) if insight else None}
        return remember(db, user.id, key, scope, digest, result)
    @app.patch("/api/v1/insights/{id}", response_model=C.Insight)
    def edit_insight(id: str, body: C.InsightUpdate, user=Depends(actor), db=Depends(db_dep)):
        r = owned(db, user.id, id, "insight", True)
        if body.version != r.version: raise Problem(409, "VERSION_CONFLICT", "資料已變更")
        if body.statement is not None:
            if not body.statement.strip(): raise Problem(422, "STATEMENT_REQUIRED", "理解不可為空")
            validate_evidence(db, user.id, r.data["evidence_refs"])
            values = dict(r.data, statement=body.statement, supersedes=r.id, status=body.status or "ACTIVE", valid_from=now(), last_confirmed_at=now())
            change(db, r, r.version, {"status": "SUPERSEDED"})
            return serialize(create(db, user.id, "insight", values))
        if body.status == "ACTIVE": validate_evidence(db, user.id, r.data["evidence_refs"])
        return serialize(change(db, r, body.version, {"status": body.status or r.data["status"]}))

    def reflection_record(db, r):
        content = "\n\n".join([r.data["question"], r.data["core_conflict"], r.data["current_understanding"], "未知：" + "；".join(r.data["unknowns"]), "行動：" + "；".join(r.data["actions"])])
        data = {"type": "reflection", "title": r.data["question"][:300], "content": content, "occurred_at": date.today().isoformat(), "source_reflection_id": r.id}
        if r.data.get("record_id"):
            rec = owned(db, r.user_id, r.data["record_id"], "record"); change(db, rec, rec.version, data)
        else:
            rec = create(db, r.user_id, "record", data); change(db, r, r.version, {"record_id": rec.id}, False)
        return r
    @app.patch("/api/v1/reflections/{id}", response_model=C.Reflection)
    def edit_reflection(id: str, body: C.ReflectionUpdate, user=Depends(actor), db=Depends(db_dep)):
        r = owned(db, user.id, id, "reflection", True)
        values = body.model_dump(exclude_unset=True); version = values.pop("version")
        combined = dict(r.data, **values)
        validate_evidence(db, user.id, combined["evidence_refs"] + combined["counter_evidence_refs"])
        change(db, r, version, values)
        if r.data["confirmed"]: reflection_record(db, r)
        return serialize(r)
    @app.post("/api/v1/reflections/{id}/blog", status_code=201, response_model=C.Record)
    def to_blog(id: str, request: Request, user=Depends(actor), db=Depends(db_dep)):
        key, scope, old, digest = idem(request, db, user, {})
        if old is not None: return old
        r = owned(db, user.id, id, "reflection")
        reflection_record(db, r)
        rec = owned(db, user.id, r.data["record_id"], "record")
        blog = create(db, user.id, "record", dict(rec.data, type="blog"))
        return remember(db, user.id, key, scope, digest, serialize(blog))

    @app.get("/api/v1/sessions/{id}/messages", response_model=C.MessagePage)
    def messages(id: str, request: Request, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "session"); return page(db, user, "message", request, lambda r: r["session_id"] == id)
    @app.post("/api/v1/sessions/{id}/messages", status_code=202, response_model=C.MessageAccepted)
    def submit(id: str, body: C.MessageCreate, request: Request, user=Depends(actor), db=Depends(db_dep)):
        key, scope, old, digest = idem(request, db, user, body.model_dump())
        if old is not None: return old
        owned(db, user.id, id, "session", True)
        if any(r.data["status"] in ("QUEUED", "RUNNING") for r in rows(db, user.id, "run")): raise Problem(409, "RUN_ACTIVE", "請先等待目前探索完成")
        reserve(db, f"generation:{user.id}:{date.today().isoformat()}", settings.daily_generation_limit)
        message = create(db, user.id, "message", {"session_id": id, "role": "user", "content": body.content, "run_id": None, "ui": [], "complete": True})
        run = create(db, user.id, "run", {"session_id": id, "message_id": message.id, "status": "QUEUED", "error": None, "trace_id": request.state.trace_id})
        change(db, message, message.version, {"run_id": run.id}, False)
        db.add(Job(user_id=user.id, kind="generate", resource_id=run.id))
        result = {"message_id": message.id, "run_id": run.id, "stream_url": f"/api/v1/runs/{run.id}/events"}
        return remember(db, user.id, key, scope, digest, result)
    def artifact(db, user, session_id):
        owned(db, user.id, session_id, "session")
        found = [r for r in rows(db, user.id, "reflection") if r.data["session_id"] == session_id]
        return max(found, key=lambda r: r.created_at) if found else None
    @app.get("/api/v1/sessions/{id}/artifact", response_model=C.Reflection)
    def get_artifact(id: str, user=Depends(actor), db=Depends(db_dep)):
        r = artifact(db, user, id)
        if not r: raise Problem(404, "NOT_FOUND", "尚未產生回顧")
        return serialize(r)
    @app.post("/api/v1/sessions/{id}/artifact", status_code=201, response_model=C.Reflection)
    def make_artifact(id: str, user=Depends(actor), db=Depends(db_dep)):
        session = owned(db, user.id, id, "session", True)
        existing = artifact(db, user, id)
        if existing: return serialize(existing)
        msgs = [r for r in rows(db, user.id, "message") if r.data["session_id"] == id and r.data["complete"]]
        msgs.sort(key=lambda r: r.created_at)
        first = next((m.data["content"] for m in msgs if m.data["role"] == "user"), session.data["title"])
        last = next((m.data["content"] for m in reversed(msgs) if m.data["role"] == "assistant"), "尚待整理")
        hypotheses = [r for r in rows(db, user.id, "hypothesis") if r.data["session_id"] == id]
        refs = list(dict.fromkeys(ref for h in hypotheses for ref in h.data["evidence_refs"]))
        r = create(db, user.id, "reflection", {"session_id": id, "record_id": None, "question": first, "core_conflict": "待使用者整理與確認", "evidence_refs": refs, "counter_evidence_refs": [], "current_understanding": last, "unknowns": ["這份草稿尚未確認"], "actions": [], "confirmed": False, "source_removed": False})
        return serialize(r)
    @app.put("/api/v1/sessions/{id}/artifact", response_model=C.Reflection)
    def save_artifact(id: str, body: C.ArtifactSave, request: Request, user=Depends(actor), db=Depends(db_dep)):
        key, scope, old, digest = idem(request, db, user, body.model_dump())
        if old is not None: return old
        r = artifact(db, user, id)
        if not r: raise Problem(404, "NOT_FOUND", "尚未產生回顧")
        if body.confirmed: validate_evidence(db, user.id, r.data["evidence_refs"] + r.data["counter_evidence_refs"])
        change(db, r, body.version, {"confirmed": body.confirmed})
        reflection_record(db, r)
        return remember(db, user.id, key, scope, digest, serialize(r))
    @app.post("/api/v1/runs/{id}/cancel", response_model=C.Run)
    def cancel(id: str, user=Depends(actor), db=Depends(db_dep)):
        r = owned(db, user.id, id, "run", True)
        if r.data["status"] in ("QUEUED", "RUNNING"):
            change(db, r, r.version, {"status": "CANCELLED"}, False); event(db, r, "run.cancelled", {})
        return serialize(r)
    @app.get("/api/v1/runs/{id}/events")
    def events(id: str, request: Request, user=Depends(actor), db=Depends(db_dep)):
        owned(db, user.id, id, "run")
        last = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
        sequence = 0
        if last:
            previous = db.scalar(select(StreamEvent).where(StreamEvent.id == last, StreamEvent.run_id == id, StreamEvent.user_id == user.id))
            if not previous: raise Problem(422, "INVALID_EVENT_ID", "串流游標無效")
            sequence = previous.sequence
        user_id = user.id
        async def stream():
            nonlocal sequence
            while not await request.is_disconnected():
                with factory() as stream_db:
                    current_user = stream_db.get(User, user_id)
                    if not current_user or current_user.disabled: return
                    run = stream_db.scalar(select(Resource).where(Resource.id == id, Resource.user_id == user_id))
                    if not run: return
                    batch = list(stream_db.scalars(select(StreamEvent).where(StreamEvent.run_id == id, StreamEvent.user_id == user_id, StreamEvent.sequence > sequence).order_by(StreamEvent.sequence)))
                    terminal = run.data["status"] in ("COMPLETED", "FAILED", "CANCELLED")
                    for e in batch:
                        sequence = e.sequence
                        yield f"id: {e.id}\nevent: {e.type}\ndata: {json.dumps(event_json(e), ensure_ascii=False)}\n\n"
                    if terminal: return
                if not batch: yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})
    return app

app = create_app()
