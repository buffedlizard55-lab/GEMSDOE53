# Hypotheses, ranked (2026-10-08)

Ranking = expected DTI gain (judgement, **not a score**) divided by cost. Holdout numbers come only from `evidence/`
and are labelled **HOLDOUT-DTI** (proxy: withheld catalogue segments, shared template evaluator, 95% t-CI, df 4).
Nothing on this page is an organizer score.

| Rank | ID | One line | Status | Evidence |
|---|---|---|---|---|
| 1 | **H2** | Band-2 (RTP) multi-scale ridge/valley centrelines, Poisson-packed at 2.8 px, 44,090 binary dots | **Tested on holdout: passes G1, G2, G3, G4. Blocked at G5: dot-level flags are density artefacts, but the surface shares its top tail with two team files (lift 3.6 and 5.6). DO-NOT-SUBMIT.** | `evidence/x2_ridge_holdout.json`, `evidence/x3_candidate_receipt.json`, `evidence/uniqueness_v2.json` |
| 2 | H5 | Apply the same Poisson packing to the 19-band HGB probability surface (method hypothesis, not geology) | not run (experiment budget spent) | mechanism measured in X2 (below) |
| 3 | H3 | Fault-parallel strain: orientation of shear (band 7) and dilatation (band 8) as extensional-lineament features | not run | band list in `training_features.tif` |
| 4 | H6 | Radiometric alteration lineaments (K, Th, U ratios): hydrothermally altered fault zones | **data-blocked** (IR-53-30); no radiometric channel in the 19-band stack | band list; sandbox allow-list |
| 5 | H1 | Segment-exact learn-predict separation: distance to visible faults, excluding only the pixel's own segment | **validated in another session (PR #6): HOLDOUT-DTI 0.0560, its own uniqueness check; cross-check here is NOT CLEARED under the literal dot rule (60 lattice-family rows, lift ≤ 1.31).** Its file is on main (`docs/downloads/`). Not re-validated here. | `docs/archive/pr6/`, `evidence/crosscheck_pr6_h1_uniqueness_v2.json` |
| - | H4 (rejected) | USGS Quaternary fault database as an extra label source | rejected: it re-expresses the catalogue (S1, "Labels") | prior session |

## H2 - tested (rank 1)

- **Layers:** RTP magnetic anomaly only (GeoDAWN band 2). No label is read by the score.
- **Signature:** linear magnetic discontinuities. Bright ridges (dykes, magnetite-rich contacts) and dark valleys
  (demagnetised, hydrothermally altered fault zones). Scales 1.5, 2.5 and 3.5 px (150-350 m), a 1.5 km detrend.
- **Emission:** NMS centrelines, then greedy Poisson-disk packing at 2.8 px (the d2.8 family spacing), 44,090 dots,
  binary. Visible faults are masked pixel-exactly; all no-data RTP cells are excluded.
- **Pre-registered gates** (`evidence/preregistration_x2.json`, written before the run):
  - G1: pooled HOLDOUT-DTI at 44,090 dots > 0.035233 (the repo's frozen best). **Result: 0.050097 (PASS).**
  - G2: paired per-fold difference vs the same-budget HGB baseline, 95% t-CI lower bound > 0. **Result:
    +0.023615 (CI 0.016962 to 0.030269), PASS.**
  - G3: leakage canary, every ridge feature alone <= 0.90. **Result: worst 0.559399 (PASS).**
  - G4: format, through the template's writer and validators. **PASS** (all three validator exit codes 0).
  - G5: uniqueness. **FAIL** (see below).
- **Mechanism (MEASURED, X2):** at the same budget, packing roughly doubles the credit per dot. At 44,090 dots,
  pooled TP_w is 4,678 for the packed arm versus 2,072 for the unpacked top-N arm and 1,999 for HGB. FP_w is almost
  the same for both (about 218k). The spacing rule, not the feature alone, does most of the work. The ridge
  feature on its own is weak (X1 separability 0.56).
- **Why G5 fails (MEASURED; diagnostic, not an experiment):** 66 registry rows exceed 70% at the dot level, all with
  chance lift ≤ 1.35, so they are density artefacts (the worst is the 5-px lattice raster, lift 1.00). Sixteen rows
  exceed 70% at the surface level, and those lifts are real: GEMSDOE46 dfa-corroborated (72.9% against 20.1%
  chance, lift 3.6) and GEMSDOE40 eulerdepth-si0 (70.5% against 12.6%, lift 5.6). Our signal is therefore not
  untried at its strongest structures (IR-53-34). A chance-corrected dot rule would not clear the file.
- **Caveats:** the holdout truth is the catalogue, not the competition's new faults (L-02). The surface similarity
  above means H2's signal is shared with other team files, so 'untried' does not hold for this signal. About half of the
  centrelines are valley-polarity, and some of these may be detrend side-lobes (IR-53-29). Nothing has been
  tuned on the holdout.

## H5 - credit packing on the HGB surface (rank 2, not run)

- **Idea:** keep the 19-band HGB probability surface, but emit it as Poisson-packed dots instead of a top-N block.
- **Why:** X2 shows that packing alone roughly doubles the credit per dot on a ridge surface. The same effect may hold for
  any surface whose top-N is clustered.
- **Test:** one more arm on the same folds, with pre-registered gates. Cost is low (about 5 minutes). Expected gain:
  unknown; a holdout gain would not by itself show that the gain transfers to new faults (L-14).

## H3 - fault-parallel strain (rank 3, not run)

- **Layers:** geodetic shear rate (band 7) and dilatation rate (band 8); second invariant (band 4).
- **Signature:** orientation of extensional lineaments from the principal strain axes.
- **Cost:** medium. Caveat: band 7 is the strongest label-free band in E1 (separability 0.60), so part of any gain may just
  be strain magnitude.

## H6 - radiometric alteration lineaments (rank 4, data-blocked)

- **Idea:** potassium enrichment and thorium/uranium ratios in altered fault zones (a domain prior, not verified here).
- **Blocker:** the 19-band stack has no radiometric channel (band descriptions, read this session). The grids would
  come from USGS/ScienceBase, which is not on the sandbox allow-list (IR-53-30).

## H1 - segment-exact learn-predict separation (rank 5; validated in PR #6, not re-validated here)

- **Idea:** distance to visible faults, excluding only the pixel's own segment, so the leak-free feature is less
  weak than the 4x4-block cross-fit (separability 0.52, IR-53-09).
- **Cost:** low. Caveat: it is a feature idea, not an emission rule, and the holdout shows that label-based
  distance features leak unless learn-predict is separated (E2 `leaky_ablate` 0.999957).

## Sources

- Band list: `training_features.tif` band descriptions, read this session (see `evidence/x1_ridge_canary.json`).
- Metric and submission rules: S1 (problem page), S3 (rules PDF). Template evaluator and writer: S23.
- Owner context for the packed d2.8 family: S22 (owner analysis, unverified by an organizer receipt).
