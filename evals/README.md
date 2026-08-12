# Golden dataset

FCA-sourced audit examples used as ground truth for every eval in this repo. v2 (2026-08)
replaces a v1 set whose labels were LLM-generated end to end and never human-adjudicated.
Its headline numbers measured cross-model agreement rather than accuracy, so the set and
the numbers were removed together (see git history). What v2 encodes: a label is
trustworthy because of where it came from, not because it is non-synthetic. The FCA's own
published examples are explicitly fictitious and authoritative anyway, because the FCA
wrote them.

## Sources

Every label is anchored to an FCA publication via a per-claim `label_authority` block:

- [Dear CEO letter: financial promotions of high-cost lending products, 6 May 2022](https://www.fca.org.uk/publication/correspondence/dear-ceo-ensure-your-financial-promotions-clear-fair-not-misleading.pdf), breach patterns with verbatim phrases mapped to named CONC rules.
- [Car finance case study transcript](https://www.fca.org.uk/publication/documents/transcript-case-study-1-car-finance-video.pdf), the FCA's own promotion checklist.
- The [FCA Handbook, CONC 3](https://www.handbook.fca.org.uk/handbook/CONC/3/) live text (compliant controls cite the operative rule wording directly).

## The firms in this dataset are invented

Every firm, domain, phone number and address in `golden.jsonl` is fictitious. The
promotions are written to carry the breach patterns the FCA's publications name; no
example describes, quotes or alleges anything about a real business. Before this repo was
first published, all 26 invented names were swept against public sources. The record:

- No exact match for any of the 26 names, in any sector or jurisdiction.
- Nearest real-world neighbours, none of them the same name, listed so the check is
  auditable rather than asserted: Otter Vale Motor Services Ltd (Honiton; a real used-car
  dealer that offers finance, and the closest collision in the set, one space away from
  this dataset's "Ottervale Car Finance"), Copperfin Credit Union (Ontario), Bramblegate
  Limited (a UK non-trading company, dissolved January 2026), The Redshank Group Ltd
  (Portsmouth, IT services), Thistlemoor Medical Centre (Peterborough), Tarnwell Polska
  (Polish plastics manufacturer).
- Domains: all ten invented `.co.uk` domains fail to resolve. None is a live site.
- Phone number: the one number in the set, `0161 496 0210`, sits inside Ofcom's
  reserved drama range for Manchester (`0161 496 0000` to `0999`), which exists so that
  fiction never dials a real line.
- Addresses: real postcode districts, invented street names (there is no Dockside Walk
  in M4). No example address resolves to a real premises.

Re-run this sweep before adding any new named firm.

## Schema (`golden.jsonl`, one JSON object per line)

| field | meaning |
|---|---|
| `id` | stable id, `gold-1NN` (v2 numbering) |
| `channel` | `promo_email` \| `promo_social` \| `promo_web`; promotions only, by scope decision |
| `input_text` | the financial promotion being audited (treated as untrusted input) |
| `claims[]` | per-claim label: `claim`, `verdict` (`breach`/`compliant`/`needs_review`), `rules`, `rationale`, `label_authority` |
| `claims[].label_authority` | `{source, url, quote, rule_cited_by_source, verification}`, the FCA provenance for this label; `quote` is verbatim from the source |
| `overall_verdict` | worst-case of the claim verdicts (test-enforced) |
| `status` | `verified` = the dataset owner has personally checked this example's quotes and rule texts; `draft` = that per-example pass is pending (every label is machine-verified for provenance and twice independently reviewed regardless) |
| `notes` | what a future re-verifier should re-check |

## Labelling protocol

1. Mechanical rules only. Every verdict must be checkable by reading the cited rule
   text against the promotion text. Judgement calls ("is this misleading?") are out of
   scope, because the labeller is an engineer, not a compliance officer, and the dataset
   does not pretend otherwise. Prominence questions are `needs_review` by construction
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
   (a) a payday-loan promotion is treated as high-cost short-term credit, the Dear
   CEO letter's own framing; the Glossary's APR limb is not establishable from
   promotion text (disclosed in the affected examples' notes);
   (b) three example pairs (gold-109/124, gold-115/126, gold-120/125) deliberately
   present near-identical facts with one member `compliant` and the other
   `needs_review`. The prominence question is carried by exactly one member of
   each pair, so overall verdicts differ by design, not by error;
   (c) claims are per triggering statement: one promotion firing several limbs of
   the same rule yields one claim per limb (see gold-101's three CONC 3.5.7R
   claims);
   (d) there is no severity field. Severity was derivable from the cited rule and
   carried no FCA authority, so it was removed rather than labelled.

## Coverage

26 examples / 34 claims across six areas: guaranteed-approval claims (CONC 3.3.3R),
HCSTC risk warnings (CONC 3.4.1R), representative-APR triggers (CONC 3.5.7R/3.5.8G,
where all three limbs of 3.5.7R(1) are exercised), representative-example triggers
(CONC 3.5.5R, car-finance checklist), broker status statements (CONC 3.7.7R), and
prominence needs-review cases. Overall verdicts: 17 breach / 6 compliant /
3 needs_review (claims: 25 / 6 / 3).

Known coverage limits: no example yet exercises CONC 3.5.9R representative-APR
labelling defects, the broker-and-lender limb of CONC 3.7.7R(2), the transcript's
second-"representative"-example pattern, a promotion omitting the firm's name, the
image-promotion side of the CONC 3.1.7R exclusion, or the CONC 3.5.12R restricted
expressions. Expansion is planned for a future re-baseline. The FCA-authored holdout
extracted from FG15-04's image examples has landed; see the next section.

## The FG15-04 holdout

Every number in this document so far is scored against the golden set that also
motivated the changes being measured, which makes it an eval set and not a holdout. The
multimodal phase built an independent check: nine promotion images from the FCA's own
2015 social-media guidance, [FG15/4](https://www.fca.org.uk/publication/finalised-guidance/fg15-04.pdf),
turned into ground truth through the same seam the multimodal slice ships
(`extract.py`'s vision call, wired into the audit CLI via `--media`). The transcription
is verbatim and layout-annotated, with `[position · relative size · emphasis or
contrast]` prefixed on every line, so that prominence facts (font size, contrast,
position) enter the audit graph *in-band*, as text, instead of being invisible to a
text-only pipeline the way the two `prominence-review` golden misses are (see
"Tuning" below).

Composition: 9 examples / 13 claims / 3 corpus-mappable. The low corpus-mappable
count has a structural reason rather than an authoring one. FG15/4's example images
are overwhelmingly investment and spread-betting promotions (five investment
examples, three spread-betting examples), and exactly one, the Figure 6 "logbook
lender" tweet, is a consumer-credit promotion inside CONC 3's scope. All 3
corpus-mappable claims come from that single image; the other 10 claims cite
COBS/PRIN/FSMA provisions the CONC 3 corpus was never built to answer, and are marked
`rules_in_corpus: false` by construction, kept as judge context and excluded from
retrieval scoring. Overall verdicts: 2 breach / 5 compliant / 2 needs_review.

One figure was deliberately excluded. FG15/4's Figure 9 is a grid of tweets each
carrying the FCA's own per-tweet verdict label ("Non-compliant – promotional",
"Compliant – promotional", and so on) baked into the image content itself. It was left
out of the dataset entirely, because transcribing it verbatim as `input_text` would hand
the system under evaluation the answer key.

Two rulings needed a human, and both are disclosed in the dataset's own notes.
FG15/4 presents its Figure 6 example without any verdict label (its caption is just
"Consumer Credit inserted images example"), so the two compliant calls on that image
are *inferred* from the annotated content mechanically satisfying current CONC
3.5.7R/3.5.8G(4)/3.5.3R(2) rather than FCA-stated, and that inference was owner-ratified
before any holdout number existed. Separately, the same image shows a rate (RAPR
209.8%) but no visible postal address. Whether CONC 3.5.3R(1)(b)'s postal-address
requirement is satisfied cannot be determined from an inserted-image fragment alone,
so that claim is carried as `needs_review`, an owner ruling also made and disclosed
before any holdout number existed.

Drift, checked per rule against the current corpus text. CONC 3.4.1R(2), the
provision FG15/4's annex discusses in the context of a since-closed consultation, now
reads "[deleted]" in the live Handbook; no holdout claim rests on it (Figure 6's
logbook credit is excluded from the HCSTC definition it used to qualify). CONC 3.5.7R
and CONC 3.5.3R, the two rules the holdout does claim on, both gained limbs since
2015: CONC 3.5.7R added a payment-account cash-sum carve-out and further exclusions
(overdrafts, 0%-APR agreements, community finance organisations), and CONC 3.5.3R
added a 0%-APR-only exemption. None of the additions touches the Figure 6 promotion.

Power limits. The retrieval half of any holdout comparison rests on 3 claims that all
come from one promotion, effectively n=1 at the level that matters (a distinct
promotion, not a distinct claim), nowhere near enough to adjudicate a retrieval-fusion
decision. The e2e half covers all 9 examples, but at that size one example is worth
about 11 percentage points of accuracy, so a result that moves by one example is a
result at the edge of what nine examples can say anything about. Both limits are why
the adjudication rules for this holdout were pre-registered *before* any holdout number
existed (see the next section).

## Metrics (v2 re-baseline, 2026-08-10)

Scored against the v2 golden set (26 examples / 34 claims) on both provider arms, both
at 768 embedding dims: Gemini (`gemini-embedding-001` dense / `gemini-3.5-flash-lite`
judge, the Phase 3 incumbent, run as the v2 control before its vectors were
overwritten) and Azure (`text-embedding-3-large` dense / `gpt-4.1-mini` judge, the
production target). Corpus: CONC 3, 86 chunks, 0 claims skipped on either provider.
Predictions for every number below were pre-registered *before* any v2 run; see the
scorecard.

### Retrieval

`python -m sentinel.eval_retrieval --mode all`, one query per golden claim, ground truth
= the claim's cited rule ids at chunk granularity.

Four arms ship: `bm25`, `dense`, `hybrid` (RRF), `weighted`. Two more were built and
measured on the v1 dataset and failed their gate there: a cross-encoder reranker
(`ms-marco-MiniLM-L-6-v2`) and contextual-blurb embeddings (`dense-ctx`, one generated
blurb prepended per chunk before embedding). Their numbers were deleted with the rest of
v1 in the ground-truth rebuild, and the code came out at the v2 close rather than being
carried as Gemini-era arms that crash if run. Both are recoverable from git history if
either is ever re-measured against v2.

Gemini (control)

| mode | recall@3 | recall@5 | recall@10 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|---|---|
| bm25 | 0.760 | 0.789 | 0.868 | 0.882 | 0.941 | 0.971 | 0.744 |
| dense | 0.794 | 0.809 | 0.824 | 0.853 | 0.882 | 0.882 | 0.782 |
| hybrid (RRF) | 0.676 | 0.809 | 0.912 | 0.824 | 0.912 | 1.000 | 0.784 |
| weighted (α=0.5) | 0.775 | 0.882 | 0.912 | 0.941 | 1.000 | 1.000 | 0.827 |

Azure (text-embedding-3-large @768)

| mode | recall@3 | recall@5 | recall@10 | hit@3 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|---|---|---|
| bm25 | 0.760 | 0.789 | 0.868 | 0.882 | 0.941 | 0.971 | 0.744 |
| dense | 0.593 | 0.740 | 0.882 | 0.765 | 0.882 | 0.941 | 0.674 |
| hybrid (RRF) | 0.775 | 0.814 | 0.912 | 0.941 | 0.971 | 1.000 | 0.824 |
| weighted (α=0.5) | 0.804 | 0.814 | 0.926 | 0.971 | 0.971 | 1.000 | 0.833 |

BM25 rows are identical between providers by construction (BM25 never touches
embeddings), a sanity check that both runs share the same corpus and query set.

The price of residency is real, it is measured at dense, and fusion recovers most of it.
Azure's dense arm trails Gemini's on both gated metrics: recall@5 -0.069 (.740 vs
.809), MRR -0.108 (.674 vs .782). The gap also has a qualitative face:
`prominence-review` recall@3 on Azure dense is 0.000 (MRR .217) against
Gemini dense's 1.000 (MRR .778), so Azure's embedding space misses this area entirely at
top-3 instead of trailing proportionally. Fusion narrows or reverses the gap depending on
the metric: hybrid's recall@5 flips to Azure ahead (.814 vs .809, +.005) and hybrid's MRR
flips Azure ahead too (.824 vs .784, +.040); weighted's MRR also flips Azure ahead
(.833 vs .827, +.006), though weighted's recall@5 gap persists (.814 vs .882, -.068).
That last gap is not Azure's own fusion underperforming: within-provider, weighted lifts
Azure dense by +.074 recall@5 and Gemini dense by +.073, essentially the same absolute
gain. Gemini's weighted arm is simply the single best number in either table.

BM25's near-tie with dense reverses a v1 conclusion. v1 measured naive dense
comfortably ahead of BM25 on paraphrased claims. v2's FCA-sourced claims share verbatim
vocabulary with the guidance text itself ("guaranteed", "pre-approved",
"representative"), and BM25 comes within .02 of dense recall@5 overall (.789 vs .809
Gemini; .789 vs .740 Azure, where BM25 actually *beats* Azure dense outright). BM25 wins
`guaranteed-3.3` cleanly on both providers: recall@5 .682 vs dense .591 (Gemini), .682
vs .455 (Azure), a full reversal of which arm is stronger on that area rather than a
noise-sized wobble.

Weighted α=0.5 is the only arm beating dense on both gated metrics on both
providers: Gemini .882/.827 vs dense .809/.782; Azure .814/.833 vs dense .740/.674.
(Hybrid comes close but only ties Gemini's dense recall@5, .809 = .809, rather than
beating it.) What matters is what α=0.5 *isn't*. v1's weighted arm only won by
sweeping to α=0.9 on the same golden set that scored it, and was explicitly held back
from adoption for exactly that reason (see git history, commit `ec9c160`), because a
hyperparameter tuned on the only labelled data available is not evidence of a real win.
v2's α=0.5 is the pre-registered default, never swept or tuned on this or any golden
set, and it still clears dense on both metrics on both providers. That is a
categorically stronger claim to adoption than v1 had. It is still not adopted here,
held pending a holdout set, the same standard that held v1's α=0.9 back.

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

Confusion matrices are identical across providers: `{breach→breach: 25,
compliant→compliant: 5, compliant→needs_review: 1, needs_review→needs_review: 3}`. The
one miss both judges make is the same one, in the conservative direction (a compliant
claim routed to human review, never the reverse). Per-area accuracy matches exactly
too: apr-triggers-3.5 1.000, broker-3.7 0.667, guaranteed-3.3 1.000, hcstc-warning-3.4
1.000, prominence-review 1.000, rep-example-3.5 1.000.

A Google model and an OpenAI model landing on the same verdict for the same claim,
error included, is evidence that the v2 labels are model-robust: checkable by more than
one judge family instead of an artifact of one model's quirks. That is the exact
property v1's headline number lacked, since v1's accuracy measured agreement between
LLM-generated labels and an LLM judge, which is agreement with itself. v2's agreement is
between two independent judge families and FCA-anchored ground truth.

#### Full-corpus control arm — predictions, recorded before the run

CONC 3 is 86 chunks, about 21K tokens, so the whole corpus fits in a single judge prompt.
Retrieval has never been measured against simply putting all of it in the prompt, which
means the retrieval layer has never been shown to earn its keep at this scale.
`--mode judge-fullcorpus` is that control arm: identical to `--mode judge` in every
respect except which provisions reach `judge_prompt`.

Recorded 2026-08-12, before any full-corpus call was made. Scoring rule fixed at the same
time: a prediction misses if the measured value falls outside its stated band or
contradicts its stated direction, and bands are not widened after seeing the data.

| # | Prediction | Mechanism |
|---|---|---|
| 1 | Verdict accuracy ≤ 0.971, most likely 0.912–0.971 (31–33 of 34) | Almost nothing to win: dense already scores 33/34 and its single miss is conservative, so the upside is one claim. Against that, the class-A miss taxonomy says this judge is context-composition-sensitive, and 86 chunks maximises that. Asymmetric downside. |
| 2 | `ungrounded_rate` ≈ 0.00 in both arms — an uninformative check on this dataset | Only a fabricated rule id or an out-of-chapter citation (COBS, PRIN) registers, and every golden claim is CONC 3. Said in advance so a zero is not later presented as reassurance. |
| 3 | `citation_hit` ≥ 0.882 (the dense value) | The dense figure is retrieval-bounded by construction; with every provision in context that bound is gone. Direction up, magnitude modest, since v2 dense recall@5 (.740–.814) was not a tight bound. |
| 4 | `needs_review` recall flat at 1.000 (3/3), precision below 0.750 | Two mechanisms pull against each other — class A concerns context-*poor* fragments, and this arm is context-rich but diffuse — so the inflation should appear as false positives rather than missed reviews. With n=3 the recall cell quantises to thirds. |
| 5 | Cost ≈ $0.30 for the arm, ≈12× the dense arm's ≈$0.02; p95 latency 2–4× dense | Input goes from ~1.5K to ~21.5K tokens per call while output stays ~60; cost is input-dominated at $0.40/$1.60 per 1M. Latency is prefill-bound but sub-linear. |

### End-to-end

`python -m sentinel.eval_judge --mode e2e`, full graph (decompose → omission scan →
per-claim retrieve → judge → HITL gate) against all 26 golden examples, Azure only (see
the scope note below).

| metric | before (omission-blind decomposer) | after (+ omission scan) |
|---|---|---|
| overall_accuracy | 0.308 (8/26) | 0.500 (13/26) |
| mean_claim_delta | 3.00 | 3.69 |

Per-component judge accuracy is .971; the pre-scan end-to-end number was .308. That
0.663 gap was root-caused offline via a decompose-cache readback: 0 of 26
decompositions contained any omission-style claim, while 13 of the 17 gold `breach`
examples are omission breaches. The decomposer's prompt asks what the ad *says*; the
golden labels ask what it *fails to say*. No amount of judge or retrieval tuning fixes a
claim the decomposer never extracts in the first place.

The fix is one new graph node, `omission_scan`, wired between `decompose` and the
per-claim fan-out. Whole-promotion retrieval (the existing searcher, queried with the
full promotion text instead of a single claim) surfaces the provisions in play, the LLM
is asked which of those provisions' requirements are triggered by something in the text
but not satisfied by it, and the resulting omission claims are appended to the claim
list before the normal per-claim retrieve → judge → grounding-check → HITL-gate path
runs on every claim, stated or omitted. The scan itself emits no verdicts and cites no
rules: it is a claim generator, and the judge stays the single verdict authority.

Result: overall_accuracy 0.308 → 0.500, mean_claim_delta 3.00 → 3.69, meaning 5 more
examples scored correctly (+62% relative). The delta rose too, which is expected rather
than a regression. Gold examples average 1.3 claims (34/26) while the decomposer already
emits several stated claims per promotion, and a baseline delta of 3.00 with zero
omission claims is only possible if the pipeline over-counts gold on nearly every
example. Each appended omission claim, correct or not, moves the count further from
gold's.

Prediction, pre-registered before the run: overall accuracy ≈ 0.65 (17/26), claim
delta ≈ 3.8. Actual: 0.500 (13/26), delta 3.69. Accuracy missed high again, the second
pre-registered e2e-accuracy miss on this project's prediction scorecard, after the v2
re-baseline's 0.81 → 0.308. Delta landed close to predicted (3.69 vs 3.8).

Judge-mode invariance: re-running `--mode judge` gives accuracy 0.971 and
citation_hit 0.882, unchanged from the table above, cache-served, which confirms the scan
does not touch that path.

Scope of this number: it is Azure-only. The Gemini e2e control was not run
(judge quota). The root cause is argued from the decompose prompt and cache contents,
not from a paired Gemini e2e run. It reads as prompt-structural (the decomposer's
instructions, not the embedding or judge provider), but that inference is one un-run
experiment short of proof.

Remaining gap: per-example attribution of the remaining 13 misses is not yet possible
offline. The audit graph's default searcher has no embedding cache, so replaying a
specific example's retrieval to tell apart a retrieval miss from a prompt miss from a
judge miss needs live API calls, and that replay was attempted twice this phase and
blocked twice by transient network failures. Building that cache is the first item of
the tuning phase, alongside widening the scan's retrieval top-K and prompt variants.
Both are future experiments; no tuning happened in this phase, by user decision.

(Pre-scan run.) Demo smoke (`uv run python -m sentinel.audit "Get a loan in 5 minutes! No credit
check impact!"`, Azure end-to-end): PASS. The HITL gate interrupted on real input,
routing the claim to human review over `CONC 3.6.7G` instead of forcing a confident
breach/compliant call, the gate firing on genuine ambiguity rather than a canned example,
for the first time in a demo run.

Config note (2026-08-10). The table above was measured at `OMISSION_TOP_K = 5`, the
value in place through the tuning phase. The current default is K=12,
holdout-confirmed: two-dataset evidence (an eval-set sweep peak plus an independent,
pre-registered FG15-04 holdout direction) adjudicated the change, with the full sweep
table and adjudication in "Tuning: the scan depth sweep and its holdout verdict" below.
The 0.500 / 3.69 K=5 numbers above are the documented pre-adoption baseline and stay as
recorded now that the default has moved.

### Prediction scorecard

Predictions were pre-registered before any v2 run. Scored here, including row 7, which
would have been the easiest one to quietly drop:

| # | prediction | actual | verdict |
|---|---|---|---|
| 1 | Gemini dense recall@5 ≈ 0.65 | 0.809 | WRONG, low (off by .159) |
| 2 | Azure dense recall@5 ≈ 0.68, edges Gemini | 0.740, *trails* Gemini (.809) | WRONG on magnitude and direction |
| 3 | BM25 recall@5 ≈ 0.55, gap to dense narrows | 0.789 (near-tie with dense) | direction right, magnitude badly under (off by .239) |
| 4 | hybrid ≤ dense | Gemini: .809 = .809 (tie); Azure: .814 > .740 | MIXED |
| 5 | judge accuracy: Azure ≈ 0.88, Gemini ≈ 0.84 | both 0.971 | both UNDER (by .091, .131) |
| 6 | e2e ≈ 0.81 (21/26) | 0.308 (8/26) | badly WRONG (off by .502) |
| 7 | citation_hit ≈ dense recall@5 (retrieval ceiling reasserts itself) | citation_hit .882 both providers; dense recall@5 .809 (Gemini) / .740 (Azure), so citation_hit didn't move with the metric it was predicted to track | WRONG on mechanism |

Row 7's reading: citation_hit only needs the cited rule *anywhere* in the top-5, which
is what hit@5 measures (.882 both providers, matching citation_hit exactly), rather than
full recall@5 of every cited rule. The predicted "ceiling" metric was misidentified;
hit@5, not recall@5, is what bounds it.

Not one prediction landed. Rows 1 to 3 and 5 missed low, row 4 split, row 6 missed high
by .502, row 7 misidentified the bounding metric, and row 2 also missed on direction.
Pre-registering predictions is not meant to make them right. It fixes the story in place
before the numbers arrive.

### Statistical power

n=34 claims. Treat differences under ~.08 recall@5 as noise; several of the "wins"
described above (hybrid vs dense, weighted vs hybrid within a provider) sit inside or
near that band and are described accordingly, not as adoption cases. No retrieval arm
measured in this document is being adopted on this evidence alone. That decision was
explicitly deferred to a holdout set, and the holdout has since ruled: weighted fusion
stays held (the holdout was underpowered to adjudicate it), and the scan retrieval depth
swept below is the one number this phase's holdout did move. The residency comparison
(Gemini vs Azure at dense) used the Gemini incumbent as the baseline, not an
unconstrained frontier embedder; whether Azure's residency cost looks different against
the current best embedding model on the market is open and unmeasured.

## Tuning: the scan depth sweep and its holdout verdict

The omission scan (see "End-to-end" above) reaches into the corpus with the full
promotion text at a configurable depth, `OMISSION_TOP_K`. The tuning phase swept that
depth against the golden set, and the FG15-04 holdout then adjudicated the winner, the
two-step process the pre-registered adoption rules required.

### The eval-set sweep (diagnostics, not adoption evidence on their own)

`python -m sentinel.eval_judge --mode e2e` at four depths, golden set (26 examples),
Azure:

| K | overall_accuracy | mean_claim_delta |
|---|---|---|
| 5 | 0.500 | 3.69 |
| 8 | 0.577 | 3.96 |
| 12 | 0.654 | 4.38 |
| 20 | 0.615 | 6.04 |

K=12 peaks; K=20 over-generates (delta jumps to 6.04 for lower accuracy than K=12).
This table is an eval-set diagnostic, not adoption evidence by itself, since every
number here is measured on the same set that would be scoring the decision, the exact
failure mode v1's weighted-retrieval sweep fell into (see "Retrieval" above). Adoption
is decided below, against the holdout.

### Miss taxonomy behind the sweep

Root-causing the K=5 baseline's 13 misses (of 26 golden examples) found four classes.
Counts: 10 (class A) + 1 (class C) + 2 (class D) = 13; class B is a retrieval-mechanism
explanation nested inside class A's misses, not a separately-counted class. Only class
B, and therefore only part of class A, is something the K sweep can act on:

- A. Judge `needs_review` inflation on context-poor fragments, 10 of 13 misses.
  The 0.971-accurate judge (see "Judge accuracy" above) turns cautious when a claim is
  a bare fragment ("£189 per month", an address, even "Representative 24.9% APR
  (variable)") stripped of the omission framing that would make its significance
  legible. This is the dominant miss class, and it is a judge/decomposer-context
  problem, not a retrieval-depth problem. Out of this phase's scope, recorded as the
  next lever after multimodal.
- B. Scan under-emission, retrieval-bound. Overlaps class A and is not separately
  counted. For several of class A's misses (apr-triggers / rep-example / broker
  areas), the scan emitted no omission claim at all, consistent with whole-promotion
  K=5 retrieval missing the triggering provision. This is exactly what the K sweep
  tests, and the sweep's own accuracy climb (0.500 → 0.654 through K=12) confirms the
  hypothesis directly. It is the one mechanism the K sweep can act on.
- C. Scan false positive on an exclusion, 1 of 13 misses (gold-110). The scan
  flagged a missing HCSTC risk warning where the promotion is actually excluded from
  that requirement under CONC 3.1.7R; the judge-rescue guard, whose job is to catch a
  scan claim contradicted by what it retrieves, failed to catch this one. Status: out
  of reach of both the K sweep (more retrieval depth doesn't teach the scan to
  recognise an exclusion it already retrieved and ignored) and the multimodal layer
  (nothing about this miss is image-related). At n=1, any fix targeted at this single
  example would be overfitting the eval set rather than a generalizable improvement,
  so it is recorded as an open exclusion-awareness item for the scan prompt, to
  revisit once a future dataset expansion gives it more than one example to fix
  against.
- D. Two prominence golds, structurally unreachable in a text-only pipeline, 2 of 13
  misses. Two golden examples (`needs_review`, on font-size/contrast prominence
  questions) cannot be scored correctly by any retrieval depth or judge tuning, because
  the prominence fact they turn on was never in the text at all. It lives in the
  image. This is exactly the gap the multimodal layer, and the FG15-04 holdout built on
  it, exists to address.

### Adjudication protocol

Two adoption rules were pre-registered before any holdout number existed: weighted
retrieval (α=0.5) becomes the default iff it beats dense on both recall@5 and MRR on
the holdout; `OMISSION_TOP_K` moves to 12 iff holdout e2e accuracy at K=12 is at least
K=5's. Before the holdout was run, an adversarial review of the built dataset found the
retrieval half would rest on far fewer corpus-mappable claims than planned (see "The
FG15-04 holdout" above), and the protocol was amended accordingly, ratified by the
dataset owner before any holdout number existed:

> rule (a) weighted adoption = HELD-for-insufficient-power regardless of numbers
> (effectively n=1 promotion); rule (b) K comparison = directional smoke only (1
> example ≈ 11pp; mostly measures judge robustness to irrelevant context)

### Holdout outcomes

Retrieval smoke (n=3, all from one promotion, see the power-limits note above):
dense recall@5 0.833 / MRR 0.528 vs weighted recall@5 0.833 / MRR 0.611. Recall@5 ties
exactly; the MRR gap is noise at this size. Per the amended protocol, weighted fusion
stays held regardless of this outcome, because the holdout was never powered to
adjudicate it, tie or no tie.

End-to-end (n=9, corpus-mappable and out-of-corpus claims both included, per the
harness's existing skip path): K=5 overall accuracy 0.444 / mean_claim_delta 3.33,
vs K=12 0.556 / 5.11. K=12 beats K=5, so the directional check passes, by exactly one
example out of nine.

### Adoption: `OMISSION_TOP_K = 12`

`OMISSION_TOP_K` moves from 5 to 12 (commit `a5404d9`), on two-dataset evidence: the
eval-set sweep's own peak (0.654 at K=12, the best of four depths) plus this
independent, pre-registered holdout direction (K=12 > K=5). The margin caveat, which is
the whole basis for calling this evidence and not proof: the holdout margin is one
example, the disclosed noise quantum. Weighted retrieval (α=0.5) is not adopted
alongside it; rule (a) held it back regardless of the tied outcome above.

### Prediction scorecard (holdout runs)

Predictions were pre-registered before any holdout run, under the amended protocol:
both e2e arms in the 0.33 to 0.55 band (most holdout claims cite out-of-corpus rules, so
retrieved CONC chunks are structured noise for them, which measures judge robustness to
irrelevant context more than retrieval); K=12 ≥ K=5 by 0 to 1 examples; the retrieval
comparison an uninformative tie; and that the judge routes several out-of-domain claims
to `needs_review`, with the grounding check also firing where a claim cites a rule that
wasn't retrieved.

| # | prediction | actual | verdict |
|---|---|---|---|
| 1 | K=5 e2e accuracy in-band (0.33 to 0.55) | 0.444 | HIT |
| 2 | K=12 e2e accuracy in-band (0.33 to 0.55) | 0.556 | miss, marginal, ~0.006 above the top of the band |
| 3 | K=12 ≥ K=5 by 0 to 1 examples (direction + margin) | K=12 beats K=5 by exactly 1 example (5/9 vs 4/9) | HIT |
| 4 | retrieval comparison an uninformative tie | recall@5 tied exactly (0.833 = 0.833); MRR gap is noise at n=3 | HIT |
| 5 | judge routes several out-of-domain claims to `needs_review`; grounding check also fires on uncited-rule citations | not recorded, no per-claim holdout outputs on disk | NOT SCORED |

Row 5 is neither a hit nor a miss; it is undecidable from what exists. The
adjudication driver logged only aggregate `overall_accuracy` and `mean_claim_delta` per
K, not per-claim judge verdicts or grounding-check outcomes, so there is no artifact to
check this prediction against. It stays on the scorecard because the prediction was
made and the evidence to score it does not exist.

Three of the four scored rows land outright. The fourth, K=12's accuracy, missed the
band by about half a percentage point on the high side, the same direction the
eval-set sweep already pointed. This is the first prediction set on this project whose
scored rows come out substantially correct: every prior scorecard here (the v2
retrieval predictions above, the v2 e2e prediction, the omission-scan e2e prediction)
missed by far wider margins, several by double-digit percentage points.

### Operational notes

Azure's Prompt Shields false-positived on the app's own injection-defense wording: the
`UNTRUSTED_INTRO` fencing used to defend against prompt injection reads to the content
filter *as* an injection attempt, and it blocked 100% of judge calls with HTTP 400. The
fix was a scoped content filter policy on the judge deployment (jailbreak shield set to
annotate-only, harm-category filters untouched). Rewording the prompt would have traded
away the hardening just to dodge a false positive. Parallel e2e fan-out separately
needed judge capacity raised to 50K TPM. The `ragas` arm remains Gemini-backed by
design, a demoted and optional metric group, not re-baselined on Azure this round,
because the Phase 3 analysis found off-the-shelf faithfulness mis-measures this task
shape (rationales must reference the claim under assessment, which is never present in
the retrieved contexts).
