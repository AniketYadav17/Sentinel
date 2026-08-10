import json
import urllib.error
from io import BytesIO

import pytest

import sentinel.llm as llm

SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}


def _resp(payload: dict):
    class R(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return R(json.dumps(payload).encode())


def _azure_ok(text: str) -> dict:
    return {"choices": [{"finish_reason": "stop", "message": {"content": text, "refusal": None}}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "sentinel-judge")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "llm")


def test_returns_parsed_json(env, monkeypatch):
    captured = {}

    def fake(req, timeout):
        captured["body"] = json.loads(req.data)
        captured["req"] = req
        return _resp(_azure_ok('{"x": "ok"}'))

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    body = captured["body"]
    assert body["model"] == "sentinel-judge"
    assert body["temperature"] == 0
    assert body["response_format"]["json_schema"]["strict"] is True
    assert captured["req"].get_header("Api-key") == "test-key"


def test_cache_hit_skips_network(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok('{"x": "ok"}')))
    llm.generate_json("p", SCHEMA)

    def boom(req, timeout):
        raise AssertionError("network hit on cached call")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    with pytest.raises(AssertionError):
        llm.generate_json("p", SCHEMA, cache=False)


def test_429_retries_once_then_succeeds(env, monkeypatch):
    calls = []

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError("u", 429, "quota", {}, BytesIO(b"quota"))
        return _resp(_azure_ok('{"x": "ok"}'))

    monkeypatch.setattr(llm.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert len(calls) == 2


def test_429_honors_retry_after_header(env, monkeypatch):
    sleeps = []
    calls = []

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError("u", 429, "quota", {"Retry-After": "7"}, BytesIO(b"quota"))
        return _resp(_azure_ok('{"x": "ok"}'))

    monkeypatch.setattr(llm.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert sleeps == [7]


def test_http_error_surfaces_body(env, monkeypatch):
    def bad(req, timeout):
        raise urllib.error.HTTPError("u", 400, "bad", {}, BytesIO(b"schema rejected"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", bad)
    with pytest.raises(RuntimeError, match="schema rejected"):
        llm.generate_json("p", SCHEMA)


def test_non_json_output_raises_with_payload(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok("not json{")))
    with pytest.raises(RuntimeError, match="not json"):
        llm.generate_json("p", SCHEMA)


def test_empty_choices_raises_loudly(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp({"choices": []}))
    with pytest.raises(RuntimeError, match="no choices"):
        llm.generate_json("p", SCHEMA)


def test_refusal_raises_with_text(env, monkeypatch):
    payload = {"choices": [{"finish_reason": "content_filter", "message": {"content": None, "refusal": "cannot help with that"}}]}
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(payload))
    with pytest.raises(RuntimeError, match="cannot help with that"):
        llm.generate_json("p", SCHEMA)


def test_finish_reason_length_raises(env, monkeypatch):
    payload = _azure_ok('{"x": "ok"}')
    payload["choices"][0]["finish_reason"] = "length"
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(payload))
    with pytest.raises(RuntimeError, match="length"):
        llm.generate_json("p", SCHEMA)
