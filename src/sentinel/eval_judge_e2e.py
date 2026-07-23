"""End-to-end eval (secondary): full graph per golden example, example-level scoring only."""

import json
from pathlib import Path

from langgraph.types import Command


def e2e_rows(examples: list[dict], run_example) -> dict:
    if not examples:
        return {"n": 0, "overall_accuracy": 0.0, "mean_claim_delta": 0.0}
    hits, deltas = [], []
    for ex in examples:
        report = run_example(ex)
        hits.append(report["overall"] == ex["overall_verdict"])
        deltas.append(abs(len(report["claims"]) - len(ex["claims"])))
    return {"n": len(examples), "overall_accuracy": sum(hits) / len(hits), "mean_claim_delta": sum(deltas) / len(deltas)}


def run_e2e_mode(root: Path) -> None:
    from sentinel.audit import build_graph, default_searcher

    graph = build_graph(default_searcher())
    examples = [json.loads(l) for l in (root / "evals" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l]

    def run_example(ex: dict) -> dict:
        config = {"configurable": {"thread_id": ex["id"]}}
        state = graph.invoke({"text": ex["input_text"], "channel": ex["channel"]}, config)
        if "__interrupt__" in state:  # eval is unattended: keep judged verdicts, no human override
            state = graph.invoke(Command(resume={}), config)
        return state["report"]

    m = e2e_rows(examples, run_example)
    print(f"\n== e2e ({m['n']} examples) ==\noverall_accuracy {m['overall_accuracy']:.3f}  mean_claim_delta {m['mean_claim_delta']:.2f}")
