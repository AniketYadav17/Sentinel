import json

import pytest

import sentinel.eval_judge as ej


def row(gold_v, pred_v, gold_rules=None, pred_rules=None, ungrounded=False):
    return {
        "gold": {"verdict": gold_v},
        "pred": {"verdict": pred_v, "rule_ids": pred_rules or []},
        "gold_rules_norm": set(gold_rules or []),
        "area": "misleading-3.3",
        "ungrounded": ungrounded,
    }


def test_accuracy_and_confusion():
    rows = [row("breach", "breach"), row("breach", "compliant"), row("compliant", "compliant"), row("needs_review", "needs_review")]
    m = ej.judge_metrics(rows)
    assert m["accuracy"] == 0.75
    assert m["confusion"][("breach", "compliant")] == 1
    assert m["per_class"]["breach"]["recall"] == 0.5
    assert m["per_class"]["compliant"]["precision"] == 0.5


def test_citation_hit_uses_normalized_overlap():
    rows = [row("breach", "breach", gold_rules=["CONC 3.3.1"], pred_rules=["CONC 3.3.1R(1)"]),
            row("breach", "breach", gold_rules=["CONC 3.5.3"], pred_rules=["CONC 3.3.1R"])]
    assert ej.judge_metrics(rows)["citation_hit"] == 0.5


def test_empty_rows_all_metrics_zero():
    m = ej.judge_metrics([])
    assert m["n"] == 0 and m["accuracy"] == 0.0 and m["confusion"] == {} and m["by_area"] == {}


def test_load_golden_claims(tmp_path):
    example = {"id": "gold-001", "channel": "promo_email", "input_text": "t", "area": "misleading-3.3",
               "claims": [{"claim": "c", "verdict": "breach", "rules": ["CONC 3.3.1R"], "rationale": "r"}],
               "overall_verdict": "breach", "status": "draft", "notes": ""}
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps(example) + "\n", encoding="utf-8")
    claims = ej.load_golden_claims(p)
    assert claims[0]["channel"] == "promo_email" and claims[0]["rules"] == ["CONC 3.3.1R"]


import sentinel.eval_judge_e2e as e2e


def test_e2e_rows_scores_overall_verdicts():
    examples = [{"overall_verdict": "breach", "claims": [1, 2]}, {"overall_verdict": "compliant", "claims": [1]}]
    fake = iter([{"overall": "breach", "claims": [{}, {}, {}]}, {"overall": "breach", "claims": [{}]}])
    m = e2e.e2e_rows(examples, run_example=lambda ex: next(fake))
    assert m["overall_accuracy"] == 0.5
    assert m["mean_claim_delta"] == 0.5  # |3-2| and |1-1| -> mean 0.5


def test_run_judge_mode_does_not_publish_partial_results_on_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(ej, "RESULTS_PATH", tmp_path / "cache" / "judge_results.jsonl")
    monkeypatch.setattr(
        ej,
        "load_golden_claims",
        lambda path: [
            {"claim": "c1", "verdict": "breach", "rules": [], "area": "a", "channel": "ch", "input_text": "t"},
            {"claim": "c2", "verdict": "compliant", "rules": [], "area": "a", "channel": "ch", "input_text": "t"},
        ],
    )
    monkeypatch.setattr(ej, "query_vectors", lambda queries, cache_path: [[0.1], [0.2]])

    class FakeIndex:
        chunks: list[dict] = []  # ungrounded_rate reads the corpus rule ids in both modes

        @staticmethod
        def load(data_dir):
            return FakeIndex()

        def search_dense(self, v, k):
            return []

    monkeypatch.setattr(ej, "Index", FakeIndex)

    calls = {"n": 0}

    def crashing_generate_json(prompt, schema):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated 429 wall")
        return {"verdict": "breach", "rule_ids": [], "rationale": "r", "confidence": "high"}

    monkeypatch.setattr(ej, "generate_json", crashing_generate_json)

    with pytest.raises(RuntimeError, match="simulated 429 wall"):
        ej.run_judge_mode(tmp_path)

    assert not ej.RESULTS_PATH.exists()


def test_full_corpus_mode_passes_every_chunk_to_the_judge(tmp_path, monkeypatch):
    chunks = [
        {"rule_id": f"CONC 3.3.{i}", "designation": "R", "section": "CONC 3.3", "text": f"provision {i}"}
        for i in range(1, 87)
    ]

    class StubIndex:
        def __init__(self):
            self.chunks = chunks

        def search_dense(self, vector, k):
            raise AssertionError("full-corpus mode must not retrieve")

    prompts = []

    def fake_generate(prompt, schema, *, cache=True):
        prompts.append(prompt)
        return {"verdict": "compliant", "rule_ids": ["CONC 3.3.1R"], "rationale": "r", "confidence": "high"}

    monkeypatch.setattr(ej.Index, "load", lambda *a, **kw: StubIndex())
    monkeypatch.setattr(ej, "generate_json", fake_generate)
    monkeypatch.setattr(ej, "load_golden_claims", lambda p: [
        {"claim": "c1", "verdict": "compliant", "rules": ["CONC 3.3.1R"],
         "area": "hcstc", "channel": "promo_email", "input_text": "promo"},
    ])
    monkeypatch.setattr(ej, "RESULTS_PATH", tmp_path / "judge_results.jsonl")

    ej.run_judge_mode(tmp_path, full_corpus=True)

    assert len(prompts) == 1
    assert "provision 1" in prompts[0] and "provision 86" in prompts[0]


def test_full_corpus_mode_never_embeds_a_query(tmp_path, monkeypatch):
    class StubIndex:
        chunks = [{"rule_id": "CONC 3.3.1", "designation": "R", "section": "CONC 3.3", "text": "t"}]

    def boom(*a, **kw):
        raise AssertionError("full-corpus mode must not call the embedder")

    monkeypatch.setattr(ej.Index, "load", lambda *a, **kw: StubIndex())
    monkeypatch.setattr(ej, "query_vectors", boom)
    monkeypatch.setattr(ej, "generate_json", lambda p, s, **kw: {
        "verdict": "compliant", "rule_ids": [], "rationale": "r", "confidence": "high"})
    monkeypatch.setattr(ej, "load_golden_claims", lambda p: [
        {"claim": "c1", "verdict": "compliant", "rules": [], "area": "hcstc",
         "channel": "promo_email", "input_text": "promo"},
    ])
    monkeypatch.setattr(ej, "RESULTS_PATH", tmp_path / "judge_results.jsonl")

    ej.run_judge_mode(tmp_path, full_corpus=True)  # must not raise


def test_ungrounded_rate_counts_rule_ids_absent_from_the_corpus():
    rows = [row("breach", "breach", pred_rules=["CONC 3.3.1R"], ungrounded=False),
            row("breach", "breach", pred_rules=["CONC 9.9.9R"], ungrounded=True)]
    assert ej.judge_metrics(rows)["ungrounded_rate"] == 0.5


def test_ungrounded_rate_is_zero_on_empty_rows():
    assert ej.judge_metrics([])["ungrounded_rate"] == 0.0


def test_cli_accepts_judge_fullcorpus_mode(monkeypatch):
    import sys

    seen = {}
    monkeypatch.setattr(ej, "run_judge_mode", lambda root, **kw: seen.update(kw))
    monkeypatch.setattr(sys, "argv", ["eval_judge", "--mode", "judge-fullcorpus"])
    ej.main()
    assert seen == {"full_corpus": True}
