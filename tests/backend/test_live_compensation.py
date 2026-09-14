import copy
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lifeos.config import Settings
from lifeos.engine import Engine
from lifeos.main import create_app
from lifeos.providers import LiveProviders, ProviderError
from lifeos.store import Database


@pytest.fixture
def scenario(tmp_path):
    state = {"id": "meeting", "etag": "before", "summary": "Original", "location": "Room A"}
    requests = []
    behavior = {}

    def handler(request):
        requests.append(request)
        if request.method == "PATCH":
            assert request.headers["if-match"] == state["etag"]
            if behavior.get("race"):
                return httpx.Response(412)
            state.update(json.loads(request.content))
            state["etag"] = "after" if state["summary"] == "Updated" else "restored"
            if behavior.get("timeout"):
                raise httpx.ReadTimeout("fixture lost response", request=request)
        return httpx.Response(200, json=state)

    async def load(*_):
        return {"access_token": "local-fixture"}

    settings = SimpleNamespace(mode="live")
    providers = LiveProviders(settings, load, load)
    # No requests ever leave the process.
    providers.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    db = Database(f"sqlite:///{tmp_path}/undo.db")
    engine = Engine(db, settings, providers)
    action = {
        "id": "action",
        "application": "calendar",
        "type": "update",
        "status": "approved",
        "arguments": {"event_id": "meeting", "etag": "before", "summary": "Updated"},
        "reversible": True,
        "arguments_hash": "fixture",
        "risk": "medium",
    }
    event = {"id": "event", "version": 1, "timeline": [], "actions": [action], "status": "resolved"}
    return engine, providers, event, state, requests, behavior


async def execute_update(engine, providers, event):
    action = event["actions"][0]
    await providers.preflight("owner", [action])
    engine.save("owner", event)
    result = await providers.execute("owner", dict(action, _authorized=True), "fixture-key")
    action["compensation_journal"] = result["compensation_journal"]
    action["evidence"] = await providers.verify("owner", action, result)
    action["status"] = "verified"
    engine.save("owner", event)


async def test_live_undo_restores_only_modified_fields_and_preserves_evidence(scenario):
    engine, providers, event, state, requests, _ = scenario
    await execute_update(engine, providers, event)
    original_evidence = copy.deepcopy(event["actions"][0]["evidence"])
    undone = await engine.undo("owner", event)
    assert undone["status"] == "compensated"
    action = undone["actions"][0]
    assert action["evidence"] == original_evidence
    assert action["compensation_evidence"]["verified"]
    assert state["summary"] == "Original" and state["location"] == "Room A"
    patches = [r for r in requests if r.method == "PATCH"]
    assert len(patches) == 2
    assert json.loads(patches[-1].content) == {"summary": "Original"}
    assert patches[-1].headers["if-match"] == "after"
    assert patches[-1].url.params["sendUpdates"] == "all"
    with pytest.raises(HTTPException):
        await engine.undo("owner", undone)
    await providers.close()


@pytest.mark.parametrize("change", ["etag", "summary", "race"])
async def test_live_undo_blocks_concurrent_changes(scenario, change):
    engine, providers, event, state, requests, behavior = scenario
    await execute_update(engine, providers, event)
    if change == "race":
        behavior["race"] = True
    else:
        state[change] = "externally changed"
    result = await engine.undo("owner", event)
    assert result["status"] == "partial_failure"
    assert result["actions"][0]["compensation_status"] == "failed"
    assert not result["actions"][0].get("compensation_evidence")
    assert len([r for r in requests if r.method == "PATCH"]) == (2 if change == "race" else 1)
    await providers.close()


@pytest.mark.parametrize("crashed", [False, True])
async def test_uncertain_compensation_is_never_retried_after_restart(scenario, crashed):
    engine, providers, event, state, requests, behavior = scenario
    await execute_update(engine, providers, event)
    if crashed:
        event["actions"][0]["compensation_status"] = "executing"
        engine.save("owner", event)
    else:
        behavior["timeout"] = True
        result = await engine.undo("owner", event)
        assert result["actions"][0]["compensation_status"] == "uncertain"
        assert state["summary"] == "Original"
    restart = Engine(engine.db, engine.settings, providers)
    before = len(requests)
    with pytest.raises(HTTPException, match="409"):
        await restart.undo("owner", restart.event("owner", "event"))
    assert len(requests) == before
    await providers.close()


async def test_compensation_requires_engine_authorization(scenario):
    engine, providers, event, _, requests, _ = scenario
    await execute_update(engine, providers, event)
    before = len(requests)
    with pytest.raises(ProviderError):
        await providers.compensate_calendar("owner", event["actions"][0])
    assert len(requests) == before
    await providers.close()


async def test_startup_marks_interrupted_compensation_for_manual_review(scenario):
    engine, providers, event, _, _, _ = scenario
    await execute_update(engine, providers, event)
    event["actions"][0]["compensation_status"] = "executing"
    engine.save("owner", event)
    restarted = create_app(Settings(database_url=str(engine.db.engine.url)))
    with TestClient(restarted):
        persisted = restarted.state.engine.event("owner", event["id"])
        assert persisted["status"] == "partial_failure"
        assert persisted["actions"][0]["status"] == "verified"
        assert persisted["actions"][0]["compensation_status"] == "uncertain"
        assert "MANUAL_REVIEW_REQUIRED" in persisted["actions"][0]["compensation_error"]
    await providers.close()
