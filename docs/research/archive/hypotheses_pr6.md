# Candidate hypotheses (generated before implementation, ranked)

Ranking = expected DTI improvement (geological & data-mining judgement, NOT an organizer score) divided by implementation cost.
Nothing here is an organizer score. Every number in the holdout columns comes from `evidence/exp2_holdout_arms.json`.

| Rank | ID | Hypothesis (one line) | Expected gain | Cost | Status |
|---|---|---|---|---|---|
| 1 | **H1** | Segment-exact learn-predict separation: distance to visible faults **excluding only the pixel's own fault segment** | High | Low (minutes) | **VALIDATED**: pooled HOLDOUT-DTI = 0.0560 (95% CI [0.0488, 0.0631]), +123% gain over `bands` baseline (0.0251) with non-overlapping CI |
| 2 | H2 | Multi-physics structural corroboration: joint coincidence of active geodetic strain (bands 4, 7), potential-field basement steps (bands 3, 5, 6, 18), and Quaternary seismicity (bands 10, 16) | Moderate-High | Low-Medium | **IMPLEMENTED** in candidate emission selection |
| 3 | H3 | Andersonian fault-tip extension & dilatational relay-ramp jog prior: targeting step-over corridors (200 m to 2.5 km off-fault) where unmapped geothermal fluid conduits breach | Moderate | Low | **IMPLEMENTED** via catalogue exclusion buffer ($B=2$ px) and step-over envelope |
| 4 | H4 | Magnetic lineament ridges: multi-scale ridge (Hessian) detector on the reduced-to-pole field (band 2) and TMI (band 14) | Moderate | Medium | Candidate for future iteration |
| - | H5 (rejected) | USGS Quaternary Fault and Fold Database as an extra label source | none expected | low | **REJECTED**: competition rules cite the USGS quaternary fault maps as a label source (S1 "Labels"), so it re-expresses the training catalogue |

## H1 - segment-exact learn-predict separation (rank 1, VALIDATED)
- **Layers:** known-fault raster (`labels.tif`, 3,199 eight-connected segments, 60,988 px), `training_features.tif`.
- **Signature targeted:** proximity to *other* mapped structures. In extensional tectonic provinces (Basin and Range), new faults form en-echelon systems sub-parallel to master range-front faults.
- **Why it catches missing faults:** a pixel near a mapped fault but not on it is a candidate for an unmapped neighbour. The feature never uses the pixel's own connected segment.
- **Difference from earlier repo code:** Exp 1/2 previously used a 4×4-block cross-fit (`crossfit_distance_grid`). That removed every visible fault in the same ~41 km block, destroying local spatial correlation (separability only 0.52). H1 excludes *only* the pixel's own connected segment.
- **Validation outcome:**
  - Evaluated on the 5-fold whole-segment holdout set across all folds.
  - At $q = 0.0073$ (37,654 dots), pooled HOLDOUT-DTI jumped from **0.025063** (`bands` baseline) to **0.055957** (`h1_segment_exact`), an improvement of **+123.3%**.
  - The 95% confidence intervals do not overlap: `bands` is $[0.0162, 0.0338]$, while `h1_segment_exact` is $[0.0488, 0.0631]$.
  - Separability on the leakage canary is $0.7746 < 0.90$ (passes gate; no target shortcut).

## H2 - multi-physics structural corroboration (rank 2, IMPLEMENTED)
- **Layers:** Band 4 (Geodetic 2nd invariant), Band 7 (Shear rate), Band 3 (Magnetic gradient), Band 5 (Gravity slope), Band 6 (Magnetic tilt/curvature), Bands 10 & 16 (Quaternary microseismicity).
- **Signature:** Blind hydrothermal circulation systems require active tectonic shear strain (to prevent hydrothermal quartz/calcite self-sealing) coupled with deep basement discontinuities (gravity/magnetic steps).
- **Why off-catalogue:** Concealed geothermal blind systems frequently lack surface scarps (covered by playa alluvium or pluvial Lake Lahontan sediments), rendering them absent from optical/topographic catalogues but detectable in potential fields and geodetic strain.
- **Difference from previous code:** Incorporates physical multi-layer coincidence rather than treating features as arbitrary tabular columns.

## H3 - Andersonian fault-tip extension & relay-ramp prior (rank 3, IMPLEMENTED)
- **Layers:** `labels.tif`, Band 7 (shear rate), Band 8 (dilatation rate).
- **Signature:** Dilatational step-overs and stress concentrations between overlapping normal fault tips.
- **Why off-catalogue:** Over 80% of known Great Basin commercial geothermal fields occur in structural step-overs, terminations, or intersections (Faulds & Hinz, 2015; INGENIOUS project).
- **Implementation:** Catalogue exclusion buffer ($B=2$ px / 200 m) eliminates guaranteed false positives, while prioritizing candidate lineaments within the 200 m to 2.5 km step-over damage zone.
