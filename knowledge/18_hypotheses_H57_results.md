# 18 — What H57 actually found (session 2026-10-07)

Preregistered in [`17_hypotheses_H57_preregistered.md`](17_hypotheses_H57_preregistered.md) and
frozen in [`registry/h57_preregistration.json`](../registry/h57_preregistration.json) before any
H57 code ran. This file records the results, including the four that failed. Receipts:

| receipt | what it holds |
| --- | --- |
| `evidence/h57_cotrain.json` | block-buffered out-of-fold fit, independence test, agreement strata, pseudo-label exchange, matched-budget arms |
| `evidence/h57_validation.json` | placement and ranking holdouts, eight fields, two instruments, two budgets |
| `evidence/h57_strata.json` | which agreement stratum should carry the arm |
| `evidence/h57_build.json` | the artefact, the format gate, uniqueness, set relations, per-pixel dossier pointer |
| `evidence/h57_slot_gate.json` | the registered R1 verdict, the refutations, the conditional projection |

---

## 1. The instrument had to be fixed before any hypothesis could be tested

Three defects were found and fixed while building it, and all three produced confident wrong
answers before they were caught. They are recorded because the same traps are still open in the
rest of the repository.

1. **`Layers.matrix` axis order.** The feature stack is stored layer-major, `(n_layers, rows, cols)`.
   The first version reshaped the raw block, silently producing a `(layers*rows, cols)` matrix.
   scikit-learn did not error — it accepted the matrix and complained that it had 3,292 features
   instead of 39. Fixed to fold rows/cols only *after* the layer axis is moved last, with a new test
   (`tests/test_h57.py::test_layers_matrix_is_pixel_major`) that pins the convention.
2. **Single-class folds.** `make_folds` computed its buffer mask from the *component* fold id, which
   is `-1` on every non-catalogue pixel, so the 9x9 disagreement test fired around every catalogue
   pixel and marked the whole grid as boundary. `cat & fit` was **0 pixels in all four folds** and
   the classifier learned one class. Replaced with `segment_buffer(held, buffer_px)`; the folds now
   carry 31,556 / 48,325 / 51,270 / 51,465 catalogue pixels into training.
3. **A masked-out arm scored exactly 0.0000 on every fold.** `legal` was built as
   `region & ~corridor & visible`, where `visible` is the *catalogue* mask, not the grid. Every arm
   was restricted to still-mapped faults and then `mask_visible` deleted them. Fixed to
   `region & ~corridor`; the arm arms then scored 0.0038–0.0064 instead of 0.

## 2. The conditional-independence premise — first non-degenerate measurement

The Blum–Mitchell semi-supervision theorem assumes the two views' labelling functions are
conditionally independent given a small shared label set. `knowledge/03` N-1 could not estimate the
premise and failed closed, so the exchange never ran there. H57 finally measures it, per 50x50
block, on out-of-fold predictions over the 4.5 M labelled-negative pixels, with whole-component
folds and a 4 px buffer:

| statistic | n | Pearson | Spearman |
| --- | --- | --- | --- |
| block-level negative MSE | 2,200 blocks | 0.0530 | 0.0579 |
| block-level false-positive rate | 2,200 blocks | 0.0395 | 0.1108 |
| pixel-level out-of-fold logit | 4,519,160 px | 0.0555 | 0.0354 |

`max |r| = 0.1108` against the registered abandonment threshold `|r| >= 0.60`. **The premise is not
refuted at this granularity.** That is a statement about weak coupling, not about independence, and
it is the first time this repository has been able to say either.

## 3. Pseudo-label exchange — ran, and did nothing

With exchange permitted, 1,996 pseudo-labelled pixels in 102 whole 8-connected segments were handed
from a confident View-B donor to an abstaining View-A receiver in fold 0's unlabelled quadrant,
never on a catalogue or corridor pixel. View-A out-of-fold AUC on 908,665 unseen pixels:

