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

## Metrics (v2 re-baseline, 2026-08-10)

Scored against the v2 golden set (26 examples / 34 claims) on both provider arms, both
at 768 embedding dims: **Gemini** (`gemini-embedding-001` dense / `gemini-3.5-flash-lite`
judge — the Phase 3 incumbent, run as the v2 control before its vectors were
overwritten) and **Azure** (`text-embedding-3-large` dense / `gpt-4.1-mini` judge — the
production target). Corpus: CONC 3, 86 chunks, 0 claims skipped on either provider.
Predictions for every number below were pre-registered *before* any v2 run — see the
scorecard.

### Retrieval

`python -m sentinel.eval_retrieval --mode all`, one query per golden claim, ground truth
= the claim's cited rule ids at chunk granularity.

**Gemini (control)**

| mode | recall@3 | recall@5 | recall@10 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|---|---|
| bm25 | 0.760 | 0.789 | 0.868 | 0.882 | 0.941 | 0.971 | 0.744 |
| dense | 0.794 | 0.809 | 0.824 | 0.853 | 0.882 | 0.882 | 0.782 |
| hybrid (RRF) | 0.676 | 0.809 | 0.912 | 0.824 | 0.912 | 1.000 | 0.784 |
| weighted (α=0.5) | 0.775 | 0.882 | 0.912 | 0.941 | 1.000 | 1.000 | 0.827 |

**Azure (text-embedding-3-large @768)**

| mode | recall@3 | recall@5 | recall@10 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|---|---|
| bm25 | 0.760 | 0.789 | 0.868 | 0.882 | 0.941 | 0.971 | 0.744 |
| dense | 0.593 | 0.740 | 0.882 | 0.765 | 0.882 | 0.941 | 0.674 |
| hybrid (RRF) | 0.775 | 0.814 | 0.912 | 0.941 | 0.971 | 1.000 | 0.824 |
| weighted (α=0.5) | 0.804 | 0.814 | 0.926 | 0.971 | 0.971 | 1.000 | 0.833 |

BM25 rows are identical between providers by construction (BM25 never touches
embeddings) — a sanity check that both runs share the same corpus and query set.

**The price of residency is real, measured at dense, and mostly recovered by fusion.**
Azure's dense arm trails Gemini's on both gated metrics: recall@5 −0.069 (.740 vs
.809), MRR −0.108 (.674 vs .782). The gap has a qualitative face, not just a numeric
one: `prominence-review` recall@3 on Azure dense is **0.000** (MRR .217) against
Gemini dense's 1.000 (MRR .778) — Azure's embedding space misses this area entirely at
top-3, not just proportionally. Fusion narrows or reverses the gap depending on the
metric: hybrid's recall@5 flips to Azure ahead (.814 vs .809, +.005) and hybrid's MRR
flips Azure ahead too (.824 vs .784, +.040); weighted's MRR also flips Azure ahead
(.833 vs .827, +.006), though weighted's recall@5 gap persists (.814 vs .882, −.068) —
not because Azure's own fusion underperforms (within-provider, weighted lifts Azure
dense by +.074 recall@5 and Gemini dense by +.073, essentially the same absolute gain)
but because Gemini's weighted arm is the single best number in either table.

**BM25's near-tie with dense reverses a v1 conclusion.** v1 measured naive dense
comfortably ahead of BM25 on paraphrased claims; v2's FCA-sourced claims share verbatim
vocabulary with the guidance text itself ("guaranteed", "pre-approved",
"representative"), and BM25 comes within .02 of dense recall@5 overall (.789 vs .809
Gemini; .789 vs .740 Azure — BM25 actually *beats* Azure dense outright). BM25 wins
`guaranteed-3.3` cleanly on both providers: recall@5 .682 vs dense .591 (Gemini), .682
vs .455 (Azure) — a full reversal of which arm is stronger on that area, not a
noise-sized wobble.

**Weighted α=0.5 is the only arm beating dense on both gated metrics on both
providers**: Gemini .882/.827 vs dense .809/.782; Azure .814/.833 vs dense .740/.674.
(Hybrid comes close but only ties Gemini's dense recall@5, .809 = .809, rather than
beating it.) This matters because of what α=0.5 *isn't*: v1's weighted arm only won by
sweeping to α=0.9 on the same golden set that scored it, and was explicitly held back
from adoption for exactly that reason (see git history, commit `0baf070`) — a
hyperparameter tuned on the only labelled data available isn't evidence of a real win.
v2's α=0.5 is the pre-registered default, never swept or tuned on this or any golden
set, and it still clears dense on both metrics on both providers. That's a
categorically stronger claim to adoption than v1 had. It is still not adopted here —
held pending a holdout set, the same standard v1's α=0.9 was (and wasn't) held to.

### Judge accuracy

`python -m sentinel.eval_judge --mode judge`, golden claims fed straight to the judge
(decomposer bypassed), dense top-5 retrieval per provider, judge responses disk-cached.

| | Gemini (`gemini-3.5-flash-lite`) | Azure (`gpt-4.1-mini`) |
|---|---|---|
| accuracy | 0.971 (33/34) | 0.971 (33/34) |
| citation_hit | 0.882 | 0.882 |
| breach precision/recall (n=25) | 1.000 / 1.000 | 1.000 / 1.000 |
| compliant precision/recall (n=6) | 1.000 / 0.833 | 1.000 / 0.833 |
| needs_review precision/recall (n=3) | 0.750 / 1.000 | 0.750 / 1.000 |

