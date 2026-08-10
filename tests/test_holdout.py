"""Structural invariants for the FG15-04 holdout — test_golden's checks with the holdout deltas.

Deltas from test_golden: size 6-14; ids hold-2NN; channels promo_social/promo_web
(FG15/4 examples are social-media and banner promotions); per-claim rules_in_corpus
flag checked BOTH directions against the corpus (FG15/4 spans sectors, so most claims
cite COBS/PRIN/FSMA provisions outside the CONC 3 corpus); label_authority url
allowlist gains the FG15/4 pdf; quotes are verified against the local source and
input_texts checked for newline-normalized equality with their transcription files
when present (data/ is local-only; CRLF files vs LF input_text).
"""

import json
import re
from pathlib import Path

import pytest

from sentinel.audit import worst_case
from sentinel.eval_retrieval import normalize_rule_id

ROOT = Path(__file__).parents[1]
HOLDOUT = ROOT / "evals" / "holdout.jsonl"
CHUNKS_DIR = ROOT / "data" / "chunks"
FG15_04_TXT = ROOT / "data" / "sources" / "fg15-04.txt"
PROMO_CHANNELS = {"promo_social", "promo_web"}
VERDICTS = {"breach", "compliant", "needs_review"}
AUTHORITY_KEYS = {"source", "url", "quote", "rule_cited_by_source", "verification"}
FG15_04_URL = "https://www.fca.org.uk/publication/finalised-guidance/fg15-04.pdf"
FCA_URL_PREFIXES = ("https://www.fca.org.uk/", "https://www.handbook.fca.org.uk/", FG15_04_URL)


def rows():
    return [json.loads(l) for l in HOLDOUT.read_text(encoding="utf-8").splitlines() if l]


def all_claims():
    return [(r["id"], c) for r in rows() for c in r["claims"]]


def test_size_and_ids_unique():
    rs = rows()
    assert 6 <= len(rs) <= 14
    assert len({r["id"] for r in rs}) == len(rs)
    for r in rs:
        assert re.fullmatch(r"hold-2\d\d", r["id"]), r["id"]


def test_examples_are_promotions_with_required_fields():
    for r in rows():
        assert r["channel"] in PROMO_CHANNELS, r["id"]
        assert r["input_text"].strip(), r["id"]
        assert r["claims"], r["id"]
        assert r["status"] in {"draft", "verified"}, r["id"]
        assert r["area"].strip(), r["id"]


def test_every_verdict_class_is_represented():
    overall = [r["overall_verdict"] for r in rows()]
    assert overall.count("breach") >= 1
    assert overall.count("compliant") >= 1
    assert overall.count("needs_review") >= 1


def test_claim_labels_are_well_formed():
    for rid, c in all_claims():
        assert c["verdict"] in VERDICTS, rid
        assert c["rules"], rid
        assert c["rationale"].strip(), rid
        assert isinstance(c["rules_in_corpus"], bool), rid


def test_overall_verdict_is_worst_case_of_claims():
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
def test_rules_in_corpus_flag_matches_corpus():
    # both directions: a True claim citing an absent rule would silently vanish from
    # retrieval scoring; a False claim citing a present rule would corrupt the
    # skip accounting the adoption decision relies on.
    corpus = {
        json.loads(l)["rule_id"]
        for f in CHUNKS_DIR.glob("*.jsonl")
        for l in f.read_text(encoding="utf-8").splitlines()
        if l
    }
    for rid, c in all_claims():
        normalized = {normalize_rule_id(rule) for rule in c["rules"]}
        if c["rules_in_corpus"]:
            assert normalized <= corpus, (rid, normalized - corpus)
        else:
            assert not normalized & corpus, (rid, normalized & corpus)


@pytest.mark.skipif(
    not FG15_04_TXT.exists() or not CHUNKS_DIR.exists(),
    reason="local sources not present (data/ is local-only)",
)
def test_authority_quotes_verbatim_from_source():
    # FG15/4-sourced quotes must be verbatim in the extracted guidance text;
    # Handbook-sourced quotes (owner-ruled claims) verbatim in the ingested corpus.
    collapse = lambda s: " ".join(s.split())  # noqa: E731 — whitespace-collapse tolerance
    fg = collapse(FG15_04_TXT.read_text(encoding="utf-8"))
    corpus_text = collapse(
        " ".join(
            json.loads(l)["text"]
            for f in sorted(CHUNKS_DIR.glob("*.jsonl"))
            for l in f.read_text(encoding="utf-8").splitlines()
            if l
        )
    )
    for rid, c in all_claims():
        auth = c["label_authority"]
        source = fg if auth["url"] == FG15_04_URL else corpus_text
        assert collapse(auth["quote"]) in source, rid


@pytest.mark.skipif(
    not (ROOT / "data" / "sources" / "fg15-04-annotated").exists(),
    reason="annotated transcriptions not present (data/ is local-only)",
)
def test_input_text_is_verbatim_transcription():
    for r in rows():
        assert r["input_text"] == (ROOT / r["source_media"]).read_text(encoding="utf-8"), r["id"]
