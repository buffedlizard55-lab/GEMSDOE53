# GEMSDOE29 leakage review

**Review date:** 2026-10-08 (UTC)  
**Lane:** catalogue-distance leakage diagnosis only  
**Disposition (updated 2026-10-08):** GEMSDOE29 verdict negative and unchanged; holdout corrected to design B (IR-53-37); candidate label in `docs/submissions/CURRENT.json`; no submission slot used

## Executive finding

The GEMSDOE29 public evidence records a real training-time target shortcut: its deprecated single-fit artifact builder trained on catalogue pixels while building the catalogue-distance feature from that same full label raster. For the constructed training sample, catalogue membership is therefore recoverable from the feature itself. The repository's archival note reports **TRAIN-AUC = 1.0** for the full artifact model and documents a perfect one-feature separation by the distance column. This is a training diagnostic only—not HOLDOUT-DTI and not ORGANIZER-CONFIRMED.

The distance-to-*available* catalogue is not inherently illegitimate at competition prediction time: the competition supplies the existing fault catalogue, and the private targets are described as faults not in that catalogue. The defect is using each training target pixel to construct its own feature. That changes the learning problem: training sees a feature that contains the mapped target, whereas an unmapped test fault is absent from the catalogue used at prediction. The correct repair is the documented learn–predict separation: hide whole target segments, construct every catalogue-derived training feature from visible faults only, then build the prediction-time features from the supplied visible catalogue.

This review did **not** execute the holdout. In the current GEMSDOE53 checkout there is no data, stack, evaluator, writer, registry, or raster template. Read-only inspection of GEMSDOE29 also found two protocol gaps that must be resolved in the shared evaluator before its historical holdout results can satisfy the protocol here: a possible hidden-label side channel in negative-sample selection, and fold-wise rather than pooled DTI reporting without the required interval. No candidate is validated; no competition TIFF is created.

## Update 2026-10-08: the holdout had its own leak (design A), corrected to design B

- **Finding (IR-53-37).** The first holdout (exp2 and E1, "design A") built its negative pool as `footprint & ~known & ~buffer`. The
  10 px buffer is defined from the withheld faults, so the pool depended on withheld locations. The buffer removed 371,176 to
  390,883 negatives per fold (7.3% to 7.6%), all within 10 px of a withheld fault. Those are the hardest negatives. Measured on
  fold 0 of the bands arm (top-q 0.02): 0.0266 under design A and 0.0106 under design B. The design-A H1 canary used the same
  buffered background, so its separability was inflated as well.
- **Correction (DEV-1, pre-registered before the run).** Design B: positives are visible faults outside the buffer; negatives are
  every footprint pixel that is not a visible fault. This is the situation the real competition is posed in (unknown faults sit in
  the unlabelled pool). The 0.035233 figure is design A and is not used for any decision.
- **Result under design B** (`evidence/e2_leakfree_holdouts.json`, HOLDOUT-DTI, 5 folds, seed 53, pooled, 95% t-interval df 4):
  bands top-q 0.02 = 0.010562 (CI 0.008337 to 0.012812). H1 with binary thinning at q 0.10 = 0.141319 (stage 1 selection among 24
  variants, so this value is optimistic). On spatially contiguous super-regions (stage 2, template `src/blocks.py`):
  baseline 0.000102, selected 0.004049, paired difference 0.003533 (CI 0.000619 to 0.006447). The paired lower bound is above 0,
  so the pre-registered rule accepts the variant. The absolute size on unseen super-regions is small.
- **Reading.** H1 is not a buffer artefact: its single-feature separability is 0.77 under design B (0.768 on fold 0, the maximum over folds), so the
  holdout genuinely rewards proximity to visible faults. That is the same proximity GEMSDOE29 used on its *full* label raster. The
  difference is that H1 never uses a withheld or self label. The holdout truth is the catalogue, though, so it measures proximity to
  known faults, not the discovery of faults the catalogue lacks (IR-53-42).
- **GEMSDOE29 verdict unchanged.** Its artifact builder still trains on full-label distance (mechanism above). This review adds a
  second requirement for any holdout: the training pool must not depend on withheld locations (IR-53-37).

## Formal diagnosis

### Prediction-time legitimacy

The official problem description says the challenge uses currently known USGS/INGENIOUS faults as training labels, that this catalogue is incomplete, and that expert-identified faults absent from the public database form the initial test target. It also says submissions cover the full region and defines the distance-weighted Tversky metric and GeoTIFF contract. Thus a feature based on the **provided, pre-existing catalogue** may be available at prediction time; that fact alone does not make it leakage.

Kaufman, Rosset, Perlich, and Stitelman's “Leakage in data mining: Formulation, detection, and avoidance” (KDD 2011; ACM TKDD 2012) asks whether target information used for a training example is legitimately available for its prediction, and recommends learn–predict separation. In this case the critical distinction is between (a) distance to the catalogue that will genuinely be available for an unmapped test fault and (b) distance to a raster that includes the very positive training pixel being labelled.

### Reconstructed failure mechanism

The publicly documented GEMSDOE29 artifact path can be written as:

\[
D_i = \log\!\left(1 + \min\{d(i,C_{\rm full}), 60\}\right),\qquad Y_i = 1[i\in C_{\rm full}],
\]

where \(C_{\rm full}\) is the full supplied catalogue and distance is in raster pixels. The old builder selected every catalogue pixel as a positive, then built `E` from `ctx.labels`; its first column is exactly `D`.

- If a training pixel is a catalogue positive, it is in `C_full`, so `D_i = 0` by construction.
- The old builder sampled background negatives only where distance from the catalogue exceeded 1.5 pixels. On this two-dimensional unit-pixel EDT grid the smallest possible retained distance is 2 pixels, so their feature values are at least `log1p(2) = 1.098612…`.
- Consequently a threshold on `D` perfectly separates the builder's sampled labels; reversing the feature direction gives perfect training AUC. The archived GEMSDOE29 note reports the full model's TRAIN-AUC as 1.0, a root split on `E_dist`, and only two distinct columns used by the fitted trees. These are archival owner-reported measurements; they were not re-run in this checkout.

The underlying source and archived diagnosis are linked in the audit table below. This is the textbook shortcut: not evidence that the model has discovered fault physics, and not evidence of performance on faults absent from the catalogue.

### Important distinction: feature is conditional, not universally forbidden

At prediction time the true unmapped target is not in the input catalogue, so the prediction feature is distance to the *known* faults, not distance to the unknown target. That feature can be legitimate and potentially useful. The training construction is invalid because it makes the known-catalogue training target available to its own feature. AUC near one on that training construction is therefore a canary result, not good news.

The required holdout can test whether the feature behaves legitimately: select whole components as withheld targets, exclude a spatial collar from training, make the withheld components absent from all catalogue-derived features, and compute those features from only `visible`. A high feature-only AUC on that properly separated holdout would still require provenance review—it could be genuine spatial predictability, residual leakage, or selection bias. The threshold in the parallel-run instructions is a conservative trigger for investigation, not a proof by itself.

## Read-only audit of existing upstream code

The following is an audit of public GEMSDOE29 files, **not** of GEMSDOE53's current feature stack. No upstream file was modified.