Confusion matrices are **identical** across providers: `{breach→breach: 25,
compliant→compliant: 5, compliant→needs_review: 1, needs_review→needs_review: 3}`. The
one miss both judges make is the same one, in the conservative direction (a compliant
claim routed to human review, never the reverse). Per-area accuracy matches exactly
too: apr-triggers-3.5 1.000, broker-3.7 0.667, guaranteed-3.3 1.000, hcstc-warning-3.4
1.000, prominence-review 1.000, rep-example-3.5 1.000.

This cross-family agreement — a Google model and an OpenAI model landing on the same
verdict for the same claim, error included — is evidence the v2 labels are
**model-robust**, checkable by more than one judge family rather than an artifact of
one model's quirks. That's the exact property v1's headline number lacked: v1's
accuracy measured agreement between LLM-generated labels and an LLM judge, which is
agreement with itself, not with ground truth. v2's agreement is between two independent
judge families and FCA-anchored ground truth.

### End-to-end

`python -m sentinel.eval_judge --mode e2e`, full graph (decompose → retrieve → judge →
HITL gate) against all 26 golden examples, Azure only (see honesty check below).

| metric | value |
|---|---|
| overall_accuracy | 0.308 (8/26) |
| mean_claim_delta | 3.00 |

Per-component judge accuracy is .971; end-to-end is .308. That 0.663 gap is the
measured size of an architecture mismatch, root-caused offline via a decompose-cache
readback: **0 of 26 decompositions contain any omission-style claim, while 13 of the 17
gold `breach` examples are omission breaches** — the decomposer's prompt asks what the
ad *says*; the golden labels ask what it *fails to say*. No amount of judge or
retrieval tuning fixes a claim the decomposer never extracts in the first place.
Next-phase lever: an omission-aware decompose step — operationalizing the FCA's own
promotion checklist (the same document several `label_authority` blocks above already
cite) rather than inventing a new detection heuristic.

Honesty check on scope: this number is Azure-only. The Gemini e2e control was not run
(judge quota). The root cause is argued from the decompose prompt and cache contents,
not from a paired Gemini e2e run — it reads as prompt-structural (the decomposer's
instructions, not the embedding or judge provider) rather than provider-specific, but
that inference is one un-run experiment short of proof.

**Demo smoke** (`uv run python -m sentinel.audit "Get a loan in 5 minutes! No credit
check impact!"`, Azure end-to-end): PASS. The HITL gate interrupted on real input,
routing the claim to human review over `CONC 3.6.7G` rather than forcing a confident
breach/compliant call — the gate firing on genuine ambiguity, not a canned example, for
the first time in a demo run.

### Prediction scorecard

Predictions were pre-registered before any v2 run. Scoring them here, no post-hoc
smoothing — including the one that's easy to quietly drop:

| # | prediction | actual | verdict |
|---|---|---|---|
| 1 | Gemini dense recall@5 ≈ 0.65 | 0.809 | **WRONG — low** (off by .159) |
| 2 | Azure dense recall@5 ≈ 0.68, edges Gemini | 0.740, *trails* Gemini (.809) | **WRONG — magnitude and direction** |
| 3 | BM25 recall@5 ≈ 0.55, gap to dense narrows | 0.789 (near-tie with dense) | direction right, **magnitude badly under** (off by .239) |
| 4 | hybrid ≤ dense | Gemini: .809 = .809 (tie); Azure: .814 > .740 | **MIXED** |
| 5 | judge accuracy: Azure ≈ 0.88, Gemini ≈ 0.84 | both 0.971 | **both UNDER** (by .091, .131) |
| 6 | e2e ≈ 0.81 (21/26) | 0.308 (8/26) | **badly WRONG** (off by .502) |
| 7 | citation_hit ≈ dense recall@5 (retrieval ceiling reasserts itself) | citation_hit .882 both providers; dense recall@5 .809 (Gemini) / .740 (Azure) — citation_hit didn't move with the metric it was predicted to track | **WRONG on mechanism** |

Row 7's reading: citation_hit only needs the cited rule *anywhere* in the top-5, which
is what hit@5 measures (.882 both providers, matching citation_hit exactly) — not full
recall@5 of every cited rule. The predicted "ceiling" metric was misidentified; hit@5,
not recall@5, is what bounds it. Leaving this row out would have been exactly the
post-hoc smoothing this scorecard exists to prevent.

Every prediction missed low; #2 additionally missed on direction. That's the point of
pre-registering predictions before running the eval — not to be right, but to make it
impossible to quietly rewrite the story after seeing the numbers. This scorecard is the
evidence the discipline is doing something.

### Statistical honesty

n=34 claims. Treat differences under ~.08 recall@5 as noise; several of the "wins"
described above (hybrid vs dense, weighted vs hybrid within a provider) sit inside or
near that band and are described accordingly, not as adoption cases. No arm in this
document is being adopted — that decision is explicitly deferred to a holdout set. The
residency comparison (Gemini vs Azure at dense) used the Gemini incumbent as the
baseline, not an unconstrained frontier embedder; whether Azure's residency cost looks
different against the current best embedding model on the market is open and
unmeasured.

### Operational notes

Azure's Prompt Shields false-positived on the app's own injection-defense wording — the
`UNTRUSTED_INTRO` fencing used to defend against prompt injection reads to the content
filter *as* an injection attempt, blocking 100% of judge calls with HTTP 400. Resolved
with a scoped content filter policy on the judge deployment (jailbreak shield set to
annotate-only; harm-category filters untouched) rather than rewording the prompt, which
would have traded away the hardening just to dodge a false positive. Parallel e2e
fan-out separately needed judge capacity raised to 50K TPM. The `ragas` arm remains
Gemini-backed by design — a demoted, optional metric group, not re-baselined on Azure
this round, because the Phase 3 analysis found off-the-shelf faithfulness mis-measures
this task shape (rationales must reference the claim under assessment, which is never
present in the retrieved contexts).
