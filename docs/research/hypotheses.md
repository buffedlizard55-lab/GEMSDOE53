# Hypotheses and next-candidate screen (session-2 update 2026-10-09)

**Parallel-session pre-placement note (2026-10-09, kept for the record):** before session 2 ran, a pixel-verified public [GEMSDOE17 registry raster](https://github.com/buffedlizard55-lab/17GEMSDOE/blob/main/docs/downloads/17GEMSDOE_E-proba-multiscale_20260930T044527Z.tif) was shown to be positive on all 5,167,373 sample-footprint pixels (`evidence/protocol_preflight_20261009.json`), so ANY nonempty dot map necessarily overlaps that dense raster at 100% under the literal 70% rule (IR-53-46/50). Session 2 then implemented and validated C1 anyway (below): the corrected GD-1 gate (IR-53-73) neutralizes the dense-raster confound via chance correction (lift ~ 1 against dense rasters), and the candidate was flagged instead by 25 SPARSE dot maps with lift 1.5–4.2 — convergent fault geography, not method drift (IR-53-76). C2 and C3 still need official data availability/rights checks. No submission slot was spent.



## Session-2 screen (2026-10-09): five candidates, top candidate C1 in validation

Pre-registration: [`preregistration-2026-10-09-session2.md`](preregistration-2026-10-09-session2.md) section 6. Ranks are qualitative expected-value-per-cost judgements, not DTI projections. Every number produced this session is labelled HOLDOUT-DTI in `evidence/s2_c1_holdout.json`; none is ORGANIZER-CONFIRMED.

| Rank | ID | Layers involved | Physical signature (transform) | Why it could catch a fault MISSING from the USGS/INGENIOUS catalogue | Difference from anything implemented here or in the portfolio screen | Expected DTI improvement / cost |
|---|---|---|---|---|---|---|
| 1 | **C1** conductivity–magnetic cross-scale edge coherence | band 17 `cond_surf` + band 2 `rtp` (cached stack) | multi-scale structure-tensor line energy + energy-gated orientation agreement (σ = 1,2,4 px; DEV-C1-1) | covered/buried faults offset magnetic basement and host conductive damage zones; no surface trace exists for compilers to map | no cross-physics coherence transform in this repo or the 19-band stack; distinct from H1 (catalogue distance) and H2 (single-band ridges). USGS analogues S31/S32 are from other regions | moderate / LOW cost — validated this session on the design-B holdout (only candidate runnable from cached data) |
| 2 | **C5** strain-budget residual | bands 4/7/8 (strain invariants) conditioned on visible-catalogue density | residual = observed strain − E[strain | catalogue density], fitted on visible data only (learn-predict separated) | high geodetic strain where the catalogue has no faults is slip deficit on unmapped ACTIVE structures — a direct measurement, not a mapping inference | bands were used raw as model inputs before, but never as a catalogue-conditioned residual; named mimic: interpolation smoothing of the strain-rate field | moderate / low cost (cached stack) |
| 3 | **C4** gravity–basement collinearity | bands 13/11/18 (isostatic gravity + gradients) + band 15 (depth to basement) | directional collinearity of gravity-gradient vectors with basement-depth steps across scales | basement-involved faults under valley fill produce density/basement steps invisible at the surface | no joint gravity–basement collinearity detector in the repo; portfolio "structural-area" candidates are single-field; named mimic: regional isostatic flexure trends | moderate / medium cost (cached stack) |
| 4 | **C7** seismic–conductive concurrence | band 16 (earthquake density) × band 17 (conductivity) | rank-concurrence with local permutation significance | actively deforming AND fluid-filled structures may be unmapped; concurrence suppresses each field's independent false alarms | no product/concurrence layer in the stack; portfolio "seisgeom-ridgesnap" exists, so only this specific transform is candidate-new; named mimic: catalogue-driven event-location bias | low-moderate / low cost (cached stack, sparse coverage risk) |
| 5 | **C2/C3** raw ComCat event planes / Landsat thermal residuals (carried) | external USGS sources | 3-D hypocentral planes; persistent multi-date thermal residuals | direct activity/upflow observations independent of mapping | not in the stack | potential but **NOT viable in this environment**: official sources [USGS ANSS ComCat FDSN](https://earthquake.usgs.gov/fdsnws/event/1/) and [USGS Landsat C2 L2](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products) are outside the egress allow-list; access, coverage and licence unchecked (L-32) |

**Validation rule for the top candidate (C1):** per-feature leakage canary ≥ gate 0.90; design-B segment-fold holdout vs the same-run bands baseline; spatial-block confirmation (paired 95% t CI, accept iff lower bound > 0); GD-1 uniqueness gate on surface and final dots — all before any submission slot is touched (this is exactly the standing prompt's requirement).

---

# Historical screen (reviewed 2026-10-08)

**No experiment was run during that review.** Ranks are qualitative expected-value-per-cost judgements (expected catalogue-proxy gain balanced against data and validation cost), not DTI projections or scores. Candidate HOLDOUT-DTI values and organizer scores are reported only when measured/receipted in the evidence files.

## What has already been tried (do not describe as new)

- **H1 + M1** (catalogue distance with learn-predict separation; thinning) was tested in E1/E2. Its selection-stage result is optimistic because it selected among variants. Stage-2 spatial confirmation is reported in `evidence/e2_leakfree_holdouts.json`; the holdout truth is still the known-fault catalogue, not the competition's unmapped-fault target (IR-53-42).
- **H2** (band-2 magnetic Hessian ridges with Poisson packing) is implemented in `src/gems53/ridge.py` and was attempted in X1/X2/X3 (`scripts/x1_ridge_canary.py`, `scripts/x2_ridge_holdout.py`, `scripts/x3_build_candidate.py`). X2 used the invalid design-A negative pool that depends on withheld faults (IR-53-37); its apparent HOLDOUT-DTI gain is not valid holdout confirmation, and no design-B rerun was made because the experiment budget is exhausted. H2 is not untried, but it is not cleanly validated.
- **H5** (thermal/paleo-geothermal corroboration) and **H7** (strike/trend priors) have close portfolio analogues in the registered GEMSDOE raster inventory: thermal-pop/geothermal-pinning/geothermometer/btherm candidates (GEMSDOE19, 30, 36, 47, 52) and strike/local-strike/strike-coherence/continuation candidates (7, 41, 48, 52). Those names are a screening signal, not a full source-code audit. Do not claim either broad family is unique.
- **H3** (strain orientation) remains blocked because the available strain channels are scalar quantities, not a strain tensor or principal azimuths (IR-53-40). **H4** (adding USGS Qfaults as labels) is rejected because the competition rules already identify those maps as a label source (S1, "Labels").

The portfolio scan is derived from `evidence/registry_manifest.json` and local source files; opaque filenames, unlisted/private submissions and hidden upstream code can still conceal overlap. No new candidate is "unique" until its surface and final raster pass the exact registry gate. Under the current raw gate, IR-53-46 makes that impossible on the rebuilt registry.

## Three untested candidate hypotheses for a future session (not implemented or promoted)

| Rank | Candidate | Layers and physical signature | Why it could mark an unmapped fault | Difference from this repo / overlap screen | Expected DTI improvement (qualitative prior only) | Cost and source status |
|---|---|---|---|---|---|---|
| 1 | **C1: conductivity–magnetic cross-scale phase coherence** | Competition-stack band 17 `cond_surf` plus band 2 `rtp` (optionally band 3 `tmi_hg` / band 6 `tc`). Use multi-scale complex-wavelet phase/edge coherence, requiring co-located line-like boundaries with consistent orientation; do not just sum the bands. | A buried fault/damage zone may juxtapose magnetic units and host conductive fluid/alteration anomalies, even where no fault trace is in the USGS/INGENIOUS catalogue. USGS analogues show concealed faults interpreted from linear aeromagnetic anomalies (S31) and fault-controlled hydrothermal conduits with electrical-resistivity/magnetic-susceptibility signatures at Yellowstone (S32). These are mechanism analogues from other regions, not evidence that this signature predicts Great Basin faults. | No conductivity cross-wavelet/phase feature exists in `src/gems53`; this is distinct from H1's catalogue distance and H2's single-band Hessian ridge. The prior portfolio contains related magnetic/multiphysics/alteration work, so only the *specific conductivity–magnetic phase-coherence transform* is a candidate; novelty is not proven. Official rationale sources: [USGS OFR 2009-1156 (S31)](https://www.usgs.gov/publications/high-resolution-aeromagnetic-survey-image-shallow-faults-poncha-springs-and-vicinity) and [Finn et al. 2022, USGS (S32)](https://pubs.usgs.gov/publication/70230158); both are analogues, and S32 is Yellowstone rather than the GEMS region. | **Moderate, low confidence.** No DTI projection is made. Must beat the frozen spatial-blocked holdout baseline and then pass the canary and registry gate. | **Medium.** Uses the cached 19-band stack; local TIFF metadata identifies band 17 as `cond_surf` and band 2 as `rtp`. The training raster came from the hash-pinned GitHub mirror (S7), not a direct DrivenData download, so names and values are verified only against that mirror, not independently against the official competition package. |
| 2 | **C2: depth- and time-resolved earthquake-plane continuity** | Raw earthquake hypocentres (location, depth, time, magnitude), not only the stack's smoothed bands 10/16. Target coherent 3-D hypocentral planes and depth-step terminations across spatial blocks. | Seismicity can illuminate active or reactivated fault segments absent from a surface catalogue; time/depth structure can distinguish a coherent fault plane from diffuse seismic background. | The 19-band stack contains smoothed earthquake distance/intensity; this proposal uses raw event geometry and temporal structure, not those scalars. The registry includes a “seisgeom-ridgesnap” candidate, so portfolio novelty needs a source-code audit. | **Moderate potential, very uncertain.** Raw event planes may map active faults, but sparse/temporally biased seismic coverage could limit catalogue-proxy recovery. No DTI projection. | **High / blocked here.** Candidate official source: [USGS ANSS ComCat FDSN event service](https://earthquake.usgs.gov/fdsnws/event/1/). This host is outside this session's egress allow-list, so endpoint availability, licensing and downloadability were not checked; it is **not viable in this environment** until checked. |
| 3 | **C3: seasonally persistent satellite thermal residuals** | Multi-date USGS Landsat Collection 2 Level-2 surface-temperature composites, after emissivity, elevation, land-cover and seasonal controls; test persistent local thermal residuals, not one-date brightness. | Persistent thermal upflow can identify a fluid pathway/vent above an unmapped permeable structure, an independent observation rather than a catalogue trace. | The stack has no satellite thermal time series. Portfolio files include probe/population/geothermometer-style thermal approaches, so this is a different measurement modality, not a claim that “thermal” is new. | **Low-to-moderate, high uncertainty for fault labels.** Thermal vents do not represent every fault, so signal coverage may be sparse. No DTI projection. | **High / blocked here.** Candidate official source: [USGS Landsat Collection 2 Level-2 science products](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products). USGS is outside this session's egress allow-list; product coverage, access and licence were not verified. **Not viable here until obtained and verified.** |

**Selection for the next experiment (original review; history):** C1 is the only candidate that can be evaluated from the existing feature stack without new third-party data. **Update 2026-10-09 session 2: C1 was implemented and validated** (S2-E1 canary pass; S2-E2 design-B holdout stage-2 ACCEPTED; candidate built and gated — verdict negative on the uniqueness overlap reading only; see `evidence/s2_c1_holdout.json` and `docs/submissions/CURRENT.json`). No weekly slot has been used or selected. C2/C3 must not be called viable until their official sources and data rights are checked. All candidates require a new pre-registration, per-feature leakage canary, whole-segment hide-and-recover, spatial-blocked confirmation and the registry uniqueness gate before a submission decision.

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
  (IR-53-42). The holdout gain is therefore an upper bound for new-fault performance, not an estimate of it.

## M1 - metric-aware thinning (tested as part of the variants)

- **Layers:** the probability surface of the chosen arm (no new layer).
- **Mechanism (from the metric, S1):** TP credit is a max over the 3 px neighbourhood, FP credit is a sum over area, so a thin
  dominating set keeps TP and removes FP mass. `src/submission_optim.py` in the shared template states the same argument and
  measured a similar effect on a smoke model. This session measured it on our holdout (design B, see E2 tables).
- **Structure seen in the registry:** GEMSDOE32 H33-2-B2 has its dots spaced about the metric radius apart (median
  nearest-dot distance 3.0 px, measured in `evidence/gemsdoe32_measured.json`). That is the same structure M1 produces. It
  does not show the file's score (IR-53-02).

## H5 - off-catalogue thermal and paleo-geothermal evidence (not tested in this lane; portfolio analogues exist)

- **Layers (external, pinned mirror, commit 56d78de7, S26):**
  - `2m_temperature_probe_INGENIOUS_regional_data` (shallow 2 m temperature probes, NAD83 UTM 11N, with T2m, T1m and T15m; S28);
  - `paleo_geothermal_regional/Paleo_geothermal_final.csv` (paleo-geothermal deposits, e.g. travertine, with coordinates);
  - `wellspringdata.gdb` (wells and springs geodatabase; ESRI format, not parsed here).
- **Signature:** shallow thermal anomalies and travertine or silica deposits line up with permeable fault zones. Those zones are the
  geothermal targets, and they are not the catalogue.
- **Off-catalogue rationale:** the evidence is a measurement, not a fault trace. A deposit on an unmapped structure is a direct
  observation of that structure.
- **Difference from the repo:** none of these layers is in the 19-band stack.
- **Cost and risk:** five layers to geo-reference to the 100 m grid, a licence check (IR-53-44), and a holdout run. The
  sandbox can reach the mirror but not USGS, ScienceBase or GDR directly.
- **Why not run now:** the three-experiment budget is used (E1, E2, E3); related thermal/geothermal approaches also already appear in the portfolio (see the initial screen). This is not a unique new strategy without a precise, pre-registered differentiation.

## H2 - magnetic lineament ridges (attempted; no valid design-B holdout confirmation)

- **Layers:** reduced-to-pole magnetics (band 2) and total magnetic intensity (band 14); native GeoDAWN grids for area 1
  and area 2 (`GeoDAWN_tiffs/22103_area*_tiffs/22103_rtp_*.tif`, pinned mirror S26) if a finer grid is wanted.
- **Signature:** linear magnetic breaks and ridges at 1 to 3 km scales, typical of buried or covered faults. This family is implemented in `src/gems53/ridge.py` and was evaluated by X1/X2/X3; it is historical evidence, not a future untried candidate.
- **Off-catalogue rationale:** covered basins have few mapped faults, but magnetic breaks show them.
- **Difference from the base feature stack:** the 19 bands include gradients and tilt products (3, 6, 9) but no explicit ridge-centreline extraction; this repo's `src/gems53/ridge.py` adds it. Band canaries under design B put the strongest label-free band at separability 0.59 (band 7, geodetic shear rate; fold maximum, `evidence/e2_leakfree_holdouts.json`, `canary_design_B`). That is below the 0.90 gate, but it is not weak.

## H7 - regional trend prior (not tested in this lane; portfolio analogues exist)

- **Layers:** the visible known-fault raster only (no new data).
- **Signature:** new faults in a strike-slip province often run sub-parallel to the regional trend (for example NW-SE in the Walker Lane,
  a geological expectation to be checked, not assumed).
- **Off-catalogue rationale:** the prior is a regional orientation, not the location of any catalogue fault.
- **Portfolio screen:** related local-strike and strike-coherence candidates are present in GEMSDOE41, GEMSDOE48 and GEMSDOE52. The broad idea is therefore not globally new; a genuinely different, pre-registered variant would need explicit separation from those methods.
- **Cost:** low. It could be tested on the segment folds after the experiment budget resets, but it is not ranked as a new top candidate.

## H3 - fault-parallel strain (BLOCKED, IR-53-40)

- The stack carries three strain scalars: the second invariant (band 4), the shear rate (band 7) and the dilatation rate
  (band 8). The mirrored NBMG CSV has the same three scalars and no principal orientation
  (`geodetics_INGENIOUS_regional_data/geodetic_strain_rate_csv.csv`, columns read on 2026-10-08).
- A fault-parallel test needs the tensor or the principal azimuths. Those are not in the public mirror, and the sandbox cannot reach the NBMG or GDR sources.

## H4 - rejected

- USGS Quaternary Fault and Fold Database as an extra label source: the rules name the USGS quaternary maps as a label source,
  so using them re-expresses the catalogue (S1, "Labels").

## Sources checked for each hypothesis

- Layer list: `evidence/exp1_leakage_canary.json` (band names), `data/bridge/manifest.json` in the template (`S25`).
- Mirror contents and commit: `S26` (`jklinck/geothermal_research@56d78de7`), read through the GitHub API on 2026-10-08.
- Rules and metric: S1 (problem page) and S3 (NLR rules PDF), as recorded in `registry/sources.json`.
- No hypothesis has an organiser score. None is ORGANIZER-CONFIRMED.

---

# S3 update (2026-10-08): H8 tested (negative); ranking of the untested hypotheses

This section supersedes the ranking table above for the untested items. Band names are read from `training_features.tif` (verified, 19 bands). Every number is HOLDOUT-DTI (proxy; `gems53.core.dti` v1.0.0), not an organizer score.

## H8 - gravity horizontal-gradient maxima on band 13 (tested S3-B, NEGATIVE)

- Layer: band 13 `iso_grav_anom` (isostatic gravity anomaly, label-free). Transform: Blakely and Simpson (1986) maxima of |grad g|, 100 m cells, 90th percentile threshold, 3 px border (`src/gems53/h8.py`).
- Result (design B, pre-registration S3 section 4): stage 1 selected `thin_bin_q0p1` (pooled 0.091362 on the segment folds, selected on those folds). Stage 2 spatial: H8 pooled **0.00402**; bands baseline 0.000102; the E2 H1 `thin_bin_q0p1` best 0.004049.
- Paired H8 minus H1, fold mean +0.000424, 95% CI [-0.003746, +0.004594]. The lower bound is not above 0, so the pre-registered rule gives **NEGATIVE**. Note: the pooled values are nearly equal (0.00402 vs 0.00405), but the paired fold differences are not one-signed.
- Paired H8 minus bands: +0.003957, CI [0.000129, 0.007785]. H8 adds information over the bands baseline on the proxy, but not over H1.
- Canary (single feature, design B, fold maxima): R 0.502, S 0.502, log1pD 0.572. All below the 0.90 gate.
- Receipt: `evidence/s3b_h8_holdout.json`. Run card: `evidence/run_card.json` (`s3_lane`).

## Untested, ranked by expected DTI gain divided by cost (judgement)

| Rank | ID | Hypothesis | Layer(s) (verified names) | Named non-fault mimic (to be tested as negative control) | Expected gain / cost (judgement) | Status |
|---|---|---|---|---|---|---|
| 1 | **H12** | Coincidence of H8 gravity-gradient ridges and magnetic horizontal-gradient maxima within 2 px. Two independent potential-field edges at one location are more likely a fault than either alone. | band 13 (H8 ridge) and band 3 `tmi_hg` (TMI horizontal gradient) | Lithological contacts that produce a gravity edge without a magnetic edge (and the reverse) | moderate / low (in-stack) | **proposed, not run**. Next experiment; validate on a spatially blocked holdout before any slot. |
| 2 | **H10** | Blakely and Simpson gradient maxima on band 15 `depth_to_base_surf` (sedimentary cover thickness). Basin-margin faults show as steps in cover thickness. | band 15 | Stratigraphic onlap and depositional thickness changes without faulting | moderate / low (in-stack). Caveat: the origin of band 15 is not documented here; if it derives from the same gravity field as band 13, it partly duplicates H8. | proposed, not run |
| 3 | **H9** | Hessian or curvature ridges on band 12 `det_elev` (100 m detrended elevation). Fault scarps appear as linear ridges in curvature. | band 12 (and band 19 slope) | Erosional escarpments, landslide scarps, and river terraces (USGS OFR 89-365 notes stream courses confound lineament interpretation) | low to moderate / low. Limit: scarps smaller than 100 m are unresolved at this grid. | proposed, not run |
| 4 | H5 | Off-catalogue thermal and paleo-geothermal evidence (INGENIOUS temperature probes, wells, springs) | external | Hot springs not on faults | unknown / medium. Licence to verify (IR-53-44). | not tested (earlier budget) |
| 5 | H2 | Magnetic lineament ridges (Hessian) on band 2 `rtp` native grids | band 2 (native GeoDAWN grid) | Dike and intrusive edges | moderate / medium | not tested |
| 6 | H7 | Regional trend prior (dominant orientation of visible faults) | catalogue-derived | Any trend-aligned feature | small to moderate / low | not tested. Caution: catalogue-derived, so it must use visible faults only. |
| - | H11 | Seismicity epicentre alignments (USGS ComCat) | bands 10 `deq_n100a15` and 16 `ieq_n100a15` already provide earthquake-derived features in the stack | Aftershock clusters along non-fault structures | potentially high / high | **BLOCKED**: the sandbox cannot reach ComCat (L-31). Also possibly redundant with bands 10 and 16 (not checked). |
| - | H3 | Fault-parallel strain | bands 7 and 8 are scalars | - | none | BLOCKED (IR-53-40) |
| - | H4 | USGS quaternary fault maps as extra labels | - | - | none | rejected (labels) |

Notes on the table: the gain and cost columns are judgements, not measurements. Nothing in the table is a score. Any of ranks 1 to 3 needs the spatially blocked holdout (design B, stage 2) before a submission slot is considered, and a named mimic run as a negative control.