| Path / evidence | What the source supports | Status |
|---|---|---|
| [`src/gemsdoe/features.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/src/gemsdoe/features.py#L238-L269) | `build_catalogue_features(visible, ...)` computes `log1p(min(distance_transform_edt(~visible), 60))` as its first column, then orientation, density, and coherence fields from that supplied mask. | Direct source inspection. Safe for a hidden target only if the caller passes the fold's visible catalogue. |
| [`scripts/build_repo_candidate.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/scripts/build_repo_candidate.py#L73-L126) | The deprecated builder takes all `ctx.labels` as positives, builds both `E` and tip-continuation features from `ctx.labels`, then fits. The `E_dist` column alone gives the deterministic separation; the other catalogue-derived columns also require visible-only construction. Its own header says not to use this path. | Direct source inspection; this is the confirmed defect path. |
| [`knowledge/33_artifact_leakage_and_crossfit_2026-10-03.md`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/knowledge/33_artifact_leakage_and_crossfit_2026-10-03.md) | Records the measured training separation, tree use, byte-identical arms, and the cross-fitted repair. | Owner-reported evidence, not an organizer receipt or a current-session experiment. |
| [`scripts/build_crossfit_candidate.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/scripts/build_crossfit_candidate.py#L223-L238) and [`tests/test_artifact_leakage.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/tests/test_artifact_leakage.py#L62-L69) | The cross-fitted artifact path builds `E` and catalogue extensions from `d.visible` for training, uses hidden training components as positives, and uses the full supplied catalogue only for prediction. | The main feature shortcut is addressed in that path; not independently executed here. |
| [`src/gemsdoe/experiment.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/src/gemsdoe/experiment.py#L128-L164) and [`scripts/build_crossfit_candidate.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/scripts/build_crossfit_candidate.py#L223-L238) | The holdout `Cell` constructs `E` from `d.visible`, but both the screen and cross-fitted builder select negative candidates with `d.train_region & ~ctx.labels & ~near`. `ctx.labels` is the full catalogue, including labels hidden for the holdout. | **Unresolved possible side channel.** If hidden-test component pixels extend into `train_region` beyond the collar, their labels influence which locations can be sampled as training negatives. The effect on stored folds has not been measured. The shared tool should prove the training-row set is invariant to hidden-test labels, or remove this dependency. |
| [`src/gemsdoe/features.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/src/gemsdoe/features.py#L115-L235) | Static feature construction uses geophysical, terrain, strain/seismicity, radiometric, conductivity, and geothermal well/spring inputs; the GDR helper explicitly does not use its `dist_known_fault_px` field. | Source provenance is encouraging, but no per-feature holdout AUC canary was run here; **not cleared**. |
| [`src/gemsdoe/holdout.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/src/gemsdoe/holdout.py#L1-L125) | The historical holdout hides whole 8-connected raster components, uses a spatial collar, derives catalogue features from `visible`, and masks visible labels during scoring. It labels the result a catalogue-gap proxy, not new-fault truth. | Useful split structure, subject to the negative-sampling issue above and the aggregation issue below. |
| [`scripts/run_holdout_screen.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/scripts/run_holdout_screen.py#L105-L108), [`fold rows`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/scripts/run_holdout_screen.py#L277-L285), and [`gate aggregation`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/scripts/run_holdout_screen.py#L128-L166) | The scorer computes one DTI per fold, stores row-wise fold results, and summarizes paired fold deltas. | **Not the requested pooled DTI evaluator.** It does not provide the required pooled numerator/denominator plus a 95% CI. |
| [`tests/test_artifact_leakage.py`](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/tests/test_artifact_leakage.py#L25-L45) | The regression test verifies zero feature values on a toy catalogue and that off-catalogue values are positive, but it does not recreate the artifact's sampled negative set and assert the exact class separation or independently calculate feature-only AUC. | Test is useful but weaker than its explanatory text; strengthen in the owning template. |

### Arithmetic irregularity to fix upstream

The archived explanation writes `log1p(1.5) = 1.0986`. That equality is false: `log1p(1.5) = log(2.5) ≈ 0.916291`, whereas `log1p(2) = log(3) ≈ 1.098612`. The separation claim can still be correct because a two-dimensional EDT on a unit square grid has no attainable distances between 1.5 and 2, and the negative filter is strictly `> 1.5`; nevertheless, the text should say the minimum *attainable retained pixel distance* is 2, not equate `log1p(1.5)` with `log1p(2)`. The current toy test does not verify that sampled-negative minimum.

## Holdout protocol and result status

The user-specified evaluation requires whole-segment hide-and-recover with a buffer; catalogue-derived features computed only from visible faults; exact masking of visible faults; **pooled** official DTI at α = 0.2, β = 0.8, and the 300 m triangular kernel; a 95% interval; and a feature-alone leakage canary. The inspected legacy GEMSDOE29 screen is not sufficient evidence for this protocol because it emits per-fold DTI rows and the stored report does not provide a pooled estimate, a segment/block-bootstrap interval, or an AUC table for every feature alone. Its historical proxy values must not be restated as current HOLDOUT-DTI results under this protocol.

The current GEMSDOE53 checkout contains none of the named `evaluate_holdout.py` / `submission_writer.py` files, nor a local equivalent, feature cache, label raster, or sample-submission template. The DrivenData data page redirected to login in this review. Therefore the required evaluator version, withheld-positive count, confidence interval, feature-only holdout AUCs, registry correlation/overlap, TIFF hash, and format-validation output are all **not run / unavailable**. No number in this review is represented as HOLDOUT-DTI or ORGANIZER-CONFIRMED.

### Required shared-template fixes before trusting a number

1. **Remove hidden-target influence on training-row construction.** In a fold, construct candidate negatives from the fold's visible catalogue and training positives plus the preregistered spatial buffer; do not inspect `ctx.labels` for withheld components. Add a regression test that toggling hidden-test labels cannot alter any training feature, sampled negative index, or fitted training input.
2. **Produce the required pooled estimator.** Sum the official `TP_w`, `FP_w`, and `FN_w` sufficient statistics over all withheld segments/folds, then calculate one pooled DTI. Report the evaluator commit/version, withheld-positive count, and a 95% component- or spatial-block-bootstrap interval. Keep per-fold values as diagnostics, not as a substitute for pooling.
3. **Run the feature-alone canary.** For every actual feature column, derive it from the fold's legitimate information set and report holdout AUC with orientation/provenance documented. Investigate every result over the user-specified threshold before trusting a multivariate model. A high score is a trigger, not automatic proof of illegal source data.
4. **Audit all inputs, not just the feature matrix.** Include negative sampling, masking, normalization, feature selection, imputation, thresholds, top-k selection, and postprocessing in the learn–predict separation review.
5. **Fix the shared template once.** GEMSDOE53 must not copy or privately fork the evaluator/writer. This branch documents the defects; it does not claim to have patched GEMSDOE29 or any other shared repository.

## The H33 score question and uniqueness gate

The prompt describes the GEMSDOE32 H33-2-B2 artifact as having the group's best score. However, the linked GEMSDOE32 page labels the H33-2-B2 file **UNSCORED**, describes its live-mirror figures as projections/proxy evidence, and explicitly says there is no organizer score for that artifact. The page explains its method as a B=2 catalogue-flank prune applied to a dotted base. Mechanistically, removing nearby dots could reduce false-positive prediction mass while retaining some broader line coverage under the official distance-weighted metric; whether it preserved enough true-positive credit is an empirical question. That is a plausible explanation for an owner-side proxy change, not evidence that this artifact earned the claimed organizer score. A score attribution would require the submission-page receipt; none is in this checkout. No defensible claim that a new submission will exceed the prompted value can be made until a comparable, protocol-compliant holdout beats its frozen control.

The supplied prompt also states incompatible current-leader values. The GEMSDOE32 page's leaderboard section is an owner-maintained snapshot with an earlier read date, not a current submission receipt. I did not scrape or manually monitor the live leaderboard: DrivenData's [Terms of Use](https://www.drivendata.org/termsofuse/) prohibit robots/automatic access and manual monitoring/copying without prior written consent. Accordingly, neither the quoted H33 score nor any claimed current top score is used as a benchmark here. An automated “current feed” is a project requirement blocked until an expressly authorized feed or written permission exists. No projection has been called a score.

No surface candidate or final-dot raster exists in this checkout, and no registry rasters are present. The pre-placement and final-dot rank-correlation / within-three-pixel duplicate checks were **not run**. Uniqueness is unknown, not passed. Creating a dummy or copying a prior TIFF would violate the brief and would not be a useful or valid submission.

## Final decision and next steps

**Verdict: negative.** This session confirms the documented mechanism from public upstream code and identifies evaluation risks; it does not establish a new candidate's holdout performance. No TIF is created and no weekly slot should be used.

When the shared, authorized data/tools are available, the next lane-compliant run should first correct and test the shared holdout path, then execute the feature-alone canary and pooled-DTI interval against the frozen baseline. Only a unique candidate that beats the comparable holdout best should be formatted with the shared writer, re-opened for range/NaN/CRS/shape/transform checks, and compared against registry rasters both before placement and on final dots. A holdout improvement remains proxy evidence, never a guaranteed leaderboard result.

## Sources for manual review

| Claim | Source | Evidence class |
|---|---|---|
| The test target consists of expert-identified faults absent from the existing public database; the known-fault catalogue is incomplete. | [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Official competition source |
| Metric definition and submission contract (UTM 11N / EPSG:32611, 100 m, matching bounds, one float32 band, probabilities in [0,1]). | [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Official competition source |
| Leakage definition and learn–predict separation framework, “Leakage in data mining: Formulation, detection, and avoidance.” | [KDD 2011](https://doi.org/10.1145/2020408.2020496) · [ACM TKDD 2012](https://doi.org/10.1145/2382577.2382579) | Primary research sources |
| GEMSDOE29 artifact defect and cross-fit correction. | [GEMSDOE29 knowledge note 33](https://github.com/buffedlizard55-lab/GEMSDOE29/blob/main/knowledge/33_artifact_leakage_and_crossfit_2026-10-03.md) | Owner-reported, code-linked; not organizer confirmation |
| Feature code, artifact builder, holdout sampler, metric script, and regression tests. | [GEMSDOE29 source tree](https://github.com/buffedlizard55-lab/GEMSDOE29) | Read-only code inspection |
| H33-2-B2 status and the distinction between owner proxy/projection and organizer score. | [GEMSDOE32 public page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) | Owner-maintained page; not a submission receipt |
| Data access requires login in the fetched session. | [DrivenData data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) | Direct fetch redirected to login |
| Robots/automatic website access and manual monitoring/copying without prior written consent are prohibited. | [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) | Official Terms of Use, fetched directly |
| Linear stream courses and other non-fault lineaments can confound terrain lineament interpretation. | [USGS Open-File Report 89-365](https://pubs.usgs.gov/of/1989/0365/report.pdf) | Official USGS report; general context, not local validation |

## Pass log

- **Pass one — review:** inventoried the local checkout; read the official problem/metric/submission pages and leakage paper; inspected the upstream artifact, feature, holdout, and test sources.
- **Pass two — adversarial check:** distinguished prediction-time legitimate catalogue distance from target-derived training distance; checked the numerical `log1p` statement; found the negative-pool dependence on full labels and the fold-wise score aggregation mismatch; checked H33 evidence provenance.
- **Pass three — acceptance check:** confirmed no local data, evaluator, writer, registry raster, TIFF, or test suite exists; did not invent a score, validator result, uniqueness pass, or competition-ready file. Run card records the negative outcome.
