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
    monkeypatch.setattr(llm, "USAGE_LOG", tmp_path / "usage.jsonl")


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
    assert captured["req"].full_url.endswith("/openai/v1/chat/completions")


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


def test_429_defaults_to_60_without_header(env, monkeypatch):
    sleeps = []
    calls = []

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError("u", 429, "quota", {}, BytesIO(b"quota"))
        return _resp(_azure_ok('{"x": "ok"}'))

    monkeypatch.setattr(llm.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm.generate_json("p-429-default", SCHEMA) == {"x": "ok"}
    assert sleeps == [60]


def test_missing_endpoint_exits_with_message(env, monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    with pytest.raises(SystemExit, match="AZURE_OPENAI_ENDPOINT"):
        llm.generate_json("p-no-endpoint", SCHEMA)


def test_missing_api_key_exits_with_message(env, monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="AZURE_OPENAI_API_KEY"):
        llm.generate_json("p-no-key", SCHEMA)


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


def test_retries_once_on_connection_error(env, monkeypatch):
    sleeps = []
    calls = []

    def flaky(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError(TimeoutError("timed out"))
        return _resp(_azure_ok('{"x": "ok"}'))

    monkeypatch.setattr(llm.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    assert llm.generate_json("p-conn-retry", SCHEMA, cache=False) == {"x": "ok"}
    assert sleeps == [5]
    assert len(calls) == 2


def test_connection_error_raises_after_retry(env, monkeypatch):
    calls = []

    def broken(req, timeout):
        calls.append(1)
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(llm.urllib.request, "urlopen", broken)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="network failure"):
        llm.generate_json("p-conn-fail", SCHEMA, cache=False)
    assert len(calls) == 2


def _azure_ok_with_usage(text: str, prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "choices": [{"finish_reason": "stop", "message": {"content": text, "refusal": None}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                  "total_tokens": prompt_tokens + completion_tokens},
    }


def test_live_call_appends_usage_row(env, monkeypatch):
    monkeypatch.setattr(
        llm.urllib.request, "urlopen",
        lambda req, timeout: _resp(_azure_ok_with_usage('{"x": "ok"}', 120, 30)),
    )
    llm.generate_json("p-usage-row", SCHEMA)
    rows = [json.loads(line) for line in llm.USAGE_LOG.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    assert rows[0]["path"] == "chat/completions"
    assert rows[0]["deployment"] == "sentinel-judge"
    assert rows[0]["prompt_tokens"] == 120
    assert rows[0]["completion_tokens"] == 30
    assert isinstance(rows[0]["ms"], int) and rows[0]["ms"] >= 0
    assert rows[0]["ts"] > 0


def test_cached_call_logs_nothing(env, monkeypatch):
    monkeypatch.setattr(
        llm.urllib.request, "urlopen",
        lambda req, timeout: _resp(_azure_ok_with_usage('{"x": "ok"}', 10, 5)),
    )
    llm.generate_json("p-usage-cached", SCHEMA)
    llm.generate_json("p-usage-cached", SCHEMA)  # cache hit — must not reach post()
    rows = [line for line in llm.USAGE_LOG.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1


def test_response_without_usage_block_logs_nothing(env, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok('{"x": "ok"}')))
    llm.generate_json("p-usage-absent", SCHEMA)
    assert not llm.USAGE_LOG.exists()


def test_offline_mode_raises_instead_of_calling_the_network(env, monkeypatch):
    monkeypatch.setenv("SENTINEL_OFFLINE", "1")

    def boom(req, timeout):
        raise AssertionError("network hit while SENTINEL_OFFLINE was set")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="offline replay"):
        llm.generate_json("p-offline-miss", SCHEMA)


def test_offline_error_names_the_endpoint_path(env, monkeypatch):
    monkeypatch.setenv("SENTINEL_OFFLINE", "1")
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok('{"x": "ok"}')))
    with pytest.raises(RuntimeError, match="chat/completions"):
        llm.post("chat/completions", {"model": "sentinel-judge"})


def test_offline_mode_still_serves_cache_hits(env, monkeypatch):
    monkeypatch.setattr(
        llm.urllib.request, "urlopen",
        lambda req, timeout: _resp(_azure_ok('{"x": "ok"}')),
    )
    llm.generate_json("p-offline-warm", SCHEMA)  # populate the cache while online
    monkeypatch.setenv("SENTINEL_OFFLINE", "1")
    assert llm.generate_json("p-offline-warm", SCHEMA) == {"x": "ok"}  # replays, no network


def test_offline_unset_behaves_normally(env, monkeypatch):
    monkeypatch.delenv("SENTINEL_OFFLINE", raising=False)
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok('{"x": "ok"}')))
    assert llm.generate_json("p-offline-unset", SCHEMA) == {"x": "ok"}


def test_empty_offline_var_is_not_offline(env, monkeypatch):
    # blanking a var is how this repo's own test commands disable Azure config;
    # SENTINEL_OFFLINE= must therefore mean "off", not "on"
    monkeypatch.setenv("SENTINEL_OFFLINE", "")
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: _resp(_azure_ok('{"x": "ok"}')))
    assert llm.generate_json("p-offline-empty", SCHEMA) == {"x": "ok"}


def test_offline_replay_needs_no_azure_credentials(env, monkeypatch):
    # replaying a cached metric must not require an Azure account: the offline check
    # comes BEFORE the endpoint/key checks, and this test pins that ordering
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SENTINEL_OFFLINE", "1")
    with pytest.raises(RuntimeError, match="offline replay"):
        llm.post("chat/completions", {"model": "sentinel-judge"})
