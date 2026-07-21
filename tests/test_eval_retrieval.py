import json

import pytest

from sentinel.eval_retrieval import load_claims, normalize_rule_id, score


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CONC 3.3.1R", "CONC 3.3.1"),
        ("CONC 3.3.10G", "CONC 3.3.10"),
        ("CONC 3.3.4G(2)", "CONC 3.3.4"),
        ("CONC 3.5.7R(1)(c)", "CONC 3.5.7"),
        ("CONC 3.3.1R(1A)", "CONC 3.3.1"),
        ("CONC 3.3.1", "CONC 3.3.1"),
        ("CONC 5A.2.1R", "CONC 5A.2.1"),
    ],
)
def test_normalize_rule_id(raw, expected):
    assert normalize_rule_id(raw) == expected


def test_score_hand_computed():
    s = score({"A", "B"}, ["X", "A", "Y", "Z", "Q", "R", "S", "T", "U", "B"])
    assert s["recall@3"] == 0.5   # A of {A,B} in top 3
    assert s["hit@3"] == 1.0
    assert s["recall@5"] == 0.5
    assert s["recall@10"] == 1.0  # B arrives at rank 10
    assert s["mrr"] == 0.5        # first relevant at rank 2


def test_score_no_relevant_retrieved():
    s = score({"A"}, ["X", "Y"])
    assert s["recall@3"] == 0.0
    assert s["hit@10"] == 0.0
    assert s["mrr"] == 0.0


def test_load_claims_skips_out_of_corpus_and_counts(tmp_path):
    golden = tmp_path / "golden.jsonl"
    example = {
        "area": "misleading-3.3",
        "claims": [
            {"claim": "guaranteed approval", "rules": ["CONC 3.3.3R", "CONC 99.1.1R"]},
            {"claim": "cites nothing in corpus", "rules": ["CONC 99.1.1R"]},
        ],
    }
    golden.write_text(json.dumps(example) + "\n", encoding="utf-8")
    claims, skipped = load_claims(golden, corpus_rule_ids={"CONC 3.3.3"})
    assert skipped == 1
    assert claims == [
        {"query": "guaranteed approval", "relevant": {"CONC 3.3.3"}, "area": "misleading-3.3"}
    ]
