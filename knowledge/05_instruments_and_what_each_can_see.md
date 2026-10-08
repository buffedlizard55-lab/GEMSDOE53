> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# 05 · The two instruments, and what each one can actually see

This repo does not have one holdout, it has two, and the disagreement between them is the most
informative result in the whole file. If you read only one knowledge note before changing a selection
rule, read this one.

## 1. What each instrument is

Both run on the same spatial blocks (`BLOCK_M` grid, whole connected components, no component split across
folds, a buffer strip removed around every hold-out block so a model cannot score by bleeding across the
edge). They differ in *how* a component is held out.

| | `mode="hide"` | `mode="tip"` |
|---|---|---|
| operation | whole fault components are removed from the training labels and scored as-is | each visible trace is **truncated**, and the missing stub is the truth |
| truth a fold can credit | a complete, never-seen fault anywhere in the block | a short continuation *adjacent to a known trace* |
| what it is blind to | nothing near a visible trace: only **0.5 %** of held-out truth lies within 5 px of one | isolated faults: an un-mapped fault that touches nothing scores 0 here by construction |
| prevalence | data-determined by the block, so absolute DTI transfers badly | 4–8 k px per fold, so only *ranking* transfers |
| corresponds to which real failure | "we find structures the catalogue has never heard of" | "we extend structures the catalogue started but did not finish" |
| metric-relevant fact | the organiser's mask is pixel-exact and *only new-fault truth counts*, so near-trace mass is credited **only** where there is new truth within 300 m of it | the same statement also says new truth *may* sit within 300 m of a known trace, and that finding those corrections is a goal |

Empirical anchor for the tip instrument: after building the truncated labels, **88.5 %** of tip-fold truth
pixels lie within 5 px of a visible trace. New fault *starts* cluster at the ends of old ones. That single
number is why the corridor regime exists at all.

## 2. Every arm, both instruments, at matched budget and matched mask

Mean DTI over 4 folds. `random|K` is the control run with the *same* budget in the *same* permitted set, so
"beats random" is the only comparison that isolates placement from mass.

| arm \| budget | tip | hide | min |
|---|---|---|---|
| `B_only|25000` | 0.0296 | 0.0497 | **0.0296** |
| `B_only|37654` | 0.0291 | 0.0518 | 0.0291 |
| `B_only|15000` | 0.0284 | 0.0435 | 0.0284 |
| `random|37654` | 0.0253 | 0.0396 | 0.0253 |
| `B_only|8000` | 0.0255 | 0.0364 | 0.0255 |
| `union_sup|37654` | 0.0245 | 0.0379 | 0.0240 |
| `union|37654` | 0.0240 | 0.0381 | 0.0240 |
| `random|25000` | 0.0216 | 0.0316 | 0.0216 |
| `cotrain|37654` | 0.0084 | 0.0078 | 0.0078 |
| `A_only_cor|37654` | 0.0160 | 0.0001 | 0.0001 |
| `corridor_blanket|37654` | 0.0154 | 0.0006 | 0.0006 |
| `union_cor|37654` | **0.0320** | 0.0001 | 0.0001 |

Per-fold detail for the two single-view leaders:

* tip, `union_cor|37654`: 0.0267 / 0.0475 / 0.0393 / 0.0147 (mean 0.0320, s.d. 0.0125) — **4/4 folds**
  above `random|37654` at the identical budget (+27 %), and the corridor restriction alone is worth
  +33 % over the unrestricted `union`.
* hide, `B_only|37654`: 0.0426 / 0.0328 / 0.0602 / 0.0715 (mean 0.0518, s.d. 0.0150) — +31 % over random
  but only **2/4** fold wins, which is why it is not simply declared better.

Two facts follow immediately. `B_only` is the only arm that beats its control on **both** instruments. And
`union_cor` — the arm that is best where the truth is densest — is *structurally* dead on hide (0.0001),
so any rule that ranks arms by their worst instrument picks `B_only` and throws the corridor away.

## 3. The selection rule we use instead of max-min

`scripts/composite_split.py` does not ask "which arm is least bad". It builds a **two-regime** emitter, in
which the two instruments each get to choose the ranking over the population they are able to judge:

```
permitted = valid & ~catalogue
corridor  = dilate(catalogue, 6 px) & ~catalogue & valid     # 1–6 px off a known trace
far       = permitted & ~corridor                             # never-mapped structures

emit = top-k(corridor, K·s, ranked by  R_cor)  ∪  top-k(far, K·(1−s), ranked by R_far)
```

and it sweeps `R_far ∈ {B_only, union, wt_A20B80, random}`, `R_cor ∈ {union_cor, corridor_blanket, …}`,
split `s ∈ {0, 0.25, 0.5, 0.75, 1.0}` and budget `K ∈ {25000, 37654}` on both instruments, then chooses by
three rules in this order:

