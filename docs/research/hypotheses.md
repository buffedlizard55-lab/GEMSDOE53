# Candidate hypotheses (generated before implementation, ranked)

Ranking = expected DTI improvement (judgement, NOT a score) divided by implementation cost.
Nothing here is a score. Every number in the holdout columns comes from `evidence/`.

Sessions: H1–H4 were ranked in session 2 (2026-10-08, PR #3). H5–H9 are the new candidates ranked in
session 3 (2026-10-08, this PR), after the E6 finding that the emission rule (value scaling × volume)
matters more than the model family, and that the model's placement AUC on withheld faults is 0.74–0.78.

| Rank | ID | Hypothesis (one line) | Expected gain | Cost | Status |
|---|---|---|---|---|---|
| 1 | **H1** | Segment-exact learn-predict separation: distance to visible faults **excluding only the pixel's own fault segment** | none (leak) | low | **REJECTED (Exp 4)**: paired pixel-neighbour canary AUC 1.000; the feature encodes the label by construction. Never use. |
| 2 | H2 | Magnetic lineament map: multi-scale ridge (Hessian) detector on the reduced-to-pole field (band 2), used as a feature | none measurable | medium | **NEGATIVE (Exp 4 canary passes; Exp 5 holdout: paired ridge-minus-bands at q=0.02 = -0.00005, 95% CI [-0.00404, +0.00394])** |
| 3 | H3 | Fault-parallel strain: principal orientation of shear (band 7) and dilatation (band 8), used as an extensional-lineament feature | small to moderate | medium | not implemented (superseded by H5/H8 below; budget) |
| - | H4 (rejected) | USGS Quaternary Fault and Fold Database as an extra label source | none expected | low | **rejected**: the rules name the USGS quaternary fault maps as a label source (S1 "Labels"), so it re-expresses the catalogue |
| **1 (session 3)** | **H5** | **Basement/conductivity edges: multi-scale scale-normalised gradient magnitude on depth-to-basement (band 15) and surface conductivity (band 17)** | small to moderate | low | **RUN (E7)**: see `evidence/exp7_h5_canary_holdout.json` |
| 2 (session 3) | H6 | Elevation curvature: profile/plan curvature of detrended elevation (band 12) as a scarp-and-valley detector | small | low | not run (budget) |
| 3 (session 3) | H7 | Radiometric alteration index: K/eTh (and K/eU) ratios from the USGS GeoDAWN radiometric grids — potassic (K-feldspar) hydrothermal alteration halos along unmapped fault conduits | potentially large | **high** (external data) | **viable but not implemented**: source verified obtainable (S15/S20, CC0), ingestion + reprojection to the 100 m grid not done in this budget |
| 4 (session 3) | H8 | Strain–topography coherence: orientation agreement between the geodetic strain axes (bands 7/8) and the topographic grain (band 19) — the H3 mechanism made orientation-explicit | small to moderate | medium | not run (budget) |
| 5 (session 3) | H9 | Seismicity–structure interaction: earthquake density (band 16) and distance (band 10) modulated by basement edges (H5) | small | low | not run (budget) |

## Session-2 status (Experiments 4–5, 2026-10-08)
- H1 is rejected by its own design, before any holdout run. The exclusion is asymmetric: a positive pixel's own segment is removed and a negative's is not, so the feature encodes the label pixel-exactly (paired canary AUC 1.000). This is the GEMSDOE29 mechanism in a different form.
- H2 passes the leakage canary (it has no label path) but gives no measurable holdout gain. Pre-registered acceptance is not met.
- H3 (fault-parallel strain) is not run; the session budget was 3 experiments and 2 were used.
- The 4x4 block cross-fit (the leak-free arm of Exp 2) passes the exhaustive pixel-neighbour check (170,638 pairs, AUC 0.4995).

## Session-3 status (Experiments 6–8, 2026-10-08)
- **E6 (emission-rule sweep, HOLDOUT-DTI):** on the same 5 folds (same training draws as Exp 2; the raw variant reproduces the Exp-2 bands arm exactly), the model's placement AUC on withheld faults is 0.742–0.781 (mean 0.772). Rescaling the emission to binary value-1.0 dots and widening the volume to q=0.05 raises pooled HOLDOUT-DTI from 0.0352 (raw @ 0.02, the Exp-2 recipe) to **0.0484 (bin @ 0.05, 95% CI [0.0421, 0.0548])**. Binary dots beat rank-rescaling and sqrt at every q; the optimum q is 0.05 (0.0484), with 0.10 close (0.0441). Credit per dot at the optimum (0.00995) sits just above the break-even bar 0.2·DTI (0.00855) — the same break-even the GEMSDOE32 analysis derives. See `evidence/exp6_emission_scaling.json`.
- **E7 (H5 canary + paired holdout):** both H5 features pass the leakage canary (separability max 0.573/0.515; paired pixel-neighbour AUC 0.500/0.503 — no label path). On the holdout with the E6 emission rule (bin), the paired H5−bands difference at the bands-best q=0.05 is **−0.00016 (95% CI [−0.00206, +0.00174])**; the pre-registered acceptance (gain beyond the fold-level 95% half-width 0.0019) is **not met**, so H5 is negative and the `bands` arm is kept (`evidence/exp7_h5_canary_holdout.json`).
- **E8 (build + gates + publish):** the unique submission `gems53-hgb-bands-bin-q0p0073` (bands arm, binary dots, q=0.0073) was built, passed the in-lane validator and the shared template validator, passed the operative uniqueness gate (mutual-overlap test, validated against the known duplicate), and is published at `docs/downloads/`. Volume selection under the release gates: q=0.02 reproduces the known duplicate (17GEMSDOE F-ensemble-2pct, mutual 0.758/0.825), q=0.05 and q=0.10 are mutual near-copies of existing same-volume submissions (0.872/0.882 and 0.770/0.834) — the strongest lane-drift evidence; among the gate-passing volumes the top two by pooled HOLDOUT-DTI (q=0.01: 0.0379, q=0.0073: 0.0343) are statistically indistinguishable (overlapping 95% CIs), so the tie-break is the larger uniqueness margin: q=0.0073 (closest count-matched weaker-direction coverage 0.646) over q=0.01 (0.674). Status: `evidence/run_card.json`, `evidence/selection.json`, `evidence/uniqueness_volume_scan.json`.

## H5 - basement-depth and conductivity edges (session-3 rank 1)
- **Layers:** depth to basement surface / sedimentary cover thickness (band 15); surface conductivity (band 17). Both are label-free and already in the stack.
- **Signature targeted:** multi-scale scale-normalised gradient magnitude (an edge detector, σ = 100/200/300 m) of each layer. Basin-bounding and range-front faults juxtapose deep, conductive, saturated cover against shallow, resistive basement, so the *edges* of those two layers are sharp exactly where a fault has no surface trace.
- **Why it should catch a fault missing from the USGS/INGENIOUS catalogue:** the catalogue is compiled from surface fault maps (S1 "Labels": USGS quaternary fault maps + INGENIOUS). A fault buried under basin cover has no surface expression, so it is absent from the catalogue, but it still offsets the basement surface and the conductivity structure. Raw band 15 separates withheld faults only weakly (Exp 1 separability 0.532); its edge may be sharper than the field itself.
- **Named non-fault process that could mimic it:** depositional onlap edges (alluvial fans thinning onto bedrock), volcanic caldera rims, landslide scarps, and artefacts of the depth-to-basement inversion (the depth model is itself derived from gravity/magnetics, so part of its edge signal re-expresses bands 5/13/18).
- **How it differs from anything already implemented:** the stack carries the raw layers and the gradients of *gravity* (5, 11, 18) and *magnetics* (3, 9), but no gradient-magnitude (edge) transform of basement depth or conductivity; H2's ridge detector ran on magnetics only and was negative. E7 tests the two edges as added features, paired against the same model without them, same folds, same emission rule (bin @ the E6 q grid).
- **Cost:** low (two Gaussian-gradient filters at three scales; no new data).

## H6 - elevation curvature (session-3 rank 2)
- **Layers:** detrended elevation (band 12); its slope is band 19.
- **Signature:** profile and plan curvature at 100–300 m scales. Fault-aligned valleys and scarps are lines of high curvature; the stack has slope but no curvature.
- **Why off-catalogue:** covered or eroded fault traces still control drainage; curvature ridges follow them.
- **Non-fault mimic:** landslide headscarps, fluvial terraces, dunes, and lava-flow fronts.
- **Differs from the repo:** no curvature transform exists in the stack or in the implemented features. Registry precedent is weak (lidar-scarp submissions scored 0.146–0.159), so the expected gain is small.
- **Cost:** low.

## H7 - radiometric alteration index (session-3 rank 3; needs external data)
- **Layers needed:** airborne radiometric grids — potassium (K), equivalent thorium (eTh), equivalent uranium (eU), total counts — from the **USGS GeoDAWN data release**, DOI [10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ), CC0 1.0. **Not in the 19-band stack** (verified against the band descriptions in `training_features.tif` and the problem page's feature list, S1).
- **Signature:** K/eTh and K/eU ratio highs. Potassic (K-feldspar) alteration halos along fault-controlled geothermal conduits are the classic radiometric geothermal indicator; eTh-normalised K suppresses lithology and exposes the alteration.
- **Why off-catalogue:** alteration halos extend well beyond mapped fault traces and mark conduits that were never mapped as faults.
- **Non-fault mimic:** felsic intrusive contacts (K-rich granite), playa/lacustrine clay, and soil-moisture effects on the low-energy window.
- **Obtainability (checked 2026-10-08):** the USGS data page (S15) and the ScienceBase item (S20) confirm the release contains radiometric grids (binary .grd, geoTIFF images, and flight-line CSVs), public domain CC0 1.0, free download. **Viable.** Not implemented in this budget: ingestion, mosaicking of the four acquisition blocks, reprojection/resampling to the 100 m EPSG:32611 competition grid, and nodata reconciliation are a multi-hour task (L-15).
- **Cost:** high (external data pipeline).

## H8 - strain–topography coherence (session-3 rank 4)
- **Layers:** geodetic shear rate (band 7), dilatation (band 8), second invariant (band 4), detrended-elevation slope (band 19).
- **Signature:** orientation agreement between the principal strain axes and the topographic grain (structure-tensor orientation of the slope). This is the H3 mechanism (fault-parallel strain) made orientation-explicit instead of magnitude-only.
- **Why off-catalogue:** present-day geodetic strain localises on structures that are not yet mapped.
- **Non-fault mimic:** regional strain gradients unrelated to faults; topographic grain set by bedding, not structure.
- **Differs from the repo:** bands are used raw; no orientation/coherence product exists.
- **Cost:** medium.

## H9 - seismicity–structure interaction (session-3 rank 5)
- **Layers:** earthquake density (band 16), distance to earthquake (band 10), H5 basement/conductivity edges.
- **Signature:** earthquake density anomalously high *along* basement/conductivity edges — seismicity on unmapped fault segments.
- **Why off-catalogue:** small-magnitude seismicity on unmapped structures is exactly what a surface catalogue misses.
- **Non-fault mimic:** mainshock–aftershock sequences off-structure; catalog completeness artefacts.
- **Differs from the repo:** no interaction term exists; bands 10/16 are used raw (Exp 1 separability 0.574/0.594).
- **Cost:** low, but the expected gain is small (both source bands are smooth, 100 km-radius kernels).

## H1 - segment-exact learn-predict separation (session-2 rank 1) - REJECTED, see status above
- **Layers:** known-fault raster (`labels.tif`, 3,199 eight-connected segments, 60,988 px).
- **Signature targeted:** proximity to *other* mapped structures. New faults are often parallel or en-echelon to mapped ones.
- **Why it should catch a fault missing from the catalogue:** a pixel near a mapped fault but not on it is a candidate for an unmapped neighbour. The feature never uses the pixel's own label.
- **Difference from the repo now:** Exp 1/2 use a 4x4-block cross-fit (`crossfit_distance_grid`). That removes every visible fault in the same ~41 km block, so the leak-free feature is weak (separability 0.52, IR-53-09). H1 removes only the pixel's own segment.
- **Validation plan (pre-registered here):** add arm `segment_exact`; run the same 5-fold holdout; accept only if pooled DTI beats the `bands` arm at the same q by more than the fold-level 95% t-interval half-width, and the leaky arm is not used as a comparator.
- **Cost:** per-segment local EDT over bounding-box + 60 px windows (3,199 windows per fold). Estimated under 30 minutes of compute on 2 CPUs.

## H2 - magnetic lineament ridges (session-2 rank 2)
- **Layers:** reduced-to-pole magnetics (band 2); total magnetic intensity (band 14).
- **Signature:** linear magnetic breaks and ridges at 1-3 km scales (a Hessian/ridge filter), which are typical of buried or covered faults.
- **Why off-catalogue:** covered basins have few mapped faults, but magnetic breaks show them.
- **Difference from the repo now:** the stack already has gradient and tilt bands (3, 6, 9), but no ridge or lineament extraction. The label-free bands alone reach separability 0.60 at most (Exp 1).
- **Cost:** medium (filter design and a scale sweep). No new data.

## H3 - fault-parallel strain (session-2 rank 3)
- **Layers:** geodetic shear rate (band 7) and dilatation rate (band 8).
- **Signature:** the orientation of extensional lineaments from the principal strain axes.
- **Why off-catalogue:** geodetic strain reflects present-day deformation, which can occur on structures that are not yet mapped.
- **Difference from the repo now:** the bands are used raw. The orientation product is not in the stack.
- **Cost:** medium. Caveat: band 7 is the strongest label-free band in Exp 1 (separability 0.60), so part of any gain may just be strain magnitude.

## Sources checked for each hypothesis
- Layers and units: the band descriptions in the feature stack (`training_features.tif`, read in this session; reference notebook S5).
- Rules on label sources: S3 section 3.3 and S1 "Labels".
- External data (H7 only): USGS GeoDAWN data release, DOI 10.5066/P93LGLVQ (S15 page + S20 ScienceBase item, both fetched 2026-10-08; CC0 1.0; radiometric grids included). No other hypothesis needs new external data. If one is added later, its source must be listed in `registry/sources.json` with an official link and a fetch check first.
