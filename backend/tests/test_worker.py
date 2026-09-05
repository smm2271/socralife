import asyncio, json, sys, types
from pathlib import Path
import pytest
from sqlalchemy import select
from app.models import Resource, Job, SearchDocument
from app.worker import work_once, retrieve
from test_api import app, login, post

class DeterministicAI:
    embedding_identity = {"provider": "test", "model": "test", "dimension": 3}
    async def embed(self, texts): return [[1.0, 0.5, 0.1] for _ in texts]
    async def rerank(self, query, semantic, temporal): return semantic[:8]
    async def respond(self, request):
        refs = [r["id"] for r in request["context"]]
        hypothesis = {"statement": "Collaboration might matter", "evidence_refs": refs, "counter_evidence_refs": [], "uncertainty": "One example"}
        return {"intent": "EXPLORATION", "stage": "VERIFY", "text": "Does this fit?", "ui": [{"schema_version": "1.0", "type": "hypothesis_card", "hypothesis_id": None, **hypothesis}], "hypothesis": hypothesis, "observation": {"statement": "A pattern", "evidence_refs": refs}, "reflection": None}

@pytest.fixture
def fake_ai(monkeypatch):
    monkeypatch.setattr("app.worker.service", lambda settings, factory: DeterministicAI())
    import jsonschema
    schema = json.loads((Path(__file__).parents[2] / "contracts/ui.schema.json").read_text())
    ui = types.ModuleType("app.ai.ui")
    ui.validate_ui = lambda c: jsonschema.validate(c, schema)
    monkeypatch.setitem(sys.modules, "app.ai.ui", ui)

def drain(app):
    for _ in range(30):
        if not asyncio.run(work_once(app.state.factory, app.state.settings)): return
    raise AssertionError("queue did not drain")

def test_generation_retrieval_persistence_and_confirmation(app, fake_ai):
    c = app.test_client; user = login(c)
    rec = post(c, "records", {"type": "manual", "title": "Pair coding", "content": "Enjoyed collaborative coding"})
    drain(app)
    session = post(c, "sessions", {"title": "Career exploration"})
    accepted = post(c, f"sessions/{session['id']}/messages", {"content": "Do I enjoy collaboration?"}, "generation")
    drain(app)
    run = c.get(f"/api/v1/runs/{accepted['run_id']}").json()
    assert run["status"] == "COMPLETED", run
    messages = c.get(f"/api/v1/sessions/{session['id']}/messages").json()["items"]
    card = messages[-1]["ui"][0]
    assert card["hypothesis_id"] and card["version"] == 1
    ev = c.get(f"/api/v1/evidences/{card['evidence_refs'][0]}").json()
    assert ev["source_id"] == rec["id"] and ev["source_version"] == 1
    assert c.get("/api/v1/insights").json()["items"] == []
    result = post(c, f"hypotheses/{card['hypothesis_id']}/feedback", {"version": 1, "decision": "partial", "statement": "Focused collaboration suits me"}, "confirm")
    drain(app)
    context = asyncio.run(retrieve(app.state.factory, app.state.settings, user["id"], "collaboration", DeterministicAI()))
    assert any(item["source_id"] == result["insight"]["id"] and item["confirmed"] for item in context)
    stream = c.get(accepted["stream_url"]).text
    assert "ui.ready" in stream and "run.completed" in stream
    with app.state.factory() as db:
        count_before = len(list(db.scalars(select(Job))))
    c.get(accepted["stream_url"])
    with app.state.factory() as db: assert len(list(db.scalars(select(Job)))) == count_before
    login(c, "other@example.test")
    assert asyncio.run(retrieve(app.state.factory, app.state.settings, c.get("/api/v1/me").json()["id"], "collaboration", DeterministicAI())) == []

def test_unknown_ai_reference_fails_without_artifact(app, fake_ai, monkeypatch):
    class BadAI(DeterministicAI):
        async def respond(self, request):
            r = await super().respond(request)
            r["hypothesis"]["evidence_refs"] = ["unauthorized-id"]
            return r
    monkeypatch.setattr("app.worker.service", lambda settings, factory: BadAI())
    c = app.test_client; login(c)
    session = post(c, "sessions", {})
    run = post(c, f"sessions/{session['id']}/messages", {"content": "Explore"}, "message")
    drain(app)
    assert c.get(f"/api/v1/runs/{run['run_id']}").json()["status"] == "FAILED"
    assert c.get("/api/v1/hypotheses").json()["items"] == []
    assert len(c.get(f"/api/v1/sessions/{session['id']}/messages").json()["items"]) == 1
