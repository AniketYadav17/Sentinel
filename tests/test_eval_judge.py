import json

import sentinel.eval_judge as ej


def row(gold_v, pred_v, gold_sev=None, pred_sev=None, gold_rules=None, pred_rules=None):
    return {
        "gold": {"verdict": gold_v, "severity": gold_sev},
        "pred": {"verdict": pred_v, "severity": pred_sev, "rule_ids": pred_rules or []},
        "gold_rules_norm": set(gold_rules or []),
        "area": "misleading-3.3",
    }


def test_accuracy_and_confusion():
    rows = [row("breach", "breach"), row("breach", "compliant"), row("compliant", "compliant"), row("needs_review", "needs_review")]
    m = ej.judge_metrics(rows)
    assert m["accuracy"] == 0.75
    assert m["confusion"][("breach", "compliant")] == 1
    assert m["per_class"]["breach"]["recall"] == 0.5
    assert m["per_class"]["compliant"]["precision"] == 0.5


def test_severity_agreement_only_on_agreed_breaches():
    rows = [row("breach", "breach", "high", "high"), row("breach", "breach", "high", "low"), row("breach", "compliant", "high", None)]
    assert ej.judge_metrics(rows)["severity_agreement"] == 0.5


def test_citation_hit_uses_normalized_overlap():
    rows = [row("breach", "breach", gold_rules=["CONC 3.3.1"], pred_rules=["CONC 3.3.1R(1)"]),
            row("breach", "breach", gold_rules=["CONC 3.5.3"], pred_rules=["CONC 3.3.1R"])]
    assert ej.judge_metrics(rows)["citation_hit"] == 0.5


def test_empty_rows_all_metrics_zero():
    m = ej.judge_metrics([])
    assert m["n"] == 0 and m["accuracy"] == 0.0 and m["confusion"] == {} and m["by_area"] == {}


def test_load_golden_claims(tmp_path):
    example = {"id": "gold-001", "channel": "promo_email", "input_text": "t", "area": "misleading-3.3",
               "claims": [{"claim": "c", "verdict": "breach", "severity": "high", "rules": ["CONC 3.3.1R"], "rationale": "r"}],
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
