import json

import pytest

import sentinel.usage as usage

ROWS = [
    {"ts": 100.0, "path": "chat/completions", "deployment": "sentinel-judge", "ms": 1000,
     "prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
    {"ts": 200.0, "path": "chat/completions", "deployment": "sentinel-judge", "ms": 3000,
     "prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
    {"ts": 300.0, "path": "embeddings", "deployment": "sentinel-embed", "ms": 200,
     "prompt_tokens": 500, "total_tokens": 500},
]


def test_groups_by_deployment_and_counts_calls():
    out = usage.summarize(ROWS)
    assert set(out) == {"sentinel-judge", "sentinel-embed"}
    assert out["sentinel-judge"]["calls"] == 2
    assert out["sentinel-embed"]["calls"] == 1


def test_sums_tokens_treating_missing_completion_as_zero():
    out = usage.summarize(ROWS)
    assert out["sentinel-judge"]["prompt_tokens"] == 2000
    assert out["sentinel-judge"]["completion_tokens"] == 200
    assert out["sentinel-embed"]["prompt_tokens"] == 500
    assert out["sentinel-embed"]["completion_tokens"] == 0


def test_cost_uses_the_rate_table():
    rate_in, rate_out = usage.RATES["sentinel-judge"]
    expected = (2000 / 1_000_000) * rate_in + (200 / 1_000_000) * rate_out
    assert usage.summarize(ROWS)["sentinel-judge"]["usd"] == pytest.approx(expected)


def test_unknown_deployment_costs_nothing_and_says_so():
    rows = [{"ts": 1.0, "path": "chat/completions", "deployment": "mystery", "ms": 10,
             "prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}]
    out = usage.summarize(rows)
    assert out["mystery"]["usd"] == 0.0
    assert out["mystery"]["rate_known"] is False
    assert usage.summarize(ROWS)["sentinel-judge"]["rate_known"] is True


def test_percentiles_on_a_single_call_do_not_crash():
    one = [ROWS[0]]
    out = usage.summarize(one)["sentinel-judge"]
    assert out["p50_ms"] == 1000 and out["p95_ms"] == 1000


def test_p95_is_the_slow_tail_not_the_median():
    rows = [dict(ROWS[0], ms=m) for m in [10] * 19 + [5000]]
    out = usage.summarize(rows)["sentinel-judge"]
    assert out["p50_ms"] == 10
    assert out["p95_ms"] >= 1000


def test_since_filters_older_rows(tmp_path, monkeypatch):
    log = tmp_path / "usage.jsonl"
    log.write_text("\n".join(json.dumps(r) for r in ROWS) + "\n", encoding="utf-8")
    monkeypatch.setattr(usage, "USAGE_LOG", log)
    assert usage.load(since=250.0) == [ROWS[2]]
    assert len(usage.load(since=None)) == 3


def test_load_on_missing_log_exits_with_guidance(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "USAGE_LOG", tmp_path / "absent.jsonl")
    with pytest.raises(SystemExit, match="no usage log"):
        usage.load(since=None)