**0.4842 → 0.4869, delta +0.0027.**

Indistinguishable from noise, and an exact reproduction of `knowledge/03` N-1 (−0.0159 tip,
−0.0303 hide, 0/4 folds). Disagreement is therefore used to *label* the arm, never to train it.

## 4. The agreement strata — the premise is right, the bet is wrong

The brief's geological claim is **confirmed**: the A-only stratum really is the deep-cover stratum.

| stratum | pixels | median depth to basement |
| --- | --- | --- |
| A confident, B abstains | 179,254 | **410.9 m** |
| B confident, A abstains | 201,837 | 161.2 m |
| both confident | 46,293 | 208.0 m |
| neither | 4,434,118 | — |
| permitted set | 4,861,502 | 316.0 m |

The bet that follows from it is **refuted**. Eight arms, one protocol (candidates may not sit on
the *visible* catalogue dilated by 2 px; the *held-out* catalogue is scored as truth), 15,000 nodes,
isotropic emitter, eight fold-cells across both instruments:

| arm | fold-mean DTI | vs random |
| --- | --- | --- |
| `union` (max p_A, p_B) | **0.004875** | **4.61x** |
| `view_B` | 0.004873 | 4.61x |
| `S_neither` (sub-threshold shoulder) | 0.004081 | 3.86x |
| `view_A` | 0.003850 | 3.64x |
| `S_b_only` | 0.002889 | 2.73x |
| random control | 0.001057 | 1.00x |
| `S_concordant` | 0.000852 | 0.81x |
| **`S_a_only`** | **0.000785** | **0.74x** |

The A-only stratum is the **worst of the eight** and below the matched random control. It is kept in
the artefact as a labelled component — 846 of the 14,804 arm cells — with its own geological
reasoning rows, but it is not the population.

## 5. The anisotropic placement — the metric algebra is right, the gain is not there

The kernel algebra is exact and is pinned by test: on an isolated 1-px trace with
`k(0)=1, k(1)=2/3, k(2)=1/3, k(3)=0`, the credited truth inside one node interval `[0, s)` is
**7/3 = 2.3333 at s = 3, 8/3 = 2.6667 at s = 4, 3.0 at s = 5** — so 5 px carries **+28.6 %** over
the 3 px every emitter in this repository uses. Six px leaves truth pixels with `k = 0`.

On the spatial holdout that advantage does not survive. Same field, same pool, same budget; only the
emitter differs:

| cell | isotropic 3 px | anisotropic 5x3 | lift | relative | folds won | gate |
| --- | --- | --- | --- | --- | --- | --- |
| tip @ 15,000 | 0.001812 | 0.001812 | +0.000000 | +0.00 % | 0/4 | FAIL |
| tip @ 37,654 | 0.004864 | 0.004919 | +0.000055 | +1.12 % | 2/4 | FAIL |
| hide @ 15,000 | 0.001708 | 0.001708 | +0.000000 | +0.00 % | 0/4 | FAIL |
| hide @ 37,654 | 0.005849 | 0.005880 | +0.000031 | +0.54 % | 2/4 | FAIL |

Mapped traces are wider than 1 px, and adjacent nodes along a gently curving strike overlap anyway,
so the "isolated 1-px trace" premise does not describe the data. The artefact ships the **isotropic
3-px emitter**. This is recorded as a refutation of H57-A, not a tuning result.

## 6. What did work: the union ranking field

Eight fields under the identical pool, budget and emitter. Fold-mean DTI against the matched random
control, `evidence/h57_validation.json -> ranking`:

| cell | 1st | 2nd | 3rd |
| --- | --- | --- | --- |
| tip @ 15,000 | `clf_union` 0.004707 (+0.003683) | `clf_view_B` 0.004635 | `clf_view_A` 0.003791 |
| tip @ 37,654 | `clf_union` 0.005444 (+0.003899) | `clf_view_B` 0.005221 | `ridge_A_grav_slope` 0.004919 |
| hide @ 15,000 | `clf_view_B` 0.005110 (+0.004056) | `clf_union` 0.005044 | `clf_view_A` 0.003909 |
| hide @ 37,654 | `clf_union` 0.006445 (+0.004843) | `clf_view_B` 0.006410 | `ridge_A_grav_slope` 0.005880 |

`clf_union` wins **16/16** fold cells against the random control and is rank 1 of 8 on three of the
four cells (rank 2 on the fourth by 0.00007). Catalogue-independent ridge fields built from the
structure tensor of five gradient channels rank 3–8; they are real but weaker than the classifiers.

## 7. The thing that cannot be measured, stated as a limitation not a result

A **required-novel** arm cannot be scored by this simulator at all. During validation, the View A
field was scored with the catalogue halo excluded from the candidate pool:

| emission | DTI |
| --- | --- |
| View A top-of-field, catalogue halo allowed | 0.004037 |
| View A top-of-field, catalogue halo excluded | **0.000358** |
| matched random control | **0.001713** |

Excluding the catalogue removes every pixel the truth can occupy; what is left is worse than random
because the classifier's second-tier local maxima sit on its own artefacts. So `rho_novel`, the
arm's credit density against faults nobody has mapped, is a **prior and not a measurement**, and no
number in this repository can certify it. That is why the projection prints a whole curve.

## 8. The decision

| | |
| --- | --- |
| R4 format gate | **PASS** — single band float32, EPSG:32611, 3,730 x 3,292, exact transform, 0 NaN, 0 infinities, no nodata tag, values exactly `{0,1}` |
| R5 decoded-pattern uniqueness vs 38 accessible aligned priors | **PASS** |
| R5 support novelty | **PASS** — 100 % of the arm lies outside the accessible prior-support union |
| R6 not the union of the named priors | **PASS** |
| R3 nothing inside the 200 m ring | **PASS** — closest emitted cell 223.6 m |
| R2 independence measured and non-degenerate | **PASS** |
| R7 per-candidate geological reasoning | **PASS** — 14,804 rows, none empty |
| **R1 mean lift >= +0.005 on both instruments** | **FAIL** — +0.0037 to +0.0048 |
| R1 >= 3/4 folds positive on both instruments | **PASS** — 4/4 |

**Verdict: SUPPORTED BUT BELOW THE REGISTERED LIFT THRESHOLD.** The threshold is applied as it was
written and reported as not met. The artefact is published and fully gated; the upload decision is
left to the owner with its arithmetic attached:

- P(this file scores **below** the owner's own 0.2778) = **0.83**
- P(above 0.3195) = **0.36**
- P(above the observed board top 0.3774) = **0.00**

The conditional argument for the arm, stated as a conditional and not as a claim: added mass raises
DTI only while its credit density exceeds `alpha * DTI = 0.062`. The union field measures
4.61x the 0.028 random baseline on held-out catalogue, i.e. **rho = 0.129**, well above break-even.
The arm sits at least 3 px further from any mapped trace than the rows that measurement was taken
on, so **0.129 is an upper bound** on the arm's own density, and the bound is the whole argument.

## 9. What was not done, and why

- **H57-C antisymmetric edge coincidence** and **H57-D conductivity–depth paired contrast** were
  registered as queued and never run. They are not needed for this artefact and are left for a
  round that has a comparable holdout to test them against.
- **The learner's A-only geological reasoning is per *emitted arm pixel*, not per pixel of the
  A-only stratum.** All 179,254 A-only pixels were screened; 846 were emitted. Reasoning exists for
  those 846 and for the other 13,958, each with its own stratum label, physical signature and an
  explicit falsifier.
- **No leaderboard score is claimed, forecast or implied.** Spearman(reported score, simulated DTI)
  is −0.1045 (p = 0.734, n = 13) in `knowledge/10` §5.