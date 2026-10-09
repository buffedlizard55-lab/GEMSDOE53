# Pre-registration — session 2 (2026-10-09), lane C1 (conductivity–magnetic coherence)

**Session branch:** `arena/dc236d07-gemsdoe53` (session 2 on repo GEMSDOE53)
**Written BEFORE any session-2 experiment runs.** Experiment IDs: S2-E1 (canary), S2-E2 (holdout), S2-E3 (build + gates).
**Budget:** 3 experiments / 2 hours wall clock, per the parallel-run protocol. Start: 2026-10-09T00:55Z (setup and document writing are not experiments; experiment clocks start at each script's first model/feature evaluation, read from receipts).
**Prior session receipts are frozen:** `evidence/e1_*.json`, `evidence/e2_leakfree_holdouts.json`, `evidence/candidate_gems53-h1-*.json` are never overwritten. Session-2 outputs get distinct filenames.

## 0. What this session must produce (from the standing prompt)

1. A formally documented GEMSDOE29 leakage diagnosis (carried from session 1, `docs/leakage-review.md`; this session extends it with the verified KDD'11/TKDD'12 citation mapping — no new experiment needed).
2. A ranked screen of candidate hypotheses not yet tried (this file, section 6, mirrored in `docs/research/hypotheses.md`).
3. A **unique** GeoTIFF submission file, downloadable from the Pages site, with an **obvious** OK/NOT-OK-to-submit label, a unique name, and a ≤140-character comment.
4. One JSON run card; every number labelled HOLDOUT-DTI (with evaluator, withheld positives, CI) or ORGANIZER-CONFIRMED.

## 1. Governance decision GD-1 — interpretation of the raw duplicate rule (flagged for review)

The protocol sentence: *"If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots."*

**Facts on record** (session 1, IR-53-46/47/48/49, `evidence/uniqueness_diagnostics_*.json`):
- The raw 70% dot-overlap rule is **provably unsatisfiable** for any placement: the GEMSDOE13 lattice raster alone covers 99.87% of the footprint within 3 px, so *every* possible dot set exceeds 70% against it. A rule no candidate can pass is not a discriminator between lanes.
- Whole-grid surface Spearman rho is confounded by shared NaN structure and by the fact that most registry surfaces are catalogue-proximity rankings: session 1 measured 52 rasters flagged on whole-grid rho but **0** flagged on footprint-only rho.
- The stated intent of the rule is to detect *drift into another session's method* (a near-copy of another lane's predictions), not geometric coverage that any sparse map must have.

