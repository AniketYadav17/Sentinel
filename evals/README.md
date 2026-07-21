# Golden dataset

Hand-labelled audit examples used as ground truth for every eval in this repo (retrieval quality, judge accuracy, end-to-end). Built *before* the pipeline, on purpose: the pipeline gets graded against this, never the other way round.

## Schema (`golden.jsonl`, one JSON object per line)

| field | meaning |
|---|---|
| `id` | stable id, `gold-NNN` |
| `channel` | `promo_email` \| `promo_social` \| `tnc` \| `support_reply` |
| `input_text` | the customer communication being audited (treated as untrusted input) |
| `claims[]` | per-claim label: `claim`, `verdict` (`breach`/`compliant`/`needs_review`), `severity` (`high`/`medium`/`low`/null), `rules` (FCA Handbook rule ids), `rationale` |
| `overall_verdict` | worst-case of the claim verdicts |
| `status` | `draft` → `verified` once checked against the live handbook |
| `notes` | anything a future labeller needs |

## Labelling protocol

1. Draft labels cite rules from verified secondary sources (FCA PS15/23, G-Regs CONC checklist — both quote rule ids directly from the handbook).
2. Drafts get an automated cross-check against live handbook text (fetched via the same API the ingestion pipeline uses); `citation_checked: true` means that pass confirmed the cited rules exist and support the verdict. It already caught real drift: secondary sources cite the pre-2020 CONC 3.5.7R numbering (the speed/ease trigger moved from 3.5.7R(3) to 3.5.7R(1)(c)).
3. Every example is then verified by hand against the live handbook (https://www.handbook.fca.org.uk/handbook/CONC/3/) — rule text read, rule id confirmed, verdict re-judged — before `status` flips to `verified`. Corrections during this pass are expected and are the point; unresolved caveats live in `notes`.
4. `needs_review` is a first-class verdict, not a cop-out: some determinations (e.g. prominence under CONC 3.2.3G) genuinely cannot be made from text alone. The system is supposed to route these to a human, so the golden set must contain them.

The handbook changes over time; rule ids in labels are as-verified on the date the example was verified. Re-verification is a job for the (planned) source-freshness monitor.

## Coverage so far

56 draft examples across five areas: CONC 3.3 misleading promotions (payday/broker copy), CONC 3.5 rep-example and representative-APR triggers (loans/car finance), CONC 3.5.12R interest-free claims (BNPL/retail), CONC 3.3.1R comms accuracy (credit cards, support replies and T&Cs), CONC 3.4 HCSTC risk warnings. Overall verdicts: 36 breach / 11 compliant / 9 needs_review. Next: BCOBS, and adversarial/injection cases as a separate suite.

## Retrieval metrics (trade-off study v1, 2026-07-21)

Scored by `python -m sentinel.eval_retrieval --mode all` — one query per golden
claim, ground truth = the claim's cited rule ids at chunk granularity. Corpus:
CONC 3 (86 chunks, gemini-embedding-001 @ 768 dims). 199 claims scored,
0 skipped.

| mode | recall@3 | recall@5 | recall@10 | hit@5 | MRR |
|---|---|---|---|---|---|
| bm25 | 0.300 | 0.398 | 0.466 | 0.497 | 0.355 |
| dense | **0.441** | **0.497** | **0.550** | **0.573** | **0.458** |
| hybrid (RRF) | 0.385 | 0.453 | 0.543 | 0.553 | 0.445 |

Honest headline: **dense-only beats naive RRF hybrid** on this corpus — the
weak BM25 arm dilutes fusion at the top ranks (hybrid only edges ahead on
hit@10, 0.623 vs 0.608). Weakest area across all modes is comms-accuracy
(subtle support-reply/T&C language). Recall@5 ≈ 0.50 leaves clear headroom, so
per the spec the next measured arms are a cross-encoder reranker and weighted
fusion — see `docs/superpowers/specs/2026-07-21-phase2-retrieval-design.md`.
