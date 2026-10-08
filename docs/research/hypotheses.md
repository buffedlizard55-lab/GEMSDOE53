# Hypotheses (updated 2026-10-08, after E1 and E2)

Ranking = judgement of expected DTI gain divided by cost. **Nothing here is a score.** Every holdout number is
HOLDOUT-DTI (proxy) and comes from `evidence/`. Layers are named as in `evidence/exp1_leakage_canary.json` (19 bands)
or as an external layer with its pinned source.

| Rank | ID | Hypothesis (one line) | Status | Expected gain (judgement) | Cost (judgement) |
|---|---|---|---|---|---|
| 1 | **H1** + **M1** | Segment-exact learn-predict distance (H1), with metric-aware thinning of the emission (M1) | **tested, design B** (`evidence/e2_leakfree_holdouts.json`) | measured on the proxy (see section H1) | low (done) |
| 2 | H5 | Off-catalogue thermal and paleo-geothermal evidence (INGENIOUS 2 m temperature probes, paleo-geothermal deposits, wells and springs) as independent features | **not tested** (budget); data present in a pinned mirror | unknown; plausibly high because it is not catalogue-derived | medium (five layers, geo-referencing, licence check) |
| 3 | H2 | Magnetic lineament ridges (Hessian) on the reduced-to-pole field (band 2) and the native GeoDAWN grid | **not tested** (budget); native grids present in the mirror | moderate, uncertain | medium |
| 4 | H6 | Regional trend prior: dominant orientation of visible faults as a feature (catalogue-derived, not proximity) | **not tested** (budget) | small to moderate | low |
| 5 | H3 | Fault-parallel strain from bands 7 and 8 | **BLOCKED**: the public strain data are scalars only (IR-53-22) | none until the tensor is found | high |
| - | H4 | USGS Quaternary Fault and Fold Database as an extra label source | **rejected**: the rules name these maps as a label source (S1, "Labels"), so they re-express the catalogue | none | low |

## H1 - segment-exact learn-predict separation (tested)

- **Layers:** known-fault raster `labels.tif` (8-connected segments, 60,988 px) and the 19 label-free bands.
- **Signature targeted:** proximity to other mapped structures (parallel or en-echelon faults).
- **Off-catalogue rationale:** a pixel near a visible fault but not on it is a candidate for an unmapped neighbour.
  The feature never uses the pixel's own label, and each training positive sees the same kind of feature a withheld fault
  would see at prediction time (its own segment is excluded).
- **Difference from the repo:** the earlier 4x4-block cross-fit (`crossfit_distance_grid`) removed every visible fault in the
  same ~41 km block, so its feature was weak (separability 0.52, IR-53-09). H1 removes only the pixel's own segment.
- **Result (design B, HOLDOUT-DTI):** see `evidence/e2_leakfree_holdouts.json`, `segment_folds.variants` and
  `spatial_confirmation`. Stage 1 selects among 24 variants on segment folds; stage 2 confirms the selection on spatially
  contiguous super-regions with a paired t-interval (df 4). **The label of the candidate follows that rule and only that rule.**
- **Caveat that stays in every H1 claim:** the holdout truth is the catalogue, and the H1 feature is proximity to the catalogue
  (single-feature separability 0.77 under design B, fold 0). The competition scores faults that are absent from the catalogue
  (IR-53-24). The holdout gain is therefore an upper bound for new-fault performance, not an estimate of it.

## M1 - metric-aware thinning (tested as part of the variants)

- **Layers:** the probability surface of the chosen arm (no new layer).
- **Mechanism (from the metric, S1):** TP credit is a max over the 3 px neighbourhood, FP credit is a sum over area, so a thin
  dominating set keeps TP and removes FP mass. `src/submission_optim.py` in the shared template states the same argument and
  measured a similar effect on a smoke model. This session measured it on our holdout (design B, see E2 tables).
- **Structure seen in the registry:** GEMSDOE32 H33-2-B2 has its dots spaced about the metric radius apart (median
  nearest-dot distance 3.0 px, measured in `evidence/gemsdoe32_measured.json`). That is the same structure M1 produces. It
  does not show the file's score (IR-53-02).

## H5 - off-catalogue thermal and paleo-geothermal evidence (not tested)

- **Layers (external, pinned mirror, commit 56d78de7, S20):**
  - `2m_temperature_probe_INGENIOUS_regional_data` (shallow 2 m temperature probes, NAD83 UTM 11N, with T2m, T1m and T15m; S22);
  - `paleo_geothermal_regional/Paleo_geothermal_final.csv` (paleo-geothermal deposits, e.g. travertine, with coordinates);
  - `wellspringdata.gdb` (wells and springs geodatabase; ESRI format, not parsed here).
- **Signature:** shallow thermal anomalies and travertine or silica deposits line up with permeable fault zones. Those zones are the
  geothermal targets, and they are not the catalogue.
- **Off-catalogue rationale:** the evidence is a measurement, not a fault trace. A deposit on an unmapped structure is a direct
  observation of that structure.
- **Difference from the repo:** none of these layers is in the 19-band stack.
- **Cost and risk:** five layers to geo-reference to the 100 m grid, a licence check (IR-53-26), and a holdout run. The
  sandbox can reach the mirror but not USGS, ScienceBase or GDR directly.
- **Why not run now:** the three-experiment budget is used (E1, E2, E3). It is the first item for the next session.

## H2 - magnetic lineament ridges (not tested)

- **Layers:** reduced-to-pole magnetics (band 2) and total magnetic intensity (band 14); native GeoDAWN grids for area 1
  and area 2 (`GeoDAWN_tiffs/22103_area*_tiffs/22103_rtp_*.tif`, pinned mirror S20) if a finer grid is wanted.
- **Signature:** linear magnetic breaks and ridges at 1 to 3 km scales, typical of buried or covered faults.
- **Off-catalogue rationale:** covered basins have few mapped faults, but magnetic breaks show them.
- **Difference from the repo:** the stack has gradient and tilt bands (3, 6, 9) but no ridge or lineament extraction.
  Band canaries under design B put the strongest label-free band at separability 0.59 (band 7, geodetic shear rate; fold maximum, `evidence/e2_leakfree_holdouts.json`, `canary_design_B`). That is below the 0.90 gate, but it is not weak.

## H6 - regional trend prior (not tested)

- **Layers:** the visible known-fault raster only (no new data).
- **Signature:** new faults in a strike-slip province often run sub-parallel to the regional trend (for example NW-SE in the Walker Lane,
  a geological expectation to be checked, not assumed).
- **Off-catalogue rationale:** the prior is a regional orientation, not the location of any catalogue fault.
- **Cost:** low. It can be tested on the segment folds in about 20 minutes. Its gain is expected to be small to moderate.

## H3 - fault-parallel strain (BLOCKED, IR-53-22)

- The stack carries three strain scalars: the second invariant (band 4), the shear rate (band 7) and the dilatation rate
  (band 8). The mirrored NBMG CSV has the same three scalars and no principal orientation
  (`geodetics_INGENIOUS_regional_data/geodetic_strain_rate_csv.csv`, columns read on 2026-10-08).
- A fault-parallel test needs the tensor or the principal azimuths. Those are not in the public mirror, and the sandbox cannot reach the NBMG or GDR sources.

## H4 - rejected

- USGS Quaternary Fault and Fold Database as an extra label source: the rules name the USGS quaternary maps as a label source,
  so using them re-expresses the catalogue (S1, "Labels").

## Sources checked for each hypothesis

- Layer list: `evidence/exp1_leakage_canary.json` (band names), `data/bridge/manifest.json` in the template (`S19`).
- Mirror contents and commit: `S20` (`jklinck/geothermal_research@56d78de7`), read through the GitHub API on 2026-10-08.
- Rules and metric: S1 (problem page) and S3 (NLR rules PDF), as recorded in `registry/sources.json`.
- No hypothesis has an organiser score. None is ORGANIZER-CONFIRMED.