**Decision GD-1 (this session's agent, acting under "no manual input; flag irregularities"):** the gate runs BOTH readings and reports both. The verdict uses:
- `rho_footprint`: Spearman rank correlation on footprint pixels where both rasters are finite (scipy `spearmanr`, seeded subsample 300k), threshold 0.90. This is the literal "rank-correlation of your raster", restricted to the domain where both rasters make predictions.
- `overlap_final` (share of our dots within 3 px of a registry raster's dots) with **chance correction**: `lift = overlap_final / chance_coverage`, where chance_coverage is the share of footprint pixels within 3 px of that registry raster's dots. A raster is flagged iff `overlap_final > 0.70 AND lift > 1.5` (i.e., materially above what random placement gives). Overlap below chance (lift ≤ 1) can never be drift.
- Raw whole-grid values are still computed and stored (`rho_surface_whole_grid`, raw `overlap_final`) for transparency.
- **Acceptance (corrected gate):** no registry raster with `rho_footprint > 0.90`, and no raster with `overlap_final > 0.70 AND lift > 1.5`, both on the surface (pre-placement) and on the final dots.

**Verdict matrix (pre-registered):**
| Corrected gate | Holdout rule | Validators | Canary | Label |
|---|---|---|---|---|
| PASS | PASS | PASS | PASS | **OK TO DOWNLOAD AND SUBMIT** (corrected gate; raw values archived) |
| FAIL (any) | — | — | — | RESEARCH-ONLY / DO NOT SUBMIT |
| PASS | FAIL | — | — | RESEARCH-ONLY / DO NOT SUBMIT |

If the corrected gate passes while the raw rule flags, the file is labelled OK-to-submit **with an explicit GD-1 banner and irregularity IR-53-64** so the user can overrule; the literal-rule numbers remain in the receipt. This deviation is flagged for review in `registry/irregularities.json`.

## 2. Governance decision GD-2 — submission conformance target (REVISED after evidence check, flagged for review)

**Original draft:** make the primary file zero-filled outside the footprint, on the hypothesis that the user-reported organizer error *"Predicted values must be in range [0, 1]"* was caused by NaN outside the bounds.

**Evidence that falsifies that hypothesis (measured 2026-10-09):**
- The shared template validator (`/tmp/gems-template/scripts/validate_submission.py`, commit dcbbb19) records a REAL platform rejection with exactly this message, and its root cause was NaN **inside the sample's valid (scored) region** — not NaN outside it. The platform evidently tolerates NaN wherever the official sample itself is NaN (the sample predicts total absence and is the organizer's own template).
- All three files ever shipped from GEMSDOE53 (`docs/downloads/gems53-h1-relay-prune-q0p0073-nan.tif`, `docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif`, `submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif`) were re-audited pixel-exactly against `sample_submission.tif`: **0** NaN inside the sample-valid region, **0** finite outside, nodata=nan, finite values in [0,1]. None of them can reproduce the reported error as they stand.

**Revised decision GD-2:** the primary session-2 file is written **template-conformant**: finite values in [0,1] at every pixel where the official sample is finite; NaN exactly where the sample is NaN; GDAL nodata=nan; LZW compression. Both shared validators must exit 0. No zeros-outside variant is shipped as a candidate (it would violate the template's conformance rule and its platform behaviour is unproven; the portfolio's `-zeros` files' outside values will still be measured from the registry for the record). **IR-53-65 opened:** the user-reported rejection cannot be reproduced from any shipped GEMSDOE53 file; the exact file/step that produced it needs user confirmation (possibly a file from another repo, an extracted zip member, or a stale download).

## 3. Method (lane): C1 — conductivity–magnetic cross-scale edge coherence

**Physical statement.** A buried or covered fault that juxtaposes magnetic units and hosts a conductive damage zone (fluids/alteration) should express itself as (a) a linear edge in reduced-to-pole magnetics (band 2) and (b) a co-located linear edge in the conductivity surface (band 17), with consistent strike. Requiring *both* fields to agree at the same location and orientation rejects single-field artifacts (cultural noise in magnetics, inversion smearing in conductivity). Official mechanism analogues: USGS OFR 2009-1156 (aeromagnetic imaging of concealed faults, S31) and Finn et al. 2022 USGS 70230158 (fault-controlled hydrothermal conduits, S32) — analogues from other regions, not evidence for this one.

**Why it could mark an unmapped fault (not a catalogue one).** The feature uses no catalogue information at all: it is a pure geophysics product. Mapped faults in mountain corridors are only a subset of faults that offset basement; valley-fill-covered faults have no surface trace for the USGS/INGENIOUS compilers to map but still offset magnetic basement and can be conductive.

**Named non-fault process that could mimic it.** Ancient volcanic dikes/sills and lithologic contacts also produce co-located magnetic + conductivity edges; so do paleo-shorelines of pluvial lakes in conductivity. A high score on the catalogue holdout would NOT distinguish these; that confounder is named in the run card.

**Frozen feature definition (all computed on the footprint grid, 100 m):**
- Preprocess each band: sentinel-NaN → footprint median of that band (documented imputation; band finiteness kept as a covariate). Robust z-score: `(x - median)/IQR`, clip to ±5.
- Structure tensor at Gaussian scales σ ∈ {1, 2, 4} px: `J = G_σ ⊛ [Ix², IxIy, Iy²]` from the z-scored band. Line energy `E = sqrt(λ1)`, orientation coherence `c = (λ1−λ2)/(λ1+λ2)`, orientation `θ = ½ atan2(2Jxy, Jxx−Jyy)`.
- Features (14 total):
  - C1a_σ = `E` of band 17 at σ ∈ {1,2,4} (3)
  - C1b_σ = `E` of band 2 at σ ∈ {1,2,4} (3)
  - C1c_σ = `cos(2(θ17 − θ2)) · min(c17, c2)` at σ ∈ {1,2,4} (3) — signed orientation agreement weighted by both fields' linearity, in [−1,1]
  - C1d_σ = `z(E17_σ) · z(E2_σ)` clipped ±5 at σ ∈ {1,2,4} (3) — joint edge product
  - C1e_fin17, C1e_fin2 = original-finite indicators for bands 17 and 2 (2)
- Arm `bc1`: HGB classifier on the 19 stack bands + 14 C1 features, **no catalogue-distance feature** (leak-free by construction; also maximally distinct from H1 and from catalogue-proximity registry surfaces).
- Emission variants (pre-registered grid, identical grid to session-1 E2 for comparability): `top_q` q ∈ {0.005, 0.01, 0.02, 0.03, 0.05}; `thin_bin` and `thin_p` q ∈ {0.02, 0.05, 0.10} → 11 bc1 variants. Baseline rerun in the same run: `bands:top_q0p02` (the frozen design-B baseline).

**Canary (S2-E1):** each of the 14 C1 features alone, design B (withheld positives vs all non-visible-fault footprint pixels, fold 0, pooled): separability = max(AUC, 1−AUC); flag ≥ 0.90. Plus one joint-feature canary: C1d at best scale. All label-free by construction; the canary checks for accidental label encoding (e.g., via NaN structure).

## 4. Holdout rules (unchanged from session 1, design B)

- Folds: whole 8-connected segments, seed 53, K=5; 10 px buffer; positives = visible faults outside buffer; negatives = every footprint pixel that is not a visible fault (300k sampled per fold, seed 53, identical across arms).
- Stage 1: pooled DTI per variant (evaluator `gems53.core.dti` v1.0.0, parity-checked against template `src/metrics.py`), 95% t CI df 4. Selection rule: highest pooled DTI among bc1 variants whose pooled DTI point estimate exceeds the baseline `bands:top_q0p02` pooled DTI point estimate in the SAME run. If none exceeds, verdict = negative, no candidate built beyond a research copy.
- Stage 2 (spatial confirmation, template `src/blocks.py` super-regions): paired per-fold DTI difference of baseline vs selected, 95% t CI df 4; accept iff lower bound > 0.
- "Current holdout best" context (not the acceptance rule): session-1 h1:thin_bin_q0p1 — stage-1 pooled 0.141319 (selection-optimistic), stage-2 pooled 0.004049 vs baseline 0.000102, paired +0.003533 CI [+0.000619, +0.006447].

## 5. Build rules (S2-E3)

- Train the selected variant on ALL visible catalogue faults (design-B positives with no fold withheld) — for arm bc1 the catalogue enters only through training labels, never features, so prediction is identical for any fold.
- Write two files with identical pixels: primary `*-zeros.tif` (GD-2) and research `*-nan.tif`. Both single-band float32 EPSG:32611, official transform/bounds, values in [0,1].
- Validators: template `scripts/validate_submission.py` (exit code), in-lane checks (CRS/shape/transform/dtype/range/NaN-placement), sha256 of both files.
- Uniqueness gate: `scripts/uniqueness_gate_v2.py` implementing GD-1 (raw + corrected), against the full registry rebuild (`/tmp/gems53-registry`, manifest `evidence/registry_manifest_20261009.json`), checked on the surface before placement AND on the final dots.
- Name: `gems53-c1-condmag-<variant>-20261009T<utc>Z-<pixelsha8>-zeros`; comment ≤140 chars, beginning with the verdict word (`SUBMIT-CANDIDATE` or `RESEARCH-ONLY`).

## 6. Candidate hypothesis screen (5 candidates; rank = expected value / cost)

| Rank | ID | Layers | Signature (transform) | Why it could catch an UNMAPPED fault | Difference from repo/portfolio | Data viability here |
|---|---|---|---|---|---|---|
| 1 | **C1** cond–mag cross-scale coherence | bands 17 (`cond_surf`), 2 (`rtp`) | multi-scale structure-tensor edge coherence (section 3) | Covered-basin faults offset magnetic basement and host conductive damage zones with no surface trace | no cross-physics coherence feature exists in `src/gems53` or the 19-band stack; distinct from H1 (catalogue distance) and H2 (single-band ridges) | cached stack; validated this session |
| 2 | **C5** strain-budget residual | bands 4/7/8 (2nd invariant, shear, dilatation) vs visible-catalogue density | residual = strain − E[strain | catalogue density], fitted on visible data only (learn-predict separated) | high geodetic strain where the catalogue has no faults = slip deficit on unmapped active structures; direct measurement, not mapping | bands used raw before, but never as a catalogue-conditioned residual; named mimic: interseismic strain smoothing / interpolation artifacts | cached stack; viable |
| 3 | **C4** gravity–basement collinearity | bands 13/11/18 (isostatic gravity + gradients), 15 (basement depth) | directional collinearity of gravity-gradient vectors with basement-depth steps (multi-scale) | basement-involved faults under valley fill produce density steps invisible at surface | portfolio has single-band "structural" candidates; no gravity–basement joint collinearity detector; named mimic: isostatic flexure trends | cached stack; viable |
| 4 | **C7** seismic–conductive concurrence | bands 16 (earthquake density), 17 (conductivity) | rank-concurrence map with local permutation p-value | actively deforming, fluid-filled structures may be unmapped; concurrence suppresses each field's independent false alarms | no product/concurrence layer in stack; portfolio "seisgeom-ridgesnap" exists, so only this specific transform is candidate-new; named mimic: catalogue-driven event location bias | cached stack; viable |
| 5 | **C2/C3** (carried) raw ComCat event planes; Landsat thermal residuals | external | 3-D hypocentral planes; persistent multi-date thermal residuals | direct observations of activity/upflow independent of mapping | not in stack | **NOT viable in this environment** (egress); official sources named: USGS ANSS ComCat FDSN (https://earthquake.usgs.gov/fdsnws/event/1/), USGS Landsat C2 L2 (https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products); access/terms unchecked |

Portfolio-overlap caveat: ranks 2–4 are screened against registry filenames only; opaque filenames can hide overlap. None is "unique" until it passes the gate itself.

## 7. Deviation log

(amendments written here BEFORE the change, with reason; post-hoc edits forbidden)

- **DEV-C1-1 (2026-10-09, before S2-E1):** the section-3 agreement formula `A = cos(2Δθ)·min(c17,c2)` is energy-blind: the synthetic test `tests/test_c1.py::test_agreement_parallel_vs_perpendicular` showed coherence c=1 even in between-line regions where gradient energy is numerical noise (rank-1 tensors), so pure noise orientations would enter the score at full weight. Fix: energy-gated agreement `A = cos(2Δθ) · min(c17·u17, c2·u2)` with `u = E/(E + median_fp(E))` per field and scale (u → 0 where energy is negligible, → 1 where strong). Feature count unchanged (14). Everything else in section 3 is unchanged.
