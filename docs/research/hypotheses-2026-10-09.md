# Candidate hypotheses — session 2026-10-09 (ranked before implementation; result column added after E2)

Labels: **HOLDOUT-DTI** = our hide-and-recover proxy (evaluator `gems53.core.dti` v1.0.0, truth = withheld catalogue
segments, 60,988 withheld positives pooled over 5 folds). **USER-REPORTED** = a leaderboard value supplied in the brief.
**INFERENCE** = algebra on USER-REPORTED values (not a score). Nothing here is ORGANIZER-CONFIRMED.

## What the scored GEMSDOE files teach (measured, `evidence/h53_lineage_algebra.json`)

* The 0.2778 file (GEMSDOE32 H33-2-B2) is **exactly** the 0.2600 d2.8 dot file (GEMSDOE25) minus every dot within
  2 px of the catalogue: B2 ⊂ r1 ⊂ d2.8 (set relations measured; 3,891 dots ≤ 1 px removed → 0.2708; 2,545 more ≤ 2 px
  removed → 0.2778). No new information was added in either step.
* DTI algebra (from the official formula, S1): `1/DTI = 0.2 + (0.2·FP_w + 0.8·|G|)/TP_w`. If the removed dots were pure
  false positives, each step implies TP_w ≈ 5,073·f and ≈ 5,470·f (f = public-chunk share of the removed dots). Two
  independent steps agreeing within 8 % **supports** (does not prove) the reading that dots on/adjacent to the catalogue
  earn ~no credit against the expert "new fault" test set. **INFERENCE.**
* Marginal rule (exact): a dot with expected credit c and FP cost f_c raises DTI iff `c/f_c > 0.2·DTI/(1 − 0.2·DTI)`
  = 0.0588 at DTI 0.2778. Since an on-truth dot can earn up to ~2.3 credit, a dot pays for itself at roughly ≥ 2.5 %
  hit probability. The bottleneck is ranking quality, not dot count.
* Why 0.2778 is top among GEMSDOE files: a supervised multi-line emission (H19-5) + metric-aware thinning to ~3 px
  spacing (d1.5 0.2477 → d2.8 0.2600, USER-REPORTED) + catalogue-flank prune (→ 0.2708 → 0.2778). The leaderboard top
  (0.3774, xiaofanhu, verified on the live board 2026-10-09) is ~36 % higher; its method is not public.

## Ranked candidates

| Rank (pre-run) | Candidate | Layers / physical signature | Why it could catch a fault missing from the catalogue | Difference from this repo and registry | Expected gain / cost | Status |
|---|---|---|---|---|---|---|
| 1 | **H53-HWVC** hanging-wall vector concordance | bands 12 det_elev (−∇), 13 iso_grav_anom (−∇), 17 cond_surf (+∇), 15 depth_to_base_surf (+∇); magnitude-weighted circular resultant at σ = 2, 5 px + Canny NMS centreline | A normal fault down-drops and fills its hanging wall; four independent measurements should point to the same down side even where no Quaternary scarp exists (catalogue requires Quaternary evidence) | Sign-aware 4-band vector concordance; not a single-band ridge (H2), not catalogue distance (H1). Related to cross-gradient structural similarity (Gallardo & Meju 2003, S33) but uses co-direction, not orthogonality. GEMSDOE41 "basin-margin" is a different construction (3DEP scarp + RTP) | Moderate prior / low cost (stack only) | **Tested: NEGATIVE** on the pre-registered rule (see `evidence/h53_e2_holdout.json`). Best label-free canary features (0.5997) but no gain once H1 + 19 bands are in the model |
| 2 | **H53-FLANK3** catalogue flank 3 px for our own decoder | labels.tif only (metric structure, not physics) | The test set is defined as faults *not* in the USGS database; algebra says ≤ 2 px flank dots were FP-only. A dot 2–3 px from a catalogue fault gives 0 kernel weight to that fault anyway | GEMSDOE32 rejected B3 on its proxy (never LB-scored). For **our** file it is a decoder parameter, not a copy | INFERENCE: if B2's 2,171 dots in (2, 3] px were also FP-only, B2 → ≈ 0.284; cost trivial, but **cannot be validated on the catalogue holdout** (the holdout truth is the catalogue itself) — needs one organizer slot | Proposed for the next session (not pre-registered here; D-S uses 2 px) |
| 3 | **C1** conductivity–magnetic cross-scale phase coherence (prior session) | bands 17 + 2 (+3, 6) | buried damage zones juxtapose magnetic units and host conductive fluids | not implemented anywhere in `src/gems53` | moderate / medium | Untested (budget) |
| 4 | **H53-DEM1M** 1 m 3DEP scarp-break detector via a GitHub Actions runner | USGS 3DEP 1 m DEM tiles listed in the competition's `1m_DEM_links.csv`; multi-azimuth scarp height × slope-break | experts mapped the new faults manually, most plausibly from high-resolution topography; 100 m `det_elev` cannot resolve metre-scale scarps | lidar/DEM scarp families exist in the registry (GEMSDOE7, 10, 12, 19, 47), so only a specific new transform could be unique | potentially the largest gain / high cost. **Source:** [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) — page fetched 2026-10-09: "All 3DEP products are available free of charge and without use restrictions." **Obtainability:** this sandbox cannot reach USGS hosts; a GitHub Actions runner can (GEMSDOE19 reports doing so — OWNER-CLAIM, not re-checked) | Not viable *in this sandbox*; viable via Actions (next session) |
| 5 | **C2** ComCat hypocentre-plane continuity | USGS ANSS ComCat raw events | seismicity illuminates active blind faults | stack only has smoothed seismicity scalars | uncertain / high. Source: [USGS ComCat FDSN](https://earthquake.usgs.gov/fdsnws/event/1/) — outside sandbox egress; Actions route needed | Not viable in this sandbox |

**Rejected idea (recorded so nobody re-tries it blindly):** decomposing the ~40 USER-REPORTED scores of registry
rasters to locate credit-bearing regions. It would fit the *public* chunks only; the prize is decided on the *private*
chunks and on the expanded final label set, so it lowers P(Win) while raising public-board risk.

## Leakage audit of every feature in the current stack (Kaufman et al. question: "could it only take this value because the label is known?")

| Feature | Derived from labels? | Canary (max separability, design B, `evidence/h53_e1_canary.json`) | Verdict |
|---|---|---|---|
| 19 competition bands | No (geophysics, geodesy, topography, seismicity) | ≤ 0.593 | clean |
| H1 catalogue distance | Yes — **recomputed per fold from visible faults only**; own segment excluded for training positives | 0.768 | legitimate at prediction time (the catalogue is a supplied input); below 0.90 |
| HWVC (6 channels) | No | ≤ 0.600 | clean |
| GEMSDOE29 full-catalogue distance (reference) | Yes — computed from the full label raster incl. the pixel's own label | 1.0 by construction (0 on every catalogue pixel) | **leak** (textbook Kaufman case) |

Sources: Kaufman, Rosset, Perlich & Stitelman, *Leakage in data mining*, ACM TKDD 6(4) 2012,
[doi:10.1145/2382577.2382579](https://doi.org/10.1145/2382577.2382579) (abstract fetched 2026-10-09: defines leakage as
information "that should not be legitimately available to mine from" and proposes "learn-predict separation").

## Final results of this session (added after E2/E3/gate; all numbers from committed receipts)

**E2, hide-and-recover** (`evidence/h53_e2_holdout.json`). HOLDOUT-DTI, evaluator `gems53.core.dti` v1.0.0 (alpha 0.2, beta 0.8, R 3 px), 60,988 withheld positives, segment folds K = 5 with a 10 px buffer, 95% t-interval df 4. Arm A reproduces the previous session's 0.141319 exactly.

| Stage / decoder | A (19 bands + H1) | B (A + HWVC) | B−A mean [95% CI] | B wins |
|---|---|---|---|---|
| Stage 1 M1 thin q0.10 | 0.141319 [0.13378, 0.14892] | 0.139727 [0.13130, 0.14823] | −0.001587 [−0.003732, +0.000559] | 1/5 |
| Stage 1 D-S (flank 2, sep 2.8, 40k) | 0.116626 [0.10813, 0.12528] | 0.117022 [0.10687, 0.12733] | +0.000400 [−0.002619, +0.003419] | 3/5 |
| Stage 2 spatial M1 | 0.004049 | 0.004456 | +0.000344 [−0.000216, +0.000903] | 4/5 |

Promotion rule (pre-registered): stage-1 lower bound > 0 AND stage-2 mean > 0, so **promote B = False. HWVC is NEGATIVE as an add-on feature.**
D-S scores below M1 on this proxy (IR-53-52). That was expected: the proxy rewards catalogue adjacency, and D-S removes it on purpose.

**E3 build + uniqueness gate v2** (`evidence/h53_e3_build.json`, `evidence/h53_gate_v2_e3_armA_ds40000.json`):
- The arm-A + D-S file (40,000 dots, ≥ 2.83 px from the catalogue, median 5 px) is **DUPLICATE** against 27 registry rows. Examples: our 2026-10-08 file (overlap 1.000, kappa 1.000), GEMSDOE37 physics-dotted-80k (0.892 / 0.852), 12GEMSDOE r5-nms3-trace (0.872 / 0.816), GEMSDOE43 sup01-hgb21-n40000 (0.812 / 0.769).
- Verdict: **DO NOT SUBMIT** (IR-53-57).

## New candidate for the next session (ranked first)

| Candidate | Layers | Why it could catch uncatalogued faults | How it differs | Expected gain / cost |
|---|---|---|---|---|
| **H53-HWVC-CF**: catalogue-free HWVC model, validated on spatial blocks | bands 12, 13, 15, 17 (HWVC channels) + the 19 official bands; **no catalogue-distance feature**; decoder flank ≥ 3 px; pre-placement fast gate against the 27 rows of IR-53-57 | E2 measured HWVC only *on top of* H1. H1 pulls dots onto catalogue sleeves that are both FP-heavy (lineage algebra) and shared with the registry (IR-53-57). Without H1, the model has to find structure from physics alone, which is the far-from-catalogue regime where the 0.2778 file lives (median 19.65 px) | Not tested anywhere: E1's canary is label-free, and E2 always included H1 | Unknown / low cost (stack cached in `/tmp/h53/hwvc.npz`, but the stack is regenerated per session). Validate on spatial blocks (stage 2), not on segment folds, because segment folds reward catalogue adjacency |
