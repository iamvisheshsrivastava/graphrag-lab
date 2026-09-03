"""
End-to-end FastAPI TestClient tests for the cheap, non-LLM endpoints
(issue #7). Deliberately does NOT exercise /graph/build or /query — those
call OpenRouter for real when OPENROUTER_API_KEY is configured (as it is in
local dev via backend/.env), and hitting them here would spend real API
credits / make CI network-dependent. Those code paths are covered by the
mocked unit tests in test_llm_extractor.py instead.
"""
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project"].startswith("GraphRAG")
    assert "llm_enabled" in body


def test_sample_requirements_returns_seed_data(client):
    resp = client.get("/requirements/sample")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0] and "text" in data[0]


def test_add_and_get_requirement_roundtrip(client):
    payload = {"id": "REQ-TEST-1", "text": "The system shall test things.", "type": "functional"}
    resp = client.post("/requirements", json=payload)
    assert resp.status_code == 200
    assert resp.json()["id"] == "REQ-TEST-1"

    resp = client.get("/requirements/REQ-TEST-1")
    assert resp.status_code == 200
    assert resp.json()["text"] == payload["text"]


def test_get_unknown_requirement_is_404(client):
    resp = client.get("/requirements/does-not-exist")
    assert resp.status_code == 404


def test_requirement_text_over_max_length_is_rejected(client):
    payload = {"id": "REQ-TOO-LONG", "text": "x" * 5001}
    resp = client.post("/requirements", json=payload)
    assert resp.status_code == 422


def test_requirement_batch_over_max_length_is_rejected(client):
    reqs = [{"id": f"REQ-{i}", "text": "x"} for i in range(201)]
    resp = client.post("/requirements/batch", json={"requirements": reqs})
    assert resp.status_code == 422


def test_verify_all_runs_deterministic_verification(client):
    client.post("/requirements", json={"id": "REQ-V1", "text": "The system shall park."})
    resp = client.post("/requirements/verify-all")
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["requirement_id"] == "REQ-V1" for r in results)


def test_graph_current_without_a_built_graph(client):
    resp = client.get("/graph/current")
    # Either 404 (nothing built yet, no Neo4j to reload from in this env) or
    # 200 if a previous test/process already built one against the shared
    # in-process singleton — both are valid states, just assert consistency.
    assert resp.status_code in (200, 404)


def test_neo4j_status_reports_not_connected_when_unconfigured(client):
    resp = client.get("/graph/neo4j/status")
    assert resp.status_code == 200
    assert resp.json()["connected"] is False
