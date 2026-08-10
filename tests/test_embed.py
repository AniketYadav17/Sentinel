import email.message
import io
import json
import urllib.error

import pytest

from sentinel.embed import embed_texts


def fake_urlopen(payload: dict):
    def _fake(req, timeout=None):
        _fake.body = json.loads(req.data)  # keep request for assertions
        _fake.req = req
        return io.BytesIO(json.dumps(payload).encode())
    return _fake


def http_error(code: int, body: bytes, retry_after: str | None = None):
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://x", code, "err", hdrs, io.BytesIO(body))


def _azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "sentinel-embed")


def test_embed_texts_normalizes_vectors(monkeypatch):
    _azure_env(monkeypatch)
    fake = fake_urlopen({"data": [{"embedding": [3.0, 4.0]}]})
    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    assert embed_texts(["hello"]) == [[0.6, 0.8]]
    assert fake.body == {"model": "sentinel-embed", "input": ["hello"], "dimensions": 768}
    assert "taskType" not in fake.body
    assert fake.req.get_header("Api-key") == "test-key"


def test_embed_texts_raises_on_count_mismatch(monkeypatch):
    _azure_env(monkeypatch)
    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake_urlopen({"data": []}))
    with pytest.raises(RuntimeError, match="0 embeddings for 1 texts"):
        embed_texts(["hello"])


def test_missing_api_key_exits_with_message(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="AZURE_OPENAI_API_KEY"):
        embed_texts(["hello"])


def test_missing_endpoint_exits_with_message(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    with pytest.raises(SystemExit, match="AZURE_OPENAI_ENDPOINT"):
        embed_texts(["hello"])


def test_retries_once_after_429_honors_retry_after(monkeypatch):
    _azure_env(monkeypatch)
    sleeps = []
    monkeypatch.setattr("sentinel.embed.time.sleep", sleeps.append)
    attempts = []

    def fake(req, timeout=None):
        attempts.append(1)
        if len(attempts) == 1:
            raise http_error(429, b"slow down", retry_after="7")
        return io.BytesIO(json.dumps({"data": [{"embedding": [3.0, 4.0]}]}).encode())

    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    assert embed_texts(["hello"]) == [[0.6, 0.8]]
    assert sleeps == [7]
    assert len(attempts) == 2


def test_retries_once_after_429_defaults_to_60(monkeypatch):
    _azure_env(monkeypatch)
    sleeps = []
    monkeypatch.setattr("sentinel.embed.time.sleep", sleeps.append)
    attempts = []

    def fake(req, timeout=None):
        attempts.append(1)
        if len(attempts) == 1:
            raise http_error(429, b"quota")
        return io.BytesIO(json.dumps({"data": [{"embedding": [3.0, 4.0]}]}).encode())

    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    assert embed_texts(["hello"]) == [[0.6, 0.8]]
    assert sleeps == [60]
    assert len(attempts) == 2


def test_http_error_surfaces_response_body(monkeypatch):
    _azure_env(monkeypatch)

    def fake(req, timeout=None):
        raise http_error(400, b'{"error": "bad dim"}')

    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    with pytest.raises(RuntimeError, match="bad dim"):
        embed_texts(["hello"])


def test_retries_once_on_connection_error(monkeypatch):
    _azure_env(monkeypatch)
    sleeps = []
    monkeypatch.setattr("sentinel.embed.time.sleep", sleeps.append)
    attempts = []

    def fake(req, timeout=None):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.URLError(TimeoutError("timed out"))
        return io.BytesIO(json.dumps({"data": [{"embedding": [3.0, 4.0]}]}).encode())

    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    assert embed_texts(["hello"]) == [[0.6, 0.8]]
    assert sleeps == [5]
    assert len(attempts) == 2


def test_connection_error_raises_after_retry(monkeypatch):
    _azure_env(monkeypatch)
    monkeypatch.setattr("sentinel.embed.time.sleep", lambda s: None)
    attempts = []

    def fake(req, timeout=None):
        attempts.append(1)
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr("sentinel.embed.urllib.request.urlopen", fake)
    with pytest.raises(RuntimeError, match="network failure"):
        embed_texts(["hello"])
    assert len(attempts) == 2
