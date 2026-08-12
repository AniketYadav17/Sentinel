import pytest
from fastapi.testclient import TestClient

import sentinel.api as api
import sentinel.audit as audit

# `tests/` has no __init__.py, so pytest's default prepend import mode puts that directory
# on sys.path and the module is `test_audit`, NOT `tests.test_audit` — the latter raises
# ModuleNotFoundError. Reusing these five helpers beats duplicating them into a second file.
from test_audit import J_LOW, J_OK, OM_NONE, PROVISION, fake_generate

KEY = {"X-API-Key": "test-key"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_API_KEY", "test-key")
    monkeypatch.setattr(api, "STATE_DIR", tmp_path)
    monkeypatch.setattr(api, "_GRAPH", None)  # force a rebuild against tmp_path
    # patched on api, not audit: api.py does `from sentinel.audit import default_searcher`,
    # so the name it calls lives in api's namespace (same reason audit.generate_json is
    # patched on audit rather than on llm)
    monkeypatch.setattr(api, "default_searcher", lambda: (lambda claim, k=None: [PROVISION]))
    return TestClient(api.app)


def test_clean_audit_returns_a_report_and_no_review_id(client, monkeypatch):
    monkeypatch.setattr(audit, "generate_json",
                        fake_generate([{"claims": [{"claim": "c1"}]}, OM_NONE, J_OK]))
    r = client.post("/audit", json={"text": "promo", "channel": "promo_email"}, headers=KEY)
    assert r.status_code == 200
    assert r.json()["review_id"] is None
    assert r.json()["report"]["overall"] == "compliant"


def test_gate_firing_returns_202_with_a_review_id(client, monkeypatch):
    monkeypatch.setattr(audit, "generate_json",
                        fake_generate([{"claims": [{"claim": "c1"}]}, OM_NONE, J_LOW]))
    r = client.post("/audit", json={"text": "promo", "channel": "promo_email"}, headers=KEY)
    assert r.status_code == 202
    body = r.json()
    assert body["review_id"]
    assert body["pending"][0]["claim"] == "c1"


def test_review_survives_a_rebuilt_graph_and_resumes(client, monkeypatch):
    monkeypatch.setattr(audit, "generate_json",
                        fake_generate([{"claims": [{"claim": "c1"}]}, OM_NONE, J_LOW]))
    review_id = client.post("/audit", json={"text": "promo", "channel": "promo_email"},
                            headers=KEY).json()["review_id"]

    api._GRAPH = None  # simulate a restart: everything in memory is gone, only the file remains

    listed = client.get("/reviews", headers=KEY).json()["reviews"]
    assert [r["review_id"] for r in listed] == [review_id]

    r = client.post(f"/reviews/{review_id}/resume", json={"0": "breach"}, headers=KEY)
    assert r.status_code == 200
    claim = r.json()["report"]["claims"][0]
    assert claim["verdict"] == "breach" and claim["resolved_by"] == "human"


def test_resume_on_an_unknown_review_id_is_404(client):
    r = client.post("/reviews/does-not-exist/resume", json={"0": "breach"}, headers=KEY)
    assert r.status_code == 404


def test_requests_without_the_key_are_rejected(client):
    assert client.post("/audit", json={"text": "p", "channel": "promo_email"}).status_code == 401
    assert client.get("/reviews").status_code == 401


def test_wrong_key_is_rejected(client):
    bad = {"X-API-Key": "not-the-key"}
    assert client.post("/audit", json={"text": "p", "channel": "promo_email"}, headers=bad).status_code == 401


def test_auth_fails_closed_when_no_key_is_configured(tmp_path, monkeypatch):
    # a forgotten env var must mean "nothing works", never "anyone can spend your Azure budget"
    monkeypatch.delenv("SENTINEL_API_KEY", raising=False)
    monkeypatch.setattr(api, "STATE_DIR", tmp_path)
    monkeypatch.setattr(api, "_GRAPH", None)
    c = TestClient(api.app)
    assert c.post("/audit", json={"text": "p", "channel": "promo_email"}, headers=KEY).status_code == 401


def test_invalid_channel_is_rejected_by_the_schema(client):
    r = client.post("/audit", json={"text": "p", "channel": "support_reply"}, headers=KEY)
    assert r.status_code == 422  # promotions-only scope, enforced by pydantic not by hand
