# Pre-registration: GEMSDOE53 session of 2026-10-08

Written and committed **before** any experiment in this session was run. The commit timestamp is the
pre-registration record. Any change to a rule below after the commit must be listed in the run card as a
deviation, not silently applied.

## 1. Budget

- At most **3 experiments** (E1, E2, E3 below) and at most **2 hours** of wall-clock time for experiments.
- No weekly competition submission slot is used. Promotion to a slot is a separate selector step.
- Wall-clock start and stop are recorded in `evidence/run_card.json` (not estimated).

## 2. Hypotheses tested (ranked as in `docs/research/hypotheses.md`)

- **H1, segment-exact learn-predict separation.** Each training positive's distance feature is computed from
  visible faults **excluding its own segment**. Non-fault pixels use all visible faults. Emission pixels use all
  visible faults. This is the only distance construction in which every training positive is treated the same way
  an unmapped fault would be treated at prediction time.
- **M1, metric-aware thinning (shaping).** Keep the top-q candidate pixels by model probability. Then keep a greedy
  dominating set: process candidates in decreasing probability, accept a candidate only if it lies more than R = 3 px
  from every accepted dot. The kept dots are the emission. Two value modes: `p` (keep the probability) and `bin` (set
  to 1). Motivation: TP credit is a max over the 3 px neighbourhood, while FP credit is a sum over area, so a thin
  dominating set keeps TP and removes FP mass (see `src/submission_optim.py` in the shared template).

## 3. Shared tools (no private forks)

- Metric: `gems53.core.dti` (formula checked against the template's `src/metrics.py` on the same arrays; parity is
  recorded in the run card).
- Spatial-block folds: template `src/blocks.py` (`block_id_map`, `block_table`, `assign_folds`, `held_out_mask`).
- Writer and validators: template `src/submission_io.py` (`write_submission`, `conform_to_template`,
  `conformance_findings`), `scripts/validate_submission.py`, and `python -m src.submission_io validate-conformant`.
- Data: `scripts/fetch_data.py` (sha256 pins from the template's `data/bridge/manifest.json`).

Naming drift recorded: the protocol names `evaluate_holdout.py` and `submission_writer.py`. The template has no
files with those names. The mapping above is the nearest shared tool and is an irregularity for review.

## 4. Experiment E1: exploration on segment folds (seed 53)

- Folds: `segment_folds(cat, K=5, seed=53)`, 1 km (10 px) buffer, visible faults masked pixel-exactly, pooled DTI
  (alpha 0.2, beta 0.8, R = 3 px), t-based 95% CI on fold means with df = 4.
- Models: HistGradientBoostingClassifier (identical settings to `exp2_holdout_arms.py`); 300k negatives drawn with
  `default_rng(53)` (a fresh generator per arm, so both arms see identical negatives).
- Arms: `bands` (19 label-free bands) and `h1` (bands + H1 distance).
- Variants per arm: top-q for q in {0.005, 0.0073, 0.01, 0.02, 0.03, 0.05}; thinned (M1, value `p`) for q in
  {0.02, 0.05, 0.10}; thinned (M1, value `bin`) for q in {0.02, 0.05, 0.10}.
- Reproduction check: the `bands` top-q values at q in {0.005, 0.0073, 0.01, 0.02} must equal
  `evidence/exp2_holdout_arms.json` (0.021681, 0.025063, 0.027919, 0.035233). A mismatch stops the run.
- Leakage canary: each feature alone (19 bands, H1 distance, and the leak-free cross-fit distance from the
  previous session) on the withheld fold positives against the buffered background. Gate: separability above 0.90
  means leakage until proven otherwise.
- **Selection rule for E2:** among the variants whose E1 pooled DTI is above the current holdout best (`bands`,
  top-q, q = 0.02, pooled DTI 0.035233), pick the one with the highest pooled DTI. If none qualifies, the result is
  negative and E2 does not run for a new variant. The `bands` baseline is then retained for E2.

## 5. Experiment E2: confirmatory spatially blocked holdout (contiguous super-regions)

- Folds: template `assign_folds(table, n_folds=5, seed=53, mode="contiguous")` on 512 px blocks (51.2 km), with
  `block_table(..., valid=footprint, labels=cat)`.
- Whole-segment hiding: each known-fault segment is assigned to the fold of the block containing its centroid pixel.
  The withheld truth for fold k is every known-fault pixel of the segments assigned to k. Buffer: 10 px around the
  withheld pixels, excluded from training.
- Models are re-fitted on each fold. Only the E1-selected variant and the `bands` top-q 0.02 baseline are scored.
- **Acceptance rule (paired):** per-fold differences d_k = DTI(selected) − DTI(baseline). Accept only if the 95%
  t-interval lower bound of mean(d_k) with df = 4 is above 0. Otherwise the variant does **not** beat the holdout
  best.

## 6. Experiment E3: candidate construction, validation and uniqueness

- Build the candidate on **all** known faults (no hold-out), with the E1/E2 recipe. Emission is zero on known faults.
- Validators (all must pass): template `scripts/validate_submission.py` against `sample_submission.tif`;
  `python -m src.submission_io validate-conformant`; and an in-lane check of CRS, shape, transform, dtype float32,
  one band, NaN exactly outside the footprint, values in [0, 1] on the **whole** array (not only the footprint).
- Uniqueness, against every registry raster that could be rebuilt from the GEMSDOE* repositories:
  - **pre-placement:** Spearman rho of the continuous surface and the top-q candidate mask against each raster;
  - **final dots:** Spearman rho of the written raster, and the share of our dots within 3 px of that raster's dots.
  - Flags: rho > 0.90 or overlap > 0.70 for any file means **drift / duplicate**. The flag is recorded. The threshold
    is **not** changed here. A chance-corrected reading is reported alongside, as a diagnostic only.

## 7. Labels and verdict

- **Validated / OK to submit** requires: E2 acceptance AND every E3 validator AND uniqueness below both thresholds for
  every registry file AND every feature in the chosen model canary-clean (separability at most 0.90).
- **Research-only / DO NOT SUBMIT** otherwise. The file is still provided for download, but its label says it must
  not be uploaded.
- Every number is labelled HOLDOUT-DTI (evaluator name and version, withheld positives, 95% CI) or ORGANIZER-CONFIRMED
  (only from a submission-page receipt; none exists in this session).
- Known caveat stated before running: E1 selects among about 24 variants on the same folds, so the E1 gain is
  optimistic. E2 is the fair test.

## 8. Amendment DEV-1 (written after E1 finished its design-A arms and before any design-B run)

**Found during E1.** The exp2 negative pool was `fp & ~cat & ~buf`. The buffer is defined from the WITHHELD faults, so
the pool depends on withheld locations. Measured on the segment folds (seed 53): the buffer removes 371,176 to 390,883
negative pixels per fold, which is 7.3% to 7.6% of the pool, and all of them lie within 10 px of a withheld fault.
Those are the hardest negatives, and dropping them can only push the emission toward withheld locations. This is the
negative-pool side channel that the GEMSDOE29 audit flagged (docs/leakage-review.md). The E1 H1 fold-0 jump (0.0266 to
0.0631) must not be read as a result until it is re-tested under a pool that does not depend on withheld labels.

**Corrected design (design B), used for every number in E2 and E3:**
- positives: visible faults outside the 10 px buffer (pixel-exact visible mask, as before);
- negatives: every footprint pixel that is NOT a visible fault (withheld faults, buffer and background are all
  candidates, so the training pool does not depend on withheld locations). This is the situation the real
  competition is posed in: unknown faults sit inside the unlabelled pool;
- every other rule unchanged: 300k negatives per fold, `default_rng(53)` per arm, same model, same folds, same
  evaluator, pooled DTI, t-based CI with df = 4.

**Consequences, pre-registered now:**
- The current holdout best is **re-established under design B**: bands top-q 0.02 under design B. The 0.035233 figure
  is design A and is reported only as the leaky reference.
- Selection rule of section 4 applies unchanged, against the design-B baseline.
- Confirmation rule of section 5 applies unchanged: spatial contiguous super-regions, paired t-interval (df = 4) lower
  bound above 0 against the design-B bands top-q 0.02 baseline.
- Canary (section 4) is recomputed under design B: withheld positives against the full non-fault background
  (footprint and not any known fault), not against a buffered background, since the buffer is also a withheld-derived
  exclusion.
- E1 (design A) is kept in `evidence/e1_h1_thin_holdout.json`, unchanged, and is not used for selection.
- Experiment count: E1 (design A, exploration, stopped as a design error) and E2 (design B, selection plus confirmation)
  are the two holdout experiments. E3 is the build. The 3-experiment limit is respected.
- Removed: `scripts/e2_spatial_block_confirm.py` (design A, written but never run) is deleted in the same commit. Its
  content is superseded by `scripts/e2_leakfree_holdouts.py`.
