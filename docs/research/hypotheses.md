# Candidate hypotheses (generated before implementation, ranked)

Ranking = expected DTI improvement (judgement, NOT a score) divided by implementation cost.
Nothing here is a score. Every number in the holdout columns comes from `evidence/`.

| Rank | ID | Hypothesis (one line) | Expected gain | Cost | Status |
|---|---|---|---|---|---|
| 1 | **H1** | Segment-exact learn-predict separation: distance to visible faults **excluding only the pixel's own fault segment** | small to moderate | low (hours) | **not yet implemented** - next experiment |
| 2 | H2 | Magnetic lineament map: multi-scale ridge (Hessian) detector on the reduced-to-pole field (band 2), used as a feature | moderate, uncertain | medium | not implemented |
| 3 | H3 | Fault-parallel strain: principal orientation of shear (band 7) and dilatation (band 8), used as an extensional-lineament feature | small to moderate | medium | not implemented |
| - | H4 (rejected) | USGS Quaternary Fault and Fold Database as an extra label source | none expected | low | **rejected**: the rules name the USGS quaternary fault maps as a label source (S1 "Labels"), so it re-expresses the catalogue |

## H1 - segment-exact learn-predict separation (rank 1)
- **Layers:** known-fault raster (`labels.tif`, 3,199 eight-connected segments, 60,988 px).
- **Signature targeted:** proximity to *other* mapped structures. New faults are often parallel or en-echelon to mapped ones.
- **Why it should catch a fault missing from the catalogue:** a pixel near a mapped fault but not on it is a candidate for an unmapped neighbour. The feature never uses the pixel's own label.
- **Difference from the repo now:** Exp 1/2 use a 4x4-block cross-fit (`crossfit_distance_grid`). That removes every visible fault in the same ~41 km block, so the leak-free feature is weak (separability 0.52, IR-53-09). H1 removes only the pixel's own segment.
- **Validation plan (pre-registered here):** add arm `segment_exact`; run the same 5-fold holdout; accept only if pooled DTI beats the `bands` arm at the same q by more than the fold-level 95% t-interval half-width, and the leaky arm is not used as a comparator.
- **Cost:** per-segment local EDT over bounding-box + 60 px windows (3,199 windows per fold). Estimated under 30 minutes of compute on 2 CPUs.

## H2 - magnetic lineament ridges (rank 2)
- **Layers:** reduced-to-pole magnetics (band 2); total magnetic intensity (band 14).
- **Signature:** linear magnetic breaks and ridges at 1-3 km scales (a Hessian/ridge filter), which are typical of buried or covered faults.
- **Why off-catalogue:** covered basins have few mapped faults, but magnetic breaks show them.
- **Difference from the repo now:** the stack already has gradient and tilt bands (3, 6, 9), but no ridge or lineament extraction. The label-free bands alone reach separability 0.60 at most (Exp 1).
- **Cost:** medium (filter design and a scale sweep). No new data.

## H3 - fault-parallel strain (rank 3)
- **Layers:** geodetic shear rate (band 7) and dilatation rate (band 8).
- **Signature:** the orientation of extensional lineaments from the principal strain axes.
- **Why off-catalogue:** geodetic strain reflects present-day deformation, which can occur on structures that are not yet mapped.
- **Difference from the repo now:** the bands are used raw. The orientation product is not in the stack.
- **Cost:** medium. Caveat: band 7 is the strongest label-free band in Exp 1 (separability 0.60), so part of any gain may just be strain magnitude.

## Sources checked for each hypothesis
- Layers and units: the band descriptions in the feature stack (`training_features.tif`, read in this session; reference notebook S5).
- Rules on label sources: S3 section 3.3 and S1 "Labels".
- No hypothesis here needs new external data. If one is added later, its source must be listed in `registry/sources.json` with an official link and a fetch check first.
