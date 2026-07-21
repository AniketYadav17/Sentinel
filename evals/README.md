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
