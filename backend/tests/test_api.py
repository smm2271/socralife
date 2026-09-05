import asyncio, io, json, os, zipfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.main import create_app
from app.config import Settings
from app.models import Base, Resource, Job, User
from app.domain import create, rows, change
from app.worker import work_once, recover

@pytest.fixture
def app(tmp_path):
    url = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    settings = Settings(environment="test", database_url=url, enable_dev_auth=True, storage_root=str(tmp_path / "files"), deletion_ledger_path=str(tmp_path / "deletions.jsonl"))
    application = create_app(settings)
    if url.startswith("postgresql"):
        with application.state.engine.begin() as conn: conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.drop_all(application.state.engine); Base.metadata.create_all(application.state.engine)
    with TestClient(application) as client:
        application.test_client = client
        yield application
    Base.metadata.drop_all(application.state.engine)

def login(client, email="alice@example.test"):
    result = client.post("/api/v1/auth/dev", json={"email": email})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result.json()

def post(client, path, body, key=None):
    headers = {"Idempotency-Key": key} if key else {}
    response = client.post("/api/v1/" + path, json=body, headers=headers)
    assert response.status_code < 300, response.text
    return response.json()

def test_auth_isolation_csrf_version_and_dates(app):
    c = app.test_client
    assert c.get("/api/v1/records").status_code == 401
    login(c)
    r = post(c, "records", {"type": "manual", "title": "Private", "content": "private original"})
    assert c.patch(f"/api/v1/records/{r['id']}", json={"version": 1, "content": "new"}, headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert c.patch(f"/api/v1/records/{r['id']}", json={"version": 1, "content": "new"}).status_code == 200
    assert c.patch(f"/api/v1/records/{r['id']}", json={"version": 1, "content": "overwrite"}).status_code == 409
    assert c.post("/api/v1/events", json={"title": "bad date", "started_at": "2025-03-02", "ended_at": "2025-01-01"}).status_code == 422
    assert c.post("/api/v1/records", json={"type": "manual", "title": "hack", "content": "x", "user_id": "fake"}).status_code == 422
    login(c, "bob@example.test")
    assert c.get(f"/api/v1/records/{r['id']}").status_code == 404
    assert c.delete(f"/api/v1/records/{r['id']}").status_code == 404
    assert c.get("/api/v1/records").json()["items"] == []

def test_chronicle_slots_file_pipeline_and_delete(app, monkeypatch):
    c = app.test_client; login(c)
    e = post(c, "events", {"title": "Hackathon"})
    slots = post(c, f"events/{e['id']}/template", {"slots": [{"name": "slides", "status": "EXPECTED"}, {"name": "proof", "status": "NOT_REQUIRED"}]})["items"]
    assert c.get(f"/api/v1/events/{e['id']}").json()["total_slots"] == 1
    assert c.get("/api/v1/events?view=no_evidence").json()["items"][0]["id"] == e["id"]
    assert c.post("/api/v1/files", files={"file": ("bad.pdf", b"not pdf", "application/pdf")}).status_code == 422
    f = c.post("/api/v1/files", files={"file": ("notes.txt", b"synthetic notes", "text/plain")}).json()
    assert f["status"] == "QUARANTINED"
    assert c.get(f"/api/v1/files/{f['id']}/download").status_code == 409
    assert c.patch(f"/api/v1/events/{e['id']}/file-slots/{slots[0]['id']}", json={"version": 1, "linked_file_id": f["id"]}).status_code == 409
    monkeypatch.setattr("app.worker.scan", lambda content, settings: None)
    # Skip index jobs here; extraction is exercised by AI package integration tests.
    import sys, types
    if "app.ai.extraction" not in sys.modules:
        module = types.ModuleType("app.ai.extraction"); module.extract_text = lambda content, mime: content.decode(); monkeypatch.setitem(sys.modules, "app.ai.extraction", module)
    from app.worker import scan_file
    with app.state.factory() as db: job = next(j for j in db.scalars(select(Job)) if j.kind == "scan")
    asyncio.run(scan_file(app.state.factory, app.state.settings, job))
    r = c.patch(f"/api/v1/events/{e['id']}/file-slots/{slots[0]['id']}", json={"version": 1, "linked_file_id": f["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "AVAILABLE"
    assert c.get(f"/api/v1/files/{f['id']}/download").content == b"synthetic notes"
    assert c.delete(f"/api/v1/files/{f['id']}").status_code == 204
    s = c.get(f"/api/v1/events/{e['id']}/file-slots").json()["items"][0]
    assert s["status"] == "MISSING" and s["linked_file_id"] is None
    assert c.get(f"/api/v1/events/{e['id']}").status_code == 200

def hypothesis_fixture(app, c):
    user = login(c)
    r = post(c, "records", {"type": "manual", "title": "Collaboration", "content": "I enjoyed collaborative coding"})
    ev = post(c, "evidences", {"source_type": "record", "source_id": r["id"], "source_version": 1, "excerpt": "collaborative coding"})
    session = post(c, "sessions", {})
    with app.state.factory() as db:
        h = create(db, user["id"], "hypothesis", {"session_id": session["id"], "statement": "You may enjoy collaboration", "evidence_refs": [ev["id"]], "counter_evidence_refs": [], "uncertainty": "one example", "status": "PROPOSED", "source_removed": False})
        db.commit(); hid = h.id
    return r, ev, hid

def test_confirmation_idempotency_versions_and_deletion(app):
    c = app.test_client; r, ev, hid = hypothesis_fixture(app, c)
    result = post(c, f"hypotheses/{hid}/feedback", {"version": 1, "decision": "partial", "statement": "I enjoy focused pair programming"}, "confirm")
    insight = result["insight"]
    duplicate = post(c, f"hypotheses/{hid}/feedback", {"version": 1, "decision": "partial", "statement": "I enjoy focused pair programming"}, "confirm")
    assert duplicate["insight"]["id"] == insight["id"]
    assert c.post(f"/api/v1/hypotheses/{hid}/feedback", json={"version": 1, "decision": "reject"}, headers={"Idempotency-Key": "confirm"}).status_code == 409
    revised = c.patch(f"/api/v1/insights/{insight['id']}", json={"version": 1, "statement": "Focused collaboration helps"}).json()
    assert revised["supersedes"] == insight["id"] and revised["id"] != insight["id"]
    assert c.get(f"/api/v1/insights/{insight['id']}").json()["status"] == "SUPERSEDED"
    assert c.delete(f"/api/v1/records/{r['id']}").status_code == 204
    assert c.get(f"/api/v1/evidences/{ev['id']}").json()["excerpt"] == ""
    assert c.get(f"/api/v1/insights/{revised['id']}").json()["status"] == "NEEDS_REVIEW"

@pytest.mark.parametrize("decision", ["reject", "explore"])
def test_no_implicit_promotion(app, decision):
    c = app.test_client; _, _, hid = hypothesis_fixture(app, c)
    result = post(c, f"hypotheses/{hid}/feedback", {"version": 1, "decision": decision}, "feedback")
    assert result["insight"] is None
    assert c.get("/api/v1/insights").json()["items"] == []

def test_stale_evidence_cannot_confirm(app):
    c = app.test_client; r, ev, hid = hypothesis_fixture(app, c)
    c.patch(f"/api/v1/records/{r['id']}", json={"version": 1, "content": "Corrected context"})
    response = c.post(f"/api/v1/hypotheses/{hid}/feedback", json={"version": 1, "decision": "agree"}, headers={"Idempotency-Key": "confirm"})
    assert response.status_code == 409 and response.json()["code"] == "STALE_EVIDENCE"

def test_run_idempotency_cancel_and_replay(app):
    c = app.test_client; login(c)
    s = post(c, "sessions", {})
    accepted = post(c, f"sessions/{s['id']}/messages", {"content": "help explore"}, "message1")
    assert post(c, f"sessions/{s['id']}/messages", {"content": "help explore"}, "message1") == accepted
    assert c.post(f"/api/v1/sessions/{s['id']}/messages", json={"content": "second"}, headers={"Idempotency-Key": "message2"}).status_code == 409
    post(c, f"runs/{accepted['run_id']}/cancel", {})
    replayed = c.get(accepted["stream_url"])
    assert "run.cancelled" in replayed.text
    eventid = replayed.text.split("id: ", 1)[1].splitlines()[0]
    assert c.get(accepted["stream_url"], headers={"Last-Event-ID": eventid}).text == ""
    login(c, "other@example.test")
    assert c.get(accepted["stream_url"]).status_code == 404

def test_reflection_blog_action_export_and_account_delete(app):
    c = app.test_client; user = login(c)
    s = post(c, "sessions", {})
    draft = post(c, f"sessions/{s['id']}/artifact", {})
    response = c.put(f"/api/v1/sessions/{s['id']}/artifact", json={"version": draft["version"], "confirmed": True}, headers={"Idempotency-Key": "save"})
    assert response.status_code == 200, response.text
    saved = response.json(); assert saved["record_id"] and saved["confirmed"]
    blog = post(c, f"reflections/{saved['id']}/blog", {}, "blog")
    assert blog["type"] == "blog" and blog["source_reflection_id"] == saved["id"]
    action = post(c, "actions", {"title": "Try pairing", "reflection_id": saved["id"]})
    result = c.patch(f"/api/v1/actions/{action['id']}", json={"version": 1, "status": "COMPLETED", "result": "Useful experience"}).json()
    assert result["result_record_id"]
    exported = c.get("/api/v1/me/export")
    with zipfile.ZipFile(io.BytesIO(exported.content)) as z: assert "data.json" in z.namelist()
    assert c.delete("/api/v1/me").status_code == 202
    assert c.get("/api/v1/me").status_code == 401
    from app.domain import purge_user
    with app.state.factory() as db: purge_user(db, user["id"], app.state.settings); db.commit()
    with app.state.factory() as db: assert db.get(User, user["id"]) is None

def test_worker_recovery_preserves_message_and_fails_run(app):
    c = app.test_client; login(c)
    s = post(c, "sessions", {})
    accepted = post(c, f"sessions/{s['id']}/messages", {"content": "synthetic"}, "msg")
    with app.state.factory() as db:
        job = db.scalar(select(Job).where(Job.kind == "generate")); job.status = "RUNNING"
        run = db.get(Resource, accepted["run_id"]); change(db, run, run.version, {"status": "RUNNING"}, False); db.commit()
    recover(app.state.factory)
    assert c.get(f"/api/v1/runs/{accepted['run_id']}").json()["status"] == "FAILED"
    assert len(c.get(f"/api/v1/sessions/{s['id']}/messages").json()["items"]) == 1

def test_production_fails_closed():
    with pytest.raises(RuntimeError): Settings(environment="production").validate_runtime()
