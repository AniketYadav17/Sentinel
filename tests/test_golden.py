"""Structural invariants every golden example must satisfy — the mechanical half of label verification."""

import json
from pathlib import Path

import pytest

from sentinel.audit import worst_case
from sentinel.eval_retrieval import normalize_rule_id

GOLDEN = Path(__file__).parents[1] / "evals" / "golden.jsonl"
CHUNKS_DIR = Path(__file__).parents[1] / "data" / "chunks"
PROMO_CHANNELS = {"promo_email", "promo_social", "promo_web"}
VERDICTS = {"breach", "compliant", "needs_review"}
AUTHORITY_KEYS = {"source", "url", "quote", "rule_cited_by_source", "verification"}
FCA_URL_PREFIXES = ("https://www.fca.org.uk/", "https://www.handbook.fca.org.uk/")


def rows():
    return [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l]


def all_claims():
    return [(r["id"], c) for r in rows() for c in r["claims"]]


def test_size_and_ids_unique():
    rs = rows()
    assert 20 <= len(rs) <= 30
    assert len({r["id"] for r in rs}) == len(rs)


def test_examples_are_promotions_with_required_fields():
    for r in rows():
        assert r["channel"] in PROMO_CHANNELS, r["id"]
        assert r["input_text"].strip(), r["id"]
        assert r["claims"], r["id"]
        assert r["status"] in {"draft", "verified"}, r["id"]
        assert r["area"].strip(), r["id"]


def test_every_verdict_class_is_represented():
    overall = [r["overall_verdict"] for r in rows()]
    assert overall.count("breach") >= 10
    assert overall.count("compliant") >= 3
    assert overall.count("needs_review") >= 3


def test_claim_labels_are_well_formed():
    for rid, c in all_claims():
        assert c["verdict"] in VERDICTS, rid
        assert c["rules"], rid
        assert c["rationale"].strip(), rid


def test_overall_verdict_is_worst_case_of_claims():
    # the defect class that made 4 v1 examples unwinnable: overall=breach with no breach claim
    for r in rows():
        assert r["overall_verdict"] == worst_case([c["verdict"] for c in r["claims"]]), r["id"]


def test_label_authority_present_and_fca_sourced():
    for rid, c in all_claims():
        auth = c["label_authority"]
        assert set(auth) == AUTHORITY_KEYS, rid
        assert all(str(auth[k]).strip() for k in AUTHORITY_KEYS), rid
        assert auth["url"].startswith(FCA_URL_PREFIXES), rid
        assert auth["verification"] in {"mechanical", "judgement"}, rid
        if auth["verification"] == "judgement":
            assert c["verdict"] == "needs_review", rid


@pytest.mark.skipif(not CHUNKS_DIR.exists(), reason="corpus not ingested (data/ is local-only)")
def test_cited_rules_exist_in_corpus():
    corpus = {
        json.loads(l)["rule_id"]
        for f in CHUNKS_DIR.glob("*.jsonl")
        for l in f.read_text(encoding="utf-8").splitlines()
        if l
    }
    for rid, c in all_claims():
        for rule in c["rules"]:
            assert normalize_rule_id(rule) in corpus, (rid, rule)
