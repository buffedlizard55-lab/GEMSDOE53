# Round 4 — rebuild after the reset, and what it measured

**Status:** measured. Every number below comes from a receipt in `evidence/`, written by
`scripts/run_r4.py`. Where a number differs from the pre-reset session, both are shown and
the difference is explained rather than smoothed over.

---

## 0. The reset (IR-R4-001)

At roughly 13:06–13:07 on 2026-10-08 the sandbox was reset to git HEAD. Everything
uncommitted and everything ignored was destroyed:

| Lost | Consequence |
|---|---|
| `src/gems52_r4/` (7 modules) | the whole round's implementation |
| `tests/test_r4.py` | 58 tests |
| `scripts/run_r4.py` + 5 publishers | the driver |
| `work/` — 74-layer stack (3.6 GB), OOF fields, pseudo-truth | every intermediate |
| `data/external/` — 24 restored layers | all externals |
| `/home/user/.venv` | the environment |
| `evidence/r4_*.json` | every receipt |

Root cause, stated plainly: `.gitignore` lists `/data/` and `/work/`, so no artifact
outside git was ever protected, **and the round's code had never been committed**. There
was no stash, no dangling object, and none of the 21 prior `arena/*` remote branches
contained it — I fetched and grepped all of them.

What survived made the rebuild possible: `scripts/restore_data.py` and
`registry/data_manifest.json` were committed, so all 23 data files came back SHA-verified
in one run. That is the entire argument for committing code before results.

**The rebuild commits after every stage.** This file is written while the arms stage is
still running, so that a second reset cannot take the conclusions and the implementation
together.

---

## 1. What was rebuilt

`src/gems52_r4/` — `layers`, `model`, `cotraining`, `instrument`, `arms`, `bias`,
`reasoning`, plus `scripts/run_r4.py` and 38 regression tests.

The layer plan is **74 layers: 30 View A / 44 View B**, asserted at import time so a
future edit that drops a layer fails loudly. Two principled exclusions: LiDAR bands 9–12
carry no description in the source file, and two near-duplicate smooth-scale layers
(`B_rad_K_grad`, `B_elev_regional`) were dropped to hold the 30/44 split.

Band 6 of `training_features.tif` stays in **View B**. The organiser's tag calls it a
magnetic tilt derivative; measured on the bytes it is radiometric total count
(IR-52-019, IR-52-034). A radiometric band inside the potential-field view would corrupt
the independence test the two views have to pass.

### New irregularity

**IR-R4-002** — band 10 (`dist_to_eq`) reaches **4,962,515 m** inside the footprint. The
grid is 3730 × 3292 px at 100 m, so its diagonal is about 492 km; **0.41% of footprint
pixels (21,326 of 5,165,840) report a distance larger than 329 km**, which is impossible
for a distance-to-nearest-earthquake measured on this grid. Median is 622.8 m and p99 is
50.2 km, so the distribution is otherwise plausible. Layers derived from band 10 are
rank-encoded before any learner sees them, which compresses the tail — but any future use
of band 10 as a *metres-valued* quantity (a buffer, a threshold, a decay length) would
silently mishandle those pixels.

---

## 2. Model results — `evidence/r4_model.json`

300,000 training rows (60,000 positives, 240,000 negatives) over a 5,165,840-px
footprint, 162 blocks of 20 km, 5-fold blocked CV.

| View | Layers | Blocked OOF AUC | Median block AUC | Blocks scored |
|---|---|---|---|---|
| A — potential field / subsurface | 30 | **0.6005** | 0.5946 | 152 |
| B — surface / radiometric | 44 | **0.7779** | 0.7999 | 152 |

View B is clearly the stronger view on this layer plan. That ordering matches the
pre-reset session (A 0.6229, B 0.7175) and is consistent with the parallel H59 round's
finding that a view-B field beats the incumbent.

### Independence: the test FIRES

**max \|ρ\| = 0.7051** across 150 blocks, against a declared threshold of 0.60.
**The two views are not conditionally independent.**

This contradicts the value recorded before the reset (0.4476, which did not fire). The
two runs are not comparable byte-for-byte and I am not going to pretend they are: the
layer plan was rebuilt from the design rather than restored, the block count differs
(162 here vs 142), and the sklearn version differs. Both numbers are reported. Neither is
presented as a re-measurement of the other.

The consequence is the same either way and is the part that matters: **co-training rests
on the views being conditionally independent, and on this measurement they are not**, so
pseudo-labels exchanged between the views are not independent evidence.

---

## 3. The instrument cannot promote — `evidence/r4_instrument.json`

Dispersed pseudo-truth, \|G\*\| density-matched to exactly 13,500 px (3,198 catalogue
components, 1,439 hidden and displaced, 1,759 kept):

| Candidate | Budget | DTI vs G\* |
|---|---|---|
| `h33-2-b2` (champion, board 0.2778) | 37,654 | **0.021529** |
| uniform random | 20,000 | **0.031296** |
| uniform random | 37,654 | **0.047374** |
| uniform random | 70,000 | **0.060798** |

