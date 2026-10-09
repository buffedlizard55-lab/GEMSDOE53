# Pre-registration S3 (2026-10-08): H8 gravity-gradient ridges, leakage repro, build gate

**Written and committed before any S3 run.** Amends nothing in the earlier pre-registration (`preregistration-2026-10-08.md`).
Lane: one method (H8) plus the GEMSDOE29 leakage reproduction. Budget: 3 experiments (S3-A, S3-B, S3-C).

## 1. Hypothesis H8 (gravity horizontal-gradient maxima)

- **Layer (label-free):** band 13 of `training_features.tif`, "Isostatic gravity anomaly - gravity after compensating for
  topographic mass". No label, no catalogue, no fault-derived layer is read.
- **Transform:** `src/gems53/h8.py`. Blakely and Simpson (1986) maxima of |grad g| (100 m cells, 4-sector non-maximum
  suppression), threshold at the 90th percentile of |grad g| over the valid footprint, border of 3 px removed.
- **Features (3):** R (ridge 0/1), S (|grad g| on ridge pixels, else 0), log1p(min(D, 60)) with D the distance to the
  nearest ridge pixel.
- **Targeted signature:** a density contrast with a linear, fault-parallel trend, which can show a fault under cover where
  the catalogue has no trace.
- **Differs from the repo:** band 13 is in the stack only as raw anomaly; band 11 is the vertical derivative, band 18 is a
  signed field labelled "horizontal gradient" (min -15.44, so not a magnitude; IR-53-63). No maxima or ridge transform
  exists here. H2 (magnetic Hessian ridges) is a different physical layer and a second-derivative operator.

## 2. Arms and holdout (design B, DEV-1 inherited, unchanged)

- Arm `h8` = bands (19) + [R, S, log1p D] (22 columns). Otherwise identical to E2: HGB (200 iters, lr 0.1, 31 leaves,
  l2 1.0, random_state 0), 300,000 negatives per fold from `default_rng(53)`, the 24 E2 variants.
- Stage 1: 5 segment folds (seed 53, 10 px buffer). Stage 2: the 5 spatial folds of E2 (template `src/blocks.py`,
  512 px blocks, seed 53). The script must reproduce the withheld-pixel count of each E2 spatial fold, or it stops.
- Evaluator: `gems53.core.dti` (alpha 0.2, beta 0.8, 300 m triangular kernel), pooled over folds; CI = t, df 4, of the
  fold mean.

## 3. Canary (feature alone, design B)

- Each of R, S, log1p D alone: positives = withheld faults, negatives = footprint non-fault pixels (E2 convention).
- Gate 0.90 on separability = max(AUC, 1 - AUC). Any feature above 0.90 halts the run as LEAK_SUSPECT.
- Reference: E2 canary, 19 bands max 0.591; H1 distance 0.768.

## 4. Decision rules (fixed in advance)

- **Stage 1 selection:** highest pooled DTI among h8 variants above the E2 design-B baseline (bands top-q 0.02 = 0.010562).
  Warning carried into every claim: selection and confirmation are on different fold sets only for stage 2.
- **Stage 2 comparisons (paired, per spatial fold):**
  (a) selected h8 minus the bands baseline (E2 rule, reproduced);
  (b) selected h8 minus the **current holdout best**, which is the E2 stage-2 H1 `thin_bin_q0p1` per-fold DTI read from
  `evidence/e2_leakfree_holdouts.json`. This is the "beats the holdout best" test.
- **Acceptance for (b):** lower 95% bound (t, df 4) > 0. Acceptance for (a) is reported but is not sufficient.
- **Negative outcome:** if (b) fails, H8 is recorded as NEGATIVE. The S3-C file is still written (the user asked for a
  unique file), labelled RESEARCH-ONLY, and no slot is recommended.

## 5. S3-A leakage reproduction (no selection)

- Reproduce the GEMSDOE29 construction: D_leaky = log1p(min(dist to FULL catalogue, 60)); positives = full catalogue.
- Show that D_leaky is exactly 0 on every training positive (the defect), that its separability on the design-B fold 0
  canary is 1.0 (the canary catches it), and that the legitimate H1 distance on the same fold is 0.77 (E2 value).
- No DTI is computed for S3-A. It is a sensitivity check of the canary.

## 6. S3-C build and gates

- Final model on all known faults with the arm that wins under section 4, or with the E2 baseline if none wins.
- Shared template writer and validators; uniqueness gate on the registry rebuilt today from GitHub
  (`/tmp/gems53-registry-now`, 1212 files, 635 unique sha256, 1189 on the official grid).
- The gate rule is **not changed** (rho > 0.90 or within-3 px overlap > 0.70). Its dense-raster defect is reported (IR-53-50).
- Label: OK TO SUBMIT only if every gate passes. Otherwise RESEARCH-ONLY / DO NOT SUBMIT. The file name and comment are
  generated from the label.

## 7. Known limits stated before the run

- The holdout truth is the catalogue. Gains here measure proximity to known faults, not discovery of unmapped faults (IR-53-42).
- Single seed; no model-variance estimate (L-25).
- 2 vCPU, no GPU. Runtime limit of this session: 2 hours.
