"""Score retrieval against the golden set: recall@k, hit@k, MRR per mode.

Usage: python -m sentinel.eval_retrieval [--mode bm25|dense|hybrid|all]
Ground truth is each claim's cited rule ids, normalized to chunk granularity.
"""

import json
from pathlib import Path

KS = (3, 5, 10)


def normalize_rule_id(rule: str) -> str:
    """'CONC 3.3.4G(2)' -> 'CONC 3.3.4' (the chunker's rule_id granularity)."""
    base = rule.split("(")[0].strip()
    if base.endswith(("R", "G")) and base[-2].isdigit():
        base = base[:-1]
    return base


def score(relevant: set[str], retrieved: list[str]) -> dict:
    out = {}
    for k in KS:
        top = set(retrieved[:k])
        out[f"recall@{k}"] = len(relevant & top) / len(relevant)
        out[f"hit@{k}"] = 1.0 if relevant & top else 0.0
    out["mrr"] = next((1 / (i + 1) for i, r in enumerate(retrieved) if r in relevant), 0.0)
    return out


def load_claims(golden_path: Path, corpus_rule_ids: set[str]) -> tuple[list[dict], int]:
    """One eval query per golden claim; claims whose cited rules are absent from the corpus are skipped and counted."""
    claims, skipped = [], 0
    for line in golden_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        example = json.loads(line)
        for c in example["claims"]:
            relevant = {normalize_rule_id(r) for r in c["rules"]} & corpus_rule_ids
            if relevant:
                claims.append({"query": c["claim"], "relevant": relevant, "area": example["area"]})
            else:
                skipped += 1
    return claims, skipped
