"""Judge-accuracy evals against the golden set.

Usage: python -m sentinel.eval_judge --mode judge|e2e|ragas
judge (primary): golden claims fed straight to the judge — deterministic 199-claim comparison.
Retrieval ceiling applies: dense recall@5 ~= .50 bounds citation_hit (that is 3b's job).
"""

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from sentinel.audit import JUDGE_SCHEMA, TOP_K, judge_prompt
from sentinel.eval_retrieval import normalize_rule_id, query_vectors
from sentinel.index import Index
from sentinel.llm import generate_json

VERDICTS = ("breach", "compliant", "needs_review")
RESULTS_PATH = Path(__file__).parents[2] / "data" / "cache" / "judge_results.jsonl"


def load_golden_claims(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        ex = json.loads(line)
        for c in ex["claims"]:
            out.append({"claim": c["claim"], "verdict": c["verdict"],
                        "rules": c["rules"], "area": ex["area"], "channel": ex["channel"],
                        "input_text": ex["input_text"]})
    return out


def judge_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    confusion = Counter((r["gold"]["verdict"], r["pred"]["verdict"]) for r in rows)
    per_class = {}
    for v in VERDICTS:
        tp = confusion[(v, v)]
        gold_n = sum(c for (g, _), c in confusion.items() if g == v)
        pred_n = sum(c for (_, p), c in confusion.items() if p == v)
        per_class[v] = {"recall": tp / gold_n if gold_n else 0.0,
                        "precision": tp / pred_n if pred_n else 0.0, "n": gold_n}
    cited = [r for r in rows if r["gold_rules_norm"]]
    by_area = defaultdict(list)
    for r in rows:
        by_area[r["area"]].append(r["gold"]["verdict"] == r["pred"]["verdict"])
    return {
        "n": n,
        "accuracy": (sum(r["gold"]["verdict"] == r["pred"]["verdict"] for r in rows) / n) if n else 0.0,
        "confusion": dict(confusion),
        "per_class": per_class,
        "citation_hit": (sum(bool(r["gold_rules_norm"] & {normalize_rule_id(x) for x in r["pred"]["rule_ids"]})
                             for r in cited) / len(cited)) if cited else 0.0,
        "by_area": {a: sum(v) / len(v) for a, v in sorted(by_area.items())},
    }


def print_metrics(m: dict) -> None:
    print(f"\n== judge accuracy ({m['n']} claims) ==")
    print(f"accuracy {m['accuracy']:.3f}  citation_hit {m['citation_hit']:.3f}")
    for v, s in m["per_class"].items():
        print(f"  {v:<13} precision {s['precision']:.3f}  recall {s['recall']:.3f}  (n={s['n']})")
    print("  confusion (gold -> pred):", {f"{g}->{p}": c for (g, p), c in sorted(m["confusion"].items())})
    for a, acc in m["by_area"].items():
        print(f"  {a:<22} accuracy {acc:.3f}")
    print("note: citation_hit is bounded by retrieval recall@5 (~.50 dense) — see trade-off table")


def run_judge_mode(root: Path) -> None:
    index = Index.load(root / "data")
    claims = load_golden_claims(root / "evals" / "golden.jsonl")
    vectors = query_vectors([c["claim"] for c in claims], root / "data" / "embeddings" / "queries.jsonl")
    rows = []
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = RESULTS_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for c, v in zip(claims, vectors):
            provisions = index.search_dense(v, TOP_K)
            pred = generate_json(judge_prompt(c["claim"], c["channel"], c["input_text"], provisions), JUDGE_SCHEMA)
            row = {"gold": {"verdict": c["verdict"]}, "pred": pred,
                   "gold_rules_norm": {normalize_rule_id(r) for r in c["rules"]}, "area": c["area"]}
            rows.append(row)
            f.write(json.dumps({"claim": c["claim"], "pred": pred, "area": c["area"],
                                "contexts": [p["text"] for p in provisions]}) + "\n")
    os.replace(tmp, RESULTS_PATH)
    print_metrics(judge_metrics(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("judge", "e2e", "ragas"), default="judge")
    args = parser.parse_args()
    root = Path(__file__).parents[2]
    if args.mode == "judge":
        run_judge_mode(root)
    elif args.mode == "e2e":
        from sentinel.eval_judge_e2e import run_e2e_mode  # Task 5

        run_e2e_mode(root)
    else:
        from sentinel.eval_judge_ragas import run_ragas_mode  # Task 5

        run_ragas_mode(root)


if __name__ == "__main__":
    main()
