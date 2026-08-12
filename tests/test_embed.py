"""Embedding-shaped behavior only — the retry/error contract is llm.post's, tested in test_llm.py."""

import io
import json

import pytest

from sentinel.embed import embed_texts


def fake_urlopen(payload: dict):
    def _fake(req, timeout=None):
        _fake.body = json.loads(req.data)  # keep request for assertions
        _fake.req = req
        return io.BytesIO(json.dumps(payload).encode())
    return _fake


def _azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "sentinel-embed")


def test_embed_texts_normalizes_vectors(monkeypatch):
    _azure_env(monkeypatch)
    fake = fake_urlopen({"data": [{"embedding": [3.0, 4.0]}]})
    monkeypatch.setattr("sentinel.llm.urllib.request.urlopen", fake)
    assert embed_texts(["hello"]) == [[0.6, 0.8]]
    assert fake.body == {"model": "sentinel-embed", "input": ["hello"], "dimensions": 768}
    assert "taskType" not in fake.body
    assert fake.req.get_header("Api-key") == "test-key"
    assert fake.req.full_url.endswith("/openai/v1/embeddings")  # embeddings path, not chat


def test_embed_texts_raises_on_count_mismatch(monkeypatch):
    _azure_env(monkeypatch)
    monkeypatch.setattr("sentinel.llm.urllib.request.urlopen", fake_urlopen({"data": []}))
    with pytest.raises(RuntimeError, match="0 embeddings for 1 texts"):
        embed_texts(["hello"])


def test_zero_norm_embedding_raises(monkeypatch):
    _azure_env(monkeypatch)
    monkeypatch.setattr("sentinel.llm.urllib.request.urlopen", fake_urlopen({"data": [{"embedding": [0.0, 0.0]}]}))
    with pytest.raises(RuntimeError, match="zero-norm"):
        embed_texts(["hello"])
