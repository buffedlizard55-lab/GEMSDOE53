# GEMSDOE29 leakage review

**Review date:** 2026-10-08 (UTC), citations verified and addendum added 2026-10-09 (session 2)  
**Lane:** catalogue-distance leakage diagnosis only  
**Disposition (updated 2026-10-08):** GEMSDOE29 verdict negative and unchanged; holdout corrected to design B (IR-53-37); candidate label in `docs/submissions/CURRENT.json`; no submission slot used

## Session-2 addendum (2026-10-09): verified citation record and the formal test applied

**Citations now verified line-by-line from official/authoritative bibliographic sources (IR-53-12 resolved):**

- **KDD '11 (three authors):** Kaufman, S., Rosset, S., Perlich, C. "Leakage in data mining: formulation, detection, and avoidance." *Proceedings of the 17th ACM SIGKDD (KDD '11)*, pp. 556–563, 2011. DOI [10.1145/2020408.2020496](https://doi.org/10.1145/2020408.2020496). Verified via [dblp record conf/kdd/KaufmanRP11](https://dblp.org/rec/conf/kdd/KaufmanRP11.html) and [Tel Aviv University CRIS](https://cris.tau.ac.il/en/publications/leakage-in-data-mining-formulation-detection-and-avoidance-2/) (both list exactly these three authors, these pages, this DOI).
- **ACM TKDD 2012 (four authors, the version the standing prompt quotes):** Kaufman, Rosset, Perlich **and Stitelman**, *ACM TKDD* 6(4):15, 2012 (S45). The prompt's four-author attribution is correct for the journal version; Stitelman does not appear on the KDD '11 conference paper.

**The KRS(-S) formulation applied to GEMSDOE29, step by step:**

1. *Leakage definition* — information about the target that "should not be legitimately available" is used to mine the model. Operational test: for a suspiciously strong feature, ask whether it **could only take its observed value because the label is already known**.
2. *Apply to `E_dist = log1p(min(d(i, C_full), 60))` with label `Y = 1[i ∈ C_full]`*: every positive has `E_dist = 0` **by construction** (a pixel's distance to a set it belongs to is 0); the builder's negative filter (`d > 1.5 px`) makes every negative ≥ `log1p(2) ≈ 1.0986`. The feature can take the value 0 *only* when the label is 1 — the observed value is a deterministic consequence of label membership. This is the textbook case, not borderline.
3. *Detection signature* — single-feature TRAIN-AUC = 1.0 (owner-archived measurement), root split on the distance column, two distinct columns used by the fitted trees: consistent with a feature that re-expresses the label.
4. *Why the fix is learn–predict separation* — at genuine prediction time the target (an unmapped fault) is **absent** from the catalogue the distance is computed against, so the legitimate prediction-time feature is distance-to-*visible*-catalogue. Training must therefore present the same situation: hide whole target segments, compute every catalogue-derived feature from visible faults only (this repo's design B, `h1_segment_exact_distance`), and keep the training pool independent of withheld locations (IR-53-37).
5. *Template, not isolated incident* — the same question is applied to every feature in the current stack via the per-feature canary (gate: single-feature separability ≥ 0.90 on a leak-free holdout = leakage until proven otherwise). Session-1 E1/E2 ran it for the 19 bands + H1; session-2 S2-E1 runs it for the 14 C1 features (`evidence/s2_c1_holdout.json`).

## Executive finding

The GEMSDOE29 public evidence records a real training-time target shortcut: its deprecated single-fit artifact builder trained on catalogue pixels while building the catalogue-distance feature from that same full label raster. For the constructed training sample, catalogue membership is therefore recoverable from the feature itself. The repository's archival note reports **TRAIN-AUC = 1.0** for the full artifact model and documents a perfect one-feature separation by the distance column. This is a training diagnostic only—not HOLDOUT-DTI and not ORGANIZER-CONFIRMED.

The distance-to-*available* catalogue is not inherently illegitimate at competition prediction time: the competition supplies the existing fault catalogue, and the private targets are described as faults not in that catalogue. The defect is using each training target pixel to construct its own feature. That changes the learning problem: training sees a feature that contains the mapped target, whereas an unmapped test fault is absent from the catalogue used at prediction. The correct repair is the documented learn–predict separation: hide whole target segments, construct every catalogue-derived training feature from visible faults only, then build the prediction-time features from the supplied visible catalogue.

At the initial read-only stage of this review, no holdout had yet been executed and the checkout lacked the experiment inputs. The later E1/E2 work fetched the hash-pinned public mirror, ran the shared template metric parity check, and performed the corrected design-B holdout; the resulting evidence and limits are recorded below. The early GEMSDOE29 holdout path still had a possible hidden-label side channel in negative-sample selection (IR-53-37), so its design-A numbers are not used for decisions. A research-only GeoTIFF was subsequently built in E3, but it failed the raw registry uniqueness rule and is explicitly not a submission candidate.

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

Kaufman, Rosset, Perlich, and Stitelman's verified ACM TKDD 2012 article, “Leakage in data mining: Formulation, detection, and avoidance” (S11; the separately cited KDD 2011 version is not verified here, IR-53-12), asks whether target information used for a training example is legitimately available for its prediction, and recommends learn–predict separation. In this case the critical distinction is between (a) distance to the catalogue that will genuinely be available for an unmapped test fault and (b) distance to a raster that includes the very positive training pixel being labelled.

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

The legacy GEMSDOE29 screen is useful for identifying the feature-construction defect, but its reported holdout rows do not by themselves satisfy this session's protocol. The parallel-run rule requires learn–predict separation, whole-segment hide-and-recover, a withheld-label-independent training pool, feature-alone canaries, pooled HOLDOUT-DTI with uncertainty, and uniqueness checks before and after placement.

### Design A was invalid; design B is the decision result

- **Design A (E1 and the earlier exp2 reference) is not used for decisions.** Its negatives were selected as `footprint & ~known & ~buffer`; the buffer was generated from withheld faults. That hidden-location side channel also appears in the separate H2 `scripts/x2_ridge_holdout.py`, so its apparent ridge gain is diagnostic only (IR-53-37). No H2 design-B rerun was performed because the experiment budget was exhausted.
- **Design B (E2) removes that side channel:** positives are visible faults outside the 10 px buffer; negatives are every footprint pixel that is not visible. It evaluates 24 variants on segment folds, then confirms the stage-1 selection on contiguous spatial super-regions.
- **Stage 1, HOLDOUT-DTI:** evaluator `gems53.core.dti` v1.0.0 (parity with the shared template `src/metrics.py` verified to absolute difference 1.32e-13); 60,988 withheld catalogue positives in 3,199 segments; five folds; 95% t intervals with df 4. The design-B baseline bands top-q 0.02 is 0.010562 (CI 0.008337–0.012812). H1 + binary thinning q=0.10 was selected among 24 variants: 0.141319 (CI 0.133780–0.148921), an optimistic selection-stage number.
- **Stage 2, spatial HOLDOUT-DTI:** pooled baseline 0.000102 versus selected H1 + M1 0.004049. The preregistered primary statistic is the paired mean fold difference +0.003533, 95% t CI +0.000619 to +0.006447 (df 4); 60,988 withheld positives across 3,199 segments. The lower bound is above zero, so the rule accepts the candidate on this catalogue proxy. The small absolute score does not establish performance on new, uncatalogued faults.
- **Leakage canary (not DTI):** on design B, each of the 19 label-free bands was screened individually; maximum separability was 0.5912 (band 7). H1 alone was 0.7680. Both are below the 0.90 trigger. This screens direct label leakage but does not rule out spatial bias or a non-fault confounder.

### Shared-tool and provenance limits

The final GeoTIFF was written with the shared template writer and checked with both shared validators. The experiment feature/evaluator helpers remain in `src/gems53/core.py`; parity with the template metric is tested, but the requested `evaluate_holdout.py` / `submission_writer.py` names are absent from the pinned template (IR-53-39). Therefore do not describe the entire holdout implementation as a shared-template evaluator. The source rasters came from the hash-pinned GitHub mirror (S7), not an independently downloaded DrivenData package; equality, licence and provenance against the login-gated official copy remain unverified (L-06, L-13).

## GEMSDOE32 0.2778 and prior H2 evidence

The S2 public leaderboard snapshot fetched on 2026-10-08 lists `extradr19` at 0.2778 (#13), while the available GEMSDOE32 source does not link that row to H33-2-B2. The owner page marks its candidate UNSCORED; the owner's 0.2708 base is an OWNER-CLAIM, not a submission receipt. The measured registry-copy structure—37,654 dots, 0.0% within 2 px of known faults, and median nearest-dot spacing of 3 px—is consistent with metric-aware pruning/packing. The GEMS distance-weighted Tversky metric gives each local target a max-style credit while predicted area contributes false-positive cost, so spacing can reduce redundant false-positive mass while retaining distinct nearby credit. That is a plausible mechanism, not a verified explanation for the leaderboard row; the row-to-file link is unresolved (IR-53-02).

The separate H2 X2 run reported design-A HOLDOUT-DTI (shared template `src/metrics.py`, commit `dcbbb19`; 60,988 withheld positives in 3,199 segments; five folds; 95% t CIs, df 4): 0.050097 for 44,090 Poisson-packed ridge dots (CI 0.042504–0.057716), versus 0.026547 for same-budget HGB (CI 0.017965–0.035025) and 0.035233 for the frozen 103,348-dot baseline (CI 0.028170–0.042229). **Those values and CIs are not valid evidence that H2 beat the holdout best:** X2 used design-A negatives that exclude a buffer derived from withheld fault locations. They are retained only as a historical diagnostic (IR-53-37; `evidence/x2_ridge_holdout.json`). X2 was not rerun under design B. The H2 X3 GeoTIFF independently fails its uniqueness gate and is labelled DO-NOT-SUBMIT.

## Candidate uniqueness and submission status

The H1/M1 file named in `docs/submissions/CURRENT.json` is format-conformant, but the canonical full registry receipt compares it with 621 unique rasters and flags 103. Under the literal protocol, 99.599% of final dots are within 3 px of the GEMSDOE13 `r13-lattice-s5_v2` raster (threshold 70%). Its chance coverage is 99.87%, giving lift 0.9973; this is a **protocol duplicate / stop**, not evidence of byte-identical pixels. The pre-placement whole-grid surface-rho maximum is 0.953943 (threshold 0.90); footprint-only results and dense-raster confounding are separately documented in IR-53-47/48. The three-raster refresh is not a clearance (IR-53-49).

The file is **RESEARCH-ONLY / DO NOT SUBMIT**. It may be downloaded for research, but it must not be uploaded. No submission slot was used and no ORGANIZER-CONFIRMED score exists. The 135-character note and the updated TIFF metadata are recorded in the current pointer; the metadata-only note edit did not change pixel bytes/hash.

## Final decision and next steps

**Verdict: negative for promotion.** H1/M1 passed the pre-registered design-B spatial holdout acceptance rule and the feature canary, but it failed the user-specified raw registry duplicate gate. No experiment was run during this review because E1/E2/E3 already consume the three-experiment budget. The holdout is catalogue-based, not an estimate of performance on new faults.

The three ranked future hypotheses are in [`docs/research/hypotheses.md`](research/hypotheses.md): C1 conductivity–magnetic cross-scale phase coherence (only candidate using the cached stack; moderate/low-confidence prior), C2 raw ComCat event planes, and C3 multi-date Landsat thermal residuals. C1 was not run; C2/C3 source reachability, coverage, and terms are unverified here. Before any next run: resolve the raw-gate definition through explicit approval; pre-register the candidate; use design-B hidden-label-independent sampling; run each-feature canaries; test the best candidate on spatial blocks against the frozen baseline; then check novelty on the surface and final dots. Do not spend a slot unless all gates pass and the holdout beats the current valid holdout best.

## Sources for manual review

| Claim | Source | Evidence class |
|---|---|---|
| Competition labels are new faults absent from the known catalogue; metric and TIFF contract. | [DrivenData problem description (S1)](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Official competition source, fetched |
| Leakage definition / learn–predict separation. | [ACM TKDD 2012 article (S11)](https://doi.org/10.1145/2382577.2382579) | Primary research source, fetched; the separately cited KDD 2011 version remains unverified (IR-53-12) |
| The full-label feature path and upstream cross-fit implementation. | [GEMSDOE29 artifact builder and feature code (S8)](https://github.com/buffedlizard55-lab/GEMSDOE29) | Read-only code inspection; owner-reported result separated from source facts |
| The 0.2778 leaderboard entry and the unresolved file attribution. | [Public leaderboard snapshot (S2)](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) · [GEMSDOE32 site (S10)](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) | Public snapshot and owner page; no receipt links the row to H33-2-B2 |
| Metric-aware packing and the H2 X2 diagnostic values. | [Pinned template metric (S25)](https://github.com/buffedlizard55-lab/GEMSDOE/tree/dcbbb192e56b2b32c0a131eba791dc363305d4a3/src/metrics.py) · `evidence/x2_ridge_holdout.json` | Template source plus measured X2 receipt; design-A result invalid for promotion |
| Concealed faults interpreted from aeromagnetic lineaments. | [USGS Open-File Report 2009-1156 (S31)](https://www.usgs.gov/publications/high-resolution-aeromagnetic-survey-image-shallow-faults-poncha-springs-and-vicinity) | Official USGS analogue from Colorado; not local GEMS validation |
| Resistivity and magnetic-susceptibility signatures of fault-controlled hydrothermal conduits. | [USGS Publications Warehouse, Finn et al. 2022 (S32)](https://pubs.usgs.gov/publication/70230158) | Official USGS abstract / Yellowstone analogue; not local GEMS validation |
| Candidate seismic and thermal-data sources for future work. | [USGS ComCat FDSN (S29)](https://earthquake.usgs.gov/fdsnws/event/1/) · [Landsat Collection 2 Level-2 (S30)](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products) | Official source links; not fetched, and access/licensing/coverage remain unchecked in this environment |

## Review passes

- **Pass 1 — source diagnosis:** inspected GEMSDOE29's feature and builder paths; separated legitimate prediction-time catalogue context from label-derived training features; checked the archived arithmetic and source claims.
- **Pass 2 — holdout audit:** identified the design-A withheld-buffer side channel; confirmed the corrected E2 design B result, per-feature canaries, evaluator parity, and the separate H2 X2 design-A limitation.
- **Pass 3 — release/uniqueness QA:** regenerated run card and site; verified JSON, shared-template format validators, 30 automated tests, current pointer/file hashes and note, full registry gate; confirmed download-only / no-submit status.

## S3-A reproduction (2026-10-08, no selection)

Source: `scripts/s3a_leakage_repro.py`, receipt `evidence/s3a_leakage_repro.json`. Label: CANARY SENSITIVITY (not HOLDOUT-DTI, not organizer-scored). Pre-registration S3 section 5.

- The GEMSDOE29 construction, reproduced: D_leaky = log1p(min(distance to the FULL catalogue, 60)), positives = the full catalogue.
- On the training positives, D_leaky is 0 on 100% of pixels (defect confirmed).
- Single-feature separability on the design-B fold 0 canary: **1.0** (AUC 0.0). The canary flags it: `canary_detects_leaky_feature = true`.
- The legitimate H1 distance (visible faults only) on the same fold: separability **0.768** (E2 reference 0.768). It passes the 0.90 gate.
- Conclusion: the leaky construction is caught by the canary. Any model that uses it would be flagged LEAK_SUSPECT. The GEMSDOE29 distance feature must not be used as a training input.
