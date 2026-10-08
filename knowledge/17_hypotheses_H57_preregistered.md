# 17 · H57 hypothesis slate — written **before** the H57 code ran

**Registration kind: blind.** This file and `registry/h57_preregistration.json` were written before
`src/gems52/h57.py`, `scripts/run_h57_cotrain.py` and `scripts/build_h57_submission.py` existed, so
unlike the H56 slate (`knowledge/15` §Chronology) nothing here can be a retrospective rationalisation.
The frozen quantities are marked **[FROZEN]**; every one of them is checked in
`scripts/run_h57_cotrain.py` and `scripts/build_h57_submission.py` and a mismatch is a hard failure.

**Authentication limit, restated because it governs every number below.** Every leaderboard score in
this repo is *owner-reported*. `registry/leaderboard_snapshot_2026-10-07.json` records the public
board; no organiser receipt in this checkout maps a score to a filename or a SHA-256. Everything
downstream of a score is therefore conditional arithmetic, and no file produced under this slate may
be described as "verified to score X".

---

## 0 · The constraint that ranks everything

From `src/gems52/metric.py` (literal transcription of the published metric, `R = 300 m`,
`alpha = 0.2`, `beta = 0.8`) and its identity `FNw = |G| - TPw`:

```
DTI = TPw / ( 0.2 * TPw + 0.2 * (S - M) + 0.8 * |G| )          [M = Σ_x p(x)·max_g k(d(x,g))]
```

and for one marginal pixel of weight 1 that covers a previously uncovered truth pixel at distance
`d` (credit `k(d)`, tax `1 - k(d)`), the module docstring's own rule
`c·(1 - α·DTI) > α·DTI·f` **reduces exactly to**

> **accept a pixel iff `k(d) > α·DTI`.**

At `DTI = 0.2778` that is `k(d) > 0.0556`, i.e. within **283 m**; on the 100 m lattice the
accepting offsets are d = 0, 1, 1.414, 2, 2.236, 2.828 px and nothing further. Consequences:

1. **The only two questions are "is there an unmapped fault pixel within 283 m of here" and "are
   two of my pixels fighting over the same truth pixel".** There is no score-dependent tuning knob.
2. **Add mass iff its credit density exceeds `0.2 · DTI`.** At the live scores that bar is
   0.055 – 0.064. `knowledge/10` measures it: the champion file averages 13.87 %, its
   double-corroborated core `P1` 16.3 – 20.5 %, its single-detector tail 0 – 5.3 %, uniform-random
   mass 2.79 %. **Anything at or below uniform-random density is pure loss.** The two dead cells in
   this family (`P3`, `P4`, 6,436 px) earned *exactly zero* and deleting them raised a real score
   from 0.2600 to 0.2778.
3. **Placement beats recall on this board** (`knowledge/01` §3): an identical-mass incoherent
   emission scores 0.0778, i.e. 3.6× worse.

Everything below is ranked by *expected credit-density gain ÷ implementation cost*, and every
candidate must beat the current holdout best before a slot is spent.

---

## H57-A · **Anisotropic (along-strike) node spacing** — RANK 1, implemented

* **Layers.** No new raster. The local strike field is the structure tensor of the smoothed density
  of the *credited* node cloud (the same object as `revealed.strike_field`, already measured at
  coherence 1.47–1.57× a matched random cloud, 16.8 % of nodes above coherence 0.8 versus 2.2 %,
  recovered strike 100–110° in array convention = NNE–SSW, which is the correct Basin-and-Range
  fabric for 37.3–40.7 N / 116.2–120.0 W).
* **Physical signature.** `TPw = Σ_g max_x p(x)·k(d(x,g))` credits each truth pixel **once, at its
  best weight**. On a 1-px truth trace with `k(0)=1, k(1)=2/3, k(2)=1/3, k(3)=0`, the credited
  truth inside one node interval `[0, s)` is

  | along-strike separation `s` | `1` | `2/3` | `1/3` | `0` / neighbour | sum | per node |
  |---|---|---|---|---|---|---|
  | **3 px** | 1 | 2/3 | 2/3 | — | 7/3 | **2.333** |
  | **4 px** | 1 | 2/3 | 1/3 | 2/3 | 8/3 | **2.667** |
  | **5 px** | 1 | 2/3 | 1/3 | 1/3 | 2/3 | **3.000** |

  so three px — the separation every emitter in this repo uses — leaves **28.6 % of the credited
  truth per node on the table**, because the second node's 300 m disc largely re-covers the first
  node's. Six px and beyond stop gaining credit and start leaving truth pixels with `k = 0`
  entirely, so **5 px is the ceiling, not "as far as you like"**. Across the strike the opposite
  holds: a node 3 px off the trace is a *different* line and is not redundant, so 3 px stays there.
  These three sums are not asserted here — they are computed from `gems52.metric.max_cover` in
  `tests/test_h57.py::test_along_strike_spacing_credit_matches_closed_form`, together with a
  ±1 px placement-error robustness check.