**Uniform random beats the champion at the same budget, and beats it again at roughly
half the budget.** This is an independent reproduction — from committed code, a rebuilt
layer plan and a fresh environment — of the finding filed as
[issue #31](https://github.com/buffedlizard55-lab/GEMSDOE52/issues/31).

The verdict is unambiguous and it is the round's most important result: **the local
pseudo-truth assay measures emission size, not geology, and cannot be used to promote a
candidate.** DTI grows with budget almost mechanically (sparse emissions give
`DTI ≈ ρS / (0.2S + 0.8G)`), so a bigger random field scores better than a smaller
well-aimed one.

*Caveat I am not hiding:* the `board` column for the random rows is a placeholder zero —
those rasters were never scored on the leaderboard — so `spearman_board_vs_neg_budget` in
that receipt is 0.0 and means nothing. The verdict above does not use the board column.

---

## 4. What this means for selection

With the instrument disqualified, promotion falls back to **matched-budget
hide-and-recover**: hold out whole catalogue segments, remove them and a buffer from
training, keep them inside the emission mask, and measure what fraction of the held-out
truth is recovered at a fixed budget. Budget is held constant by construction, so the
budget confound cannot enter.

Two design details that the tests now lock down, both of which silently produced garbage
before:

- The held-out segment is removed from the catalogue used to build the 200 m emission
  exclusion. Leaving it in makes the held-out truth unplaceable — measured survival was
  **0.000**. The stage now raises below 0.9. Current run: survival **1.0000** on fold 0.
- The training-exclusion mask and the emission-allowed mask are separate objects.
  Conflating them is the bug above.

### Results — `evidence/r4_arms.json`

Four whole-segment folds. **Truth survival 1.0000 on every fold** (15,224 / 15,224 /
15,223 / 15,223 held-out pixels, ~4.99 M allowed pixels each). Budget held constant by
construction, so the confound that disqualified the instrument cannot enter.

| Arm | Mean capture | @20k | @37,654 | @70k |
|---|---:|---:|---:|---:|
| **B_only** | **0.10055** | 0.06485 | 0.09638 | 0.14041 |
| max | 0.07607 | 0.04741 | 0.07198 | 0.10881 |
| union_top10 | 0.07607 | 0.04741 | 0.07198 | 0.10881 |
| cotrain_disagreement | 0.05827 | 0.03692 | 0.05537 | 0.08252 |
| B_where_A_abstains | 0.04346 | 0.02892 | 0.04178 | 0.05968 |
| B_gated_by_A | 0.04328 | 0.02851 | 0.04055 | 0.06078 |
| B_minus_A | 0.03633 | 0.02309 | 0.03394 | 0.05196 |
| mean / rank_sum / consensus_top50 | 0.03310 | 0.01606 | 0.03032 | 0.05291 |
| geom_mean | 0.03301 | 0.01603 | 0.03032 | 0.05270 |
| min / intersect_top10 | 0.03060 | 0.01493 | 0.02747 | 0.04940 |
| A_gated_by_B | 0.02326 | 0.01056 | 0.01895 | 0.04028 |
| A_where_B_abstains | 0.02068 | 0.00923 | 0.01746 | 0.03536 |
| A_only | 0.01944 | 0.01085 | 0.01770 | 0.02976 |
| agreement | 0.00874 | 0.00407 | 0.00757 | 0.01458 |
| **random** | **0.00812** | 0.00387 | 0.00779 | 0.01269 |
| A_minus_B | 0.00181 | 0.00054 | 0.00158 | 0.00332 |

**B_only wins by a wide margin: 12.4× random and 5.2× A_only.** Every view-B-led arm
beats every view-A-led arm, which is consistent with the blocked AUCs (B 0.7779 vs A
0.6005).

Two results that differ from the pre-reset session, recorded rather than smoothed over:

- **"Every consensus/intersection arm is worse than random" did not reproduce.** Here
  `intersect_top10` (0.03060) and `consensus_top50` (0.03310) both beat random (0.00812)
  by roughly 4×. The pre-reset run had them at 0.0224–0.0255 against a random of 0.02875.
  I do not know why; the random control is the suspicious one, since it is the number
  that moved most (0.02875 → 0.00812) and it is the arm most sensitive to how the allowed
  mask is built. Treat the pre-reset consensus finding as unconfirmed.
- **A_only is much weaker here** (0.01944 vs the pre-reset 0.01228 — same direction,
  different magnitude).

### The emitted raster

`submission/gems52-r4-B_only-37654px-b-only-research.tif` — **exactly 37,654 px**,
sha256 `c6b9351f…45e0`. All seven gates pass (`evidence/r4_gates.json`): single band,
all finite, binary {0,1}, 3730×3292, EPSG:32611, **minimum distance to the catalogue
200.0 m**, budget as requested.

Against all 16 prior submissions the maximum Jaccard is **0.0430** (0.0338 against their
union), so this is a genuinely new field and not a recombination of shipped ones.

**Is it OK to submit?** Beats random 12.4× and A_only 5.2× on a spatially-blocked,
matched-budget holdout — so yes on the evidence we can actually gather. But the one assay
that could have compared it against the champion (0.2778) is the instrument that uniform
random defeats, so **it is not established as better than the incumbent**, and it is
labelled `research` for that reason. Per the standing rule about not spending a
submission slot on an unproven idea, I would not burn a slot on it yet.

Two bugs found by insisting on exactness here, both now fixed and tested: a quantile
threshold shipped **37,655** px when 37,654 were asked for (ties at the boundary), and
the random control was generated at a single fixed budget so it understated what random
achieves at 70,000 px.

---

## 5. Standing guidance for the next session

1. **Commit code before results.** The reset cost a full round because the code was
   uncommitted. This rebuild pushes after every stage.
2. **Never trust the instrument.** Run the random control first; if random is at or above
   the incumbent, stop and use hide-and-recover.
3. **The views are not independent on this plan.** Either fix the split or stop calling
   the exchange co-training.
4. **The halo defect still stands** (pre-reset, not re-measured here): our top-37,654 sat
   a median 412 m from the catalogue with 58% inside 500 m, against the champion's
   1,965 m. Deleting a 6,436-px ring within 200 m of a mapped trace cost **exactly zero**
   credit. The training target and the evaluation truth are inversely related.
5. **Do not spend a submission slot** on a field that has not beaten the current holdout
   best on a spatially-blocked holdout.
