import json
import urllib.error
from io import BytesIO

import pytest

import sentinel.llm as llm

SCHEMA = {"type": "OBJECT", "properties": {"x": {"type": "STRING"}}, "required": ["x"]}


def _resp(payload: dict):
    class R(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return R(json.dumps(payload).encode())


def _gemini_ok(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "llm")


def test_returns_parsed_json(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_gemini_ok('{"x": "ok"}')))
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}


def test_cache_hit_skips_network(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_gemini_ok('{"x": "ok"}')))
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
        return _resp(_gemini_ok('{"x": "ok"}'))

    monkeypatch.setattr(llm.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.generate_json("p", SCHEMA) == {"x": "ok"}
    assert len(calls) == 2


def test_http_error_surfaces_body(env, monkeypatch):
    def bad(req, timeout):
        raise urllib.error.HTTPError("u", 400, "bad", {}, BytesIO(b"schema rejected"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", bad)
    with pytest.raises(RuntimeError, match="schema rejected"):
        llm.generate_json("p", SCHEMA)


def test_non_json_output_raises_with_payload(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_gemini_ok("not json{")))
    with pytest.raises(RuntimeError, match="not json"):
        llm.generate_json("p", SCHEMA)


def test_blocked_candidate_raises_loudly(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen",
                        lambda req, timeout: _resp({"candidates": [{"finishReason": "SAFETY"}]}))
    with pytest.raises(RuntimeError, match="SAFETY"):
        llm.generate_json("p", SCHEMA)