* **Why it must catch something the catalogue cannot.** The arm is placed *along* the strike of
  structure that already exists, beyond the mapped tip, so it is off-catalogue by construction
  (`revealed.CORRIDOR_M` = 200 m ring deleted).
* **Difference from everything in this repo.** Every emitter here — `nodes.spacing_select`,
  `holdout.emit_topk`, `emit.greedy_emit`, H56's frozen "≥ 3 px minimum separation" — uses an
  **isotropic** minimum separation. This is the first emitter whose separation is a *tensor*:
  `min_sep_along_strike = 4 px`, `min_sep_across_strike = 3 px`. It is derived from the kernel
  algebra, not fitted, and it is the only hypothesis here whose expected effect is on the
  denominator rather than on the numerator.
* **Validation.** Tip-mode folds (the only instrument that can see near-trace mass, `knowledge/03`
  N-3), matched node budget, isotropic-3 versus anisotropic-(3, 4) versus anisotropic-(3, 5).
  Both a *strict* isotropic control (`d ≤ 3` blocked) and a *loose* one (`d < 3`, which is what the
  incumbent family's measured "median nearest-neighbour spacing 3.0 px" is consistent with) are
  reported, so a strict-vs-loose gain is never reported as an anisotropic gain.
* **Cost.** ~1 h. **Expected gain.** Up to +28.6 % of arm credit at the same node count; the arm is
  15–20 k of a ~40 k node file, so ~+5–7 % of file credit, i.e. ~+0.015–0.02 DTI. Real but bounded,
  and only on the *new* arm — the core's nodes are fixed by set algebra and cannot be moved.

## H57-B · **A-only buried-structure arm** — RANK 2, implemented

* **Layers.** View A = potential-field and subsurface bands `{1,2,3,4,5,9,11,13,14,15,16,17,18}`
  (mag_anom, rtp, tmi_hg, geod 2nd-invariant, iso-grav slope/vertical-horizontal gradient/anomaly,
  tmi, tmi vertical gradient, depth-to-basement, seismicity density and distance, surface
  conductivity). View B = surface `{12, 19}` (detrended elevation and its slope) **plus** the
  restored external surface proxies (12-band 1 m LiDAR scarp stack, 4-band GeoDAWN radiometry and its
  4 ratio bands) used *only* as an abstention witness. Band 6 is assigned to View B as radiometric
  total count, per `evidence/h53_band6_identity.json` (Spearman +1.0000 against the GeoDAWN
  total-count grid) and `registry/irregularities.json` IR-52-019, which corrected the file's own
  `data_category = magnetic_data` tag.
* **Physical signature.** A normal fault that does not reach the surface has no geomorphic
  expression: the surface view must abstain, while the potential field still shows the structural
  grain (an offset basement edge, a magnetic basement step, a conductivity contrast at depth).
  `knowledge/03` already measured the supporting fact: A-only pixels sit at median band-15
  (depth-to-basement) rank 455.0 against 296.7 for B-only and 251.2 for concordant — the A-only
  stratum *is* the deeper-cover stratum.
* **Why it must be off-catalogue.** The USGS/INGENIOUS product is a **mapped-surface** product. It
  cannot contain a fault with no surface trace, which is exactly what "A confident, B not" selects.
  This is also the only argument in the repo that is consistent with the measured fact that the
  hidden truth never comes within 200 m of the mapped catalogue (`knowledge/10` §2).
* **Difference from repo history.** Two earlier rounds used disagreement: N-1 used it as a
  **pseudo-label source** (worst arm measured: 0.0084 tip / 0.0078 hide against random 0.0253 /
  0.0396) and H53 used it to **stratify a budget**. This round uses disagreement as the
  **definition of the candidate population** and never as a label or as a training signal; the
  independence test is reported, and the round is abandoned if it fires.
* **Cost.** ~2 h. **Expected gain.** Unknown sign. Break-even is `rho_arm > 0.2 · DTI ≈ 0.06`; the
  arm is sized by `revealed.budget_rule` so that the core carries the file if the arm is worthless.

## H57-C · **Antisymmetric edge coincidence across physics families** — RANK 3, queued, not run

* **Layers.** `mag_vg` (9) / `mag_hg` (3) against `iso_grav_vg` (11) / `iso_grav_hg` (18), plus
  radiometric total-count band 6.
* **Physical signature.** A fault is a *discontinuity*, so the right cross-family statistic is the
  **antisymmetry** of an edge pair, `cos 2(θ_A − θ_B) → −1` at the same tile, not the symmetry
  (`→ +1`) that H53's `dicoincidence` gate scores. A susceptibility-contrast interface offsets the
  magnetic field step without offsetting the density step, and vice versa; a symmetric gate scores
  the regional fabric (37/100 pairs significant globally, which is why `knowledge/09` §3.1 records
  that the symmetric gate stopped discriminating).
* **Why off-catalogue.** Only ~5 % of the survey's magnetic interfaces are faulted; the rest are
  lithological. A *coincident magnetic–gravity discontinuity* is a different and sparser population
  from a mapped scarp.
* **Difference.** `dicoincidence` measures agreement of axial orientation within a 1.6 km tile
  against a rolled null. This measures signed **dis**agreement and would be a new statistic in this
  codebase.
* **Cost.** ~1.5 h. **Expected gain.** Unknown; cannot be computed from any accessible evidence, so
  per the standing rule it is **not** proposed for a slot until it beats the holdout best.

## H57-D · **Conductivity–depth paired across-strike contrast** — RANK 4, queued, not run

* **Layers.** Band 17 (surface conductivity) and band 15 (depth to basement), paired across the
  strike field from the credited node cloud.
* **Physical signature.** A deep-seated Basin-and-Range normal fault juxtaposes conductive
  sedimentary fill against resistive basement on the hanging-wall side; the contrast is largest
  where cover is thickest, i.e. exactly the A-only stratum.
* **Difference from repo history.** Band 15 has only ever entered as a scalar rank feature
  (`features.py`) and as a reported stratum median. It has never entered as a **paired across-strike
  contrast conditioned on the local strike**, which is the physically meaningful form.
* **Risk, stated before running.** `knowledge/03` N-6 measured six separate potential-field
  transforms at 300 m cell size at AUC 0.48–0.52 against the catalogue. That is a prior against
  this family and it is the reason this is rank 4 rather than rank 2.

## H57-E · **B-only veto (surface artifact suppression)** — RANK 5, implemented inside H57-B

* **Layers.** View B only.
* **Physical signature.** Roads, levees and erosion lines produce DEM curvature and LiDAR step with
  **no** potential-field response. A B-confident / A-abstaining pixel is therefore a *suspect*, and
  the brief says so.
* **Difference.** The repo has never used the surface view as a **negative** filter. It is nearly
  free (a mask), so it is implemented inside H57-B rather than as a separate arm, but it is listed
  separately because it is falsifiable on its own: on tip folds the veto must not remove credited
  mass.

---

## FROZEN decision rules (checked by the code, not by prose)

1. **No upload without a comparable preregistered holdout.** The gate is the one already frozen for
   this repo: mean lift over the matched single-view / baseline arm **≥ +0.005** and **≥ 3/4 folds**
   positive, on **both** instruments. Anything less is recorded as a failure and no slot is spent.
2. **Independence abandonment.** If the block-level out-of-fold negative-error correlation between
   the views reaches `|r| ≥ 0.60` on a non-degenerate statistic, co-training is abandoned and the
   round is reported as abandoned, not as a weak win (`spatial.independence` is fail-closed: a
   degenerate statistic returns `allow_exchange = False`).
3. **Masking.** Nothing inside the ≤ 200 m ring of a mapped catalogue trace is emitted, whatever any
   score says (`knowledge/01` §5 item 2, refuted on the bytes).
4. **Range.** `{0, 1}` only, all-finite, single band float32, EPSG:32611, 3730 × 3292, transform
   `(100, 0, 243350, 0, -100, 4508550)`. Never NaN — that is the mechanism behind the historical
   "Predicted values must be in range [0, 1]" rejection (`knowledge/03` N-5).
5. **Uniqueness.** The decoded `<f4` array must not equal any accessible prior, and the file must
   carry a documented share of cells outside the accessible prior-support union. A new filename is
   not uniqueness.
6. **Not-the-union.** The output must not equal `A_view ∪ B_view`, nor the union of the two named
   prior files it was derived from; the decoded-pattern and set checks are reported either way.
7. **A-only dossier.** Every arm candidate gets a written geological reasoning row: the View-A bands
   that fired, depth-to-basement and conductivity values at the node, the strike the node was placed
   on, the distance to the nearest mapped trace, and the explicit alternative explanations (road,
   stream, ridge crest, magnetic contact).
8. **Honest reporting.** The projection is reported with the interval and the prior it rests on, and
   the site states the probability that the target is *not* reached.