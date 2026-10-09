# Hypotheses and next-candidate screen (reviewed 2026-10-08)

**No experiment was run during this review.** The three-experiment budget in `evidence/run_card.json` is already used. Ranks are qualitative expected-value-per-cost judgements (expected catalogue-proxy gain balanced against data and validation cost), not DTI projections or scores. Candidate HOLDOUT-DTI values and organizer scores are reported only when measured/receipted in the evidence files.

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

**Selection for the next experiment:** C1 is the only candidate that can be evaluated from the existing feature stack without new third-party data. It was not tested in this review because the experiment budget is exhausted. No weekly slot has been used or selected. C2/C3 must not be called viable until their official sources and data rights are checked. All candidates require a new pre-registration, per-feature leakage canary, whole-segment hide-and-recover, spatial-blocked confirmation and the registry uniqueness gate before a submission decision.

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
