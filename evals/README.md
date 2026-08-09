# Golden dataset

FCA-sourced audit examples used as ground truth for every eval in this repo. v2 (2026-08)
replaces a v1 set whose labels were LLM-generated end to end and never human-adjudicated —
its headline numbers measured cross-model agreement, not accuracy, so the set and the
numbers were removed together (see git history). The lesson v2 encodes: **provenance, not
syntheticity, is what makes a label trustworthy** — the FCA's own published examples are
explicitly fictitious, yet authoritative, because the FCA wrote them.

## Sources

Every label is anchored to an FCA publication via a per-claim `label_authority` block:

- [Dear CEO letter: financial promotions of high-cost lending products, 6 May 2022](https://www.fca.org.uk/publication/correspondence/dear-ceo-ensure-your-financial-promotions-clear-fair-not-misleading.pdf) — breach patterns with verbatim phrases mapped to named CONC rules.
- [Car finance case study transcript](https://www.fca.org.uk/publication/documents/transcript-case-study-1-car-finance-video.pdf) — the FCA's own promotion checklist.
- The [FCA Handbook, CONC 3](https://www.handbook.fca.org.uk/handbook/CONC/3/) live text (compliant controls cite the operative rule wording directly).

## Schema (`golden.jsonl`, one JSON object per line)

| field | meaning |
|---|---|
| `id` | stable id, `gold-1NN` (v2 numbering) |
| `channel` | `promo_email` \| `promo_social` \| `promo_web` — promotions only, by scope decision |
| `input_text` | the financial promotion being audited (treated as untrusted input) |
| `claims[]` | per-claim label: `claim`, `verdict` (`breach`/`compliant`/`needs_review`), `rules`, `rationale`, `label_authority` |
| `claims[].label_authority` | `{source, url, quote, rule_cited_by_source, verification}` — the FCA provenance for this label; `quote` is verbatim from the source |
| `overall_verdict` | worst-case of the claim verdicts (test-enforced) |
| `status` | `verified` = the dataset owner has personally checked this example's quotes and rule texts; `draft` = that per-example pass is pending (every label is machine-verified for provenance and twice independently reviewed regardless) |
| `notes` | what a future re-verifier should re-check |

## Labelling protocol

1. **Mechanical rules only.** Every verdict must be checkable by reading the cited rule
   text against the promotion text. Judgement calls ("is this misleading?") are out of
   scope — the labeller is an engineer, not a compliance officer, and the dataset does
   not pretend otherwise. Prominence questions are `needs_review` by construction
   (`verification: "judgement"`).
2. Each breach pattern comes from an FCA publication that names both the pattern and the
   rule; `label_authority.quote` carries the verbatim sentence.
3. Rule ids are verified against the live corpus text (`data/chunks/`) before citing;
   `tests/test_golden.py` mechanically enforces the structural half of this protocol
   (schema, worst-case aggregation, authority completeness, corpus membership).
4. Regulation drifts: CP26/15 (2026) is consulting on exactly these CONC 3 provisions.
   Labels are as-verified on their commit date; re-verification is the (planned)
   freshness monitor's job.
5. Documented conventions, each ruled on by the dataset owner:
   (a) a payday-loan promotion is treated as high-cost short-term credit — the Dear
   CEO letter's own framing; the Glossary's APR limb is not establishable from
   promotion text (disclosed in the affected examples' notes);
   (b) three example pairs (gold-109/124, gold-115/126, gold-120/125) deliberately
   present near-identical facts with one member `compliant` and the other
   `needs_review` — the prominence question is carried by exactly one member of
   each pair, so overall verdicts differ by design, not by error;
   (c) claims are per triggering statement: one promotion firing several limbs of
   the same rule yields one claim per limb (see gold-101's three CONC 3.5.7R
   claims);
   (d) there is no severity field — severity was derivable from the cited rule and
   carried no FCA authority, so it was removed rather than labelled.

## Coverage

26 examples / 34 claims across six areas: guaranteed-approval claims (CONC 3.3.3R),
HCSTC risk warnings (CONC 3.4.1R), representative-APR triggers (CONC 3.5.7R/3.5.8G —
all three limbs of 3.5.7R(1) are exercised), representative-example triggers
(CONC 3.5.5R, car-finance checklist), broker status statements (CONC 3.7.7R), and
prominence needs-review cases. Overall verdicts: 17 breach / 6 compliant /
3 needs_review (claims: 25 / 6 / 3).

Known coverage limits (recorded, not hidden): no example yet exercises CONC 3.5.9R
representative-APR labelling defects, the broker-and-lender limb of CONC 3.7.7R(2),
the transcript's second-"representative"-example pattern, a promotion omitting the
firm's name, the image-promotion side of the CONC 3.1.7R exclusion, or the
CONC 3.5.12R restricted expressions. Expansion is planned for the eval re-baseline,
alongside an FCA-authored holdout extracted from FG15-04's image examples once
multimodal extraction lands.

## Metrics

Re-baselining against this set is pending the provider swap (Gemini → Azure OpenAI) so
the numbers are measured once, not twice. The v1 metric tables were removed with the v1
set — quoting them against deleted ground truth would be exactly the failure mode this
project exists to catch.