1. **both instruments must beat their `random` control at the same budget and mask** — a config that only
   wins on one instrument is not selected, because we cannot tell "wins where it is able to win" from
   "wins";
2. subject to (1), maximise `mean_tip + mean_hide` — the sum, because the two regimes are *disjoint
   populations* whose DTI contributions add in the real metric (the tax on far-field false positives is the
   same linear term either way);
3. ties go to the smaller total mass, since mass is the only part of a submission we can regress and
   the metric's `α = 0.2` penalty on far-field FPw is what makes a smaller file strictly safer at equal
   ranking.

`K = 37654` is not a guess: it is the exact footprint mass the 0.2778 file used, i.e. 2.5–3.6× a fold's
held-out truth, and the metric analysis in `knowledge/01` says an all-or-nothing emission at that scale is
where the credit/penalty trade-off is closest to the accept-bar (`gain > α·DTI/(1−α·DTI)`, which across
DTI 0.28–0.46 accepts exactly the pixels within ~2.24 px of a probable uncatalogued fault pixel — no
score-dependent knob exists to tune).

## 4. What a reader should be suspicious of

* Fold-to-fold spread is the same order as the effect (s.d. ≈ 0.0125 on tip). A 2/4 fold win is *not* a
  result, which is why the gate asks for 3/4.
* Both instruments train on the *same* features as the deployed models; the composite therefore measures
  "which ranking places mass better", not "does the model overfit". The `SIBLINGS` cross-check in
  `scripts/validate_holdout.py` and the sha256 pins in `scripts/prepare_data.py` are the anti-corruption
  layer, not the folds.
* The absolute DTI here (0.03–0.05) is not a forecast of the score (0.2778 on the board). The instruments
  use a fraction of the truth population, at a prevalence that is far above the real one. Only *differences
  at matched budget* mean anything.

## 3b. What the sweep said (22:16 UTC, 60 configurations × 4 folds × 2 instruments)

Ranked by `sum`, after the "must beat the matched control on both instruments" filter:

| configuration | tip | hide | sum | corridor share |
|---|---|---|---|---|
| `B_only+blanket|37654|s0` **(selected, shipped)** | 0.0291 | 0.0518 | **0.0809** | 0.00 |
| `B_only+blanket|25000|s0` | 0.0296 | 0.0497 | 0.0793 | 0.00 |
| `B_only+union_cor|37654|s0.25` | 0.0304 | 0.0479 | 0.0783 | 0.25 |
| `B_only+union_cor|25000|s0.25` | 0.0300 | 0.0445 | 0.0744 | 0.25 |
| `B_only+blanket|37654|s0.5` | 0.0273 | 0.0345 | 0.0618 | 0.50 |
| `random+blanket|37654|s0` (the control) | 0.0250 | 0.0392 | 0.0642 | 0.00 |

Four things to take from it, in order of how much they cost to learn:

1. **Funding the corridor costs more than it pays at this budget.** Moving 25 % of the mass into the
   corridor gains +4.5 % on the instrument that can see corridor truth and loses 7.5 % on the one that
   cannot; at 50 % it loses on both. The sum rule therefore selects share 0.0 — the corridor regime is
   real, measured, and *unfunded*. That is a placement-economics statement, not a geological one: the
   corridor's truth is worth less per pixel than the far-field's, because half of it displaces mass that
   would otherwise sit on whole unmapped components.
2. **The control definition is the whole experiment.** The first version took `max` over every
   configuration whose name contained "random" — which on the truncation instrument returned 0.0320, the
   corridor arm's *own* score, because `random+union_cor|s1` is "random far, corridor-ranked near" and the
   corridor won there. The shipped arm was then reported as losing to chance (0.0291 < 0.0320) when the
   fair control is 0.0250. Fixed control → `beats_random_all: true`, and the fix is recorded in the JSON as
   `previous_selection`, not quietly overwritten (`scripts/composite_recount.py` re-derives the table from
   the stored per-fold numbers, so a rule change costs seconds and cannot be accused of re-tuning the models).
3. **`promoted` is still false.** Clearing the composite control bar on both instruments is not the same as
   clearing the pre-registered bar: +0.0051 over the naive union on tip against the required +0.010. The
   build records both flags separately (`composite_control_bar: true`, `registered_union_bar: false`) so the
   distinction survives into the evidence file next to the sha256.
4. **Ties are informative:** at share 0.0 the corridor ranker is irrelevant (zero pixels allocated), which is
   why `+blanket` and `+union_cor` produce byte-identical emissions. If they had not, the split logic would be
   broken.

Reproduce:

```bash
PYTHONPATH=src python3 scripts/validate_holdout.py --modes tip,hide   # arm tables + gates
PYTHONPATH=src python3 scripts/composite_split.py \
    --modes tip,hide --total 25000,37654 --splits 0.0,0.25,0.5,0.75,1.0 \
    --far B_only,union,random --cor union_cor,blanket                 # evidence/composite.json
```
