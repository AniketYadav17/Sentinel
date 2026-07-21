import io
import json
import urllib.error

import pytest

from sentinel.embed import embed_texts


def fake_urlopen(payload: dict):
    def _fake(req, timeout=None):
        _fake.body = json.loads(req.data)  # keep request for assertions
        return io.BytesIO(json.dumps(payload).encode())
    return _fake


def test_embed_texts_normalizes_vectors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    fake = fake_urlopen({"embeddings": [{"values": [3.0, 4.0]}]})
    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    assert embed_texts(["hello"], "RETRIEVAL_DOCUMENT") == [[0.6, 0.8]]
    req = fake.body["requests"][0]
    assert req["taskType"] == "RETRIEVAL_DOCUMENT"
    assert req["outputDimensionality"] == 768


def test_embed_texts_raises_on_count_mismatch(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake_urlopen({"embeddings": []}))
    with pytest.raises(RuntimeError, match="0 embeddings for 1 texts"):
        embed_texts(["hello"], "RETRIEVAL_QUERY")


def test_missing_api_key_exits_with_message(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        embed_texts(["hello"], "RETRIEVAL_QUERY")


def test_http_error_surfaces_response_body(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake(req, timeout=None):
        raise urllib.error.HTTPError(
            "https://x", 400, "Bad Request", None, io.BytesIO(b'{"error": "bad dim"}')
        )

    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    with pytest.raises(RuntimeError, match="bad dim"):
        embed_texts(["hello"], "RETRIEVAL_QUERY")
