"""Cost and latency report over data/usage.jsonl (written by llm.post on every LIVE call).

Usage: python -m sentinel.usage [--since 2026-08-12T09:00]
Cache hits never reach the transport, so these are first-live-run figures, not per-replay cost.
"""

import argparse
import statistics
import sys
from datetime import datetime, timezone

from sentinel.index import read_jsonl
from sentinel.llm import USAGE_LOG

# USD per 1M tokens (input, output), Azure OpenAI list price. Keyed by DEPLOYMENT name, since
# that is what the transport records. Deliberately not stored in the log: a price change must
# not retroactively rewrite recorded runs.
RATES = {
    "sentinel-judge": (0.40, 1.60),  # gpt-4.1-mini
    "sentinel-embed": (0.13, 0.0),  # text-embedding-3-large
}


def parse_since(text: str) -> float:
    """ISO timestamp -> epoch seconds. Naive input is UTC, matching `date -u` and the log's time.time().

    Reading it as local time (fromisoformat's default) silently under-filters by the UTC offset —
    a filter that quietly returns too much is worse than one that errors.
    """
    stamp = datetime.fromisoformat(text)
    return (stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp).timestamp()


def load(since: float | None) -> list[dict]:
    if not USAGE_LOG.exists():
        sys.exit(f"no usage log at {USAGE_LOG} — run a live call first (cached runs log nothing)")
    return [r for r in read_jsonl(USAGE_LOG) if since is None or r["ts"] >= since]


def summarize(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for row in rows:
        d = out.setdefault(row["deployment"], {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "_ms": []})
        d["calls"] += 1
        d["prompt_tokens"] += row.get("prompt_tokens", 0)
        d["completion_tokens"] += row.get("completion_tokens", 0)
        d["_ms"].append(row["ms"])
    for deployment, d in out.items():
        rate_in, rate_out = RATES.get(deployment, (0.0, 0.0))
        d["rate_known"] = deployment in RATES
        d["usd"] = d["prompt_tokens"] / 1_000_000 * rate_in + d["completion_tokens"] / 1_000_000 * rate_out
        ms = sorted(d.pop("_ms"))
        d["p50_ms"] = statistics.median(ms)
        # below 20 calls quantiles() would interpolate a 95th percentile out of a handful of
        # points — report the max instead, an honest overestimate rather than invented precision
        d["p95_ms"] = ms[-1] if len(ms) < 20 else statistics.quantiles(ms, n=20)[18]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="ISO timestamp in UTC, e.g. 2026-08-12T09:00 — cost one run, not all history")
    args = parser.parse_args()
    since = parse_since(args.since) if args.since else None
    summary = summarize(load(since))
    total = sum(d["usd"] for d in summary.values())
    print(f"\n== live model usage{' since ' + args.since if args.since else ''} ==")
    for deployment, d in sorted(summary.items()):
        flag = "" if d["rate_known"] else "  (no rate on file — cost shown as 0)"
        print(f"  {deployment:<16} {d['calls']:>5} calls  "
              f"in {d['prompt_tokens']:>9,}  out {d['completion_tokens']:>8,}  "
              f"${d['usd']:.4f}  p50 {d['p50_ms']:.0f}ms  p95 {d['p95_ms']:.0f}ms{flag}")
    print(f"  {'TOTAL':<16} {'':>5}        {'':>9}      {'':>8}  ${total:.4f}")


if __name__ == "__main__":
    main()
