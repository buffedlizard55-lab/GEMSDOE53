# R3-H1 paired DEM-profile result (2026-10-07)

## Decision

**Build and publish a unique research TIFF; do not upload it.** The registered candidate failed its spatial-holdout promotion gate. The file exists to satisfy the project's end-to-end GeoTIFF delivery and audit requirement, but it is explicitly research-only. No weekly portal slot was used, no portal request was made, and the local test is not an official-score forecast.

## Preregistered geological hypothesis

R3-H1 asks whether the *paired shape* of a small DEM scarp contributes information beyond existing scalar surface features. The two new measurements are computed from band 12 (detrended elevation): normalized Gaussian smoothing at sigma 2 pixels, bilinear samples at ±2 pixels along the local DEM-gradient normal, and bounded, dimensionless signed paired-slope concordance and left/right shoulder asymmetry. Band 19 (detrended-elevation slope) remains part of the existing View B baseline and candidate, but is not directly sampled by the new transform. The feature cache erodes support to 36 pixels; the transform's registered maximum support is 10 pixels. No external data or hidden test labels were used.

The physical idea is plausible but not specific: a fault-related scarp can make a paired, asymmetric step; fan margins, drainage, roads, erosion, lithologic contacts, grading, and DEM processing can make similar profiles. At a 100 m grid, this is a broad landform test, not a metre-scale scarp detector or a method for finding faults with no surface expression. It is not a geothermal-vent detector.

## Fixed spatial holdout

The comparison refitted every historical R2 arm and the registered H1 candidate using identical per-fold training rows, the fixed learner, the same four quadrant folds, whole original 8-connected catalogue components, an 80-pixel Euclidean train/evaluation buffer, and the same metric-aware placement and area-scaled 37,654-pixel budget. Six R2 mean scores were reproduced exactly from `evidence/holdout_r2.json`; View B remained the local incumbent.

| Fold | View B | View B + R3-H1 | Paired lift | Emitted |
|---:|---:|---:|---:|---:|
| 0 | 0.177276 | 0.178819 | +0.001543 | 18,577 |
| 1 | 0.273067 | 0.272296 | −0.000770 | 9,596 |
| 2 | 0.138047 | 0.138542 | +0.000495 | 3,870 |
| 3 | 0.190294 | 0.189925 | −0.000368 | 5,631 |
| **Mean** | **0.194671** | **0.194896** | **+0.000225** | — |

The preregistered gate required a mean lift of at least +0.005 and positive paired lift in at least 3/4 folds. Observed lift was +0.00022491 with 2/4 positive folds. **The gate failed; R3-H1 does not beat the current comparable local holdout best.** The public score cannot be forecast from these catalogue-component recovery folds: catalogue-zero pixels may contain unmapped faults, and the hidden expert-mapped test labels are unavailable.

Other refitted local means were: raw fusion 0.144376; View A 0.107543; View B 0.194671; naive max-view union 0.189424; structural contrast 0.193167; disagreement router 0.162120. These are local proxy-task values, not leaderboard scores.

## Co-training / disagreement diagnostic

Two sets of held-out catalogue-zero proxy errors were measured in 2,093 spatial blocks (4,201,273 proxy-negative pixel predictions). Maximum absolute Pearson/Spearman correlation was 0.07109 for View A vs View B and 0.08047 for View A vs View B+H1, below the frozen 0.60 abandonment threshold. This allowed the preregistered, single-round secondary experiment to run. It does **not** establish conditional independence or sufficient views; the negative class is an incomplete-catalogue proxy.

| Donor → receiver | Pseudo pixels | Baseline mean DTI | After exchange | Mean paired lift | Positive folds |
|---|---:|---:|---:|---:|---:|
| A → B+H1 | 496 | 0.194896 | 0.195690 | +0.000794 | 2/4 |
| B+H1 → A | 781 | 0.107543 | 0.105284 | −0.002259 | 2/4 |

All exchanged pixels were restricted to training regions; none entered an evaluation region. The exchange was not used in the TIFF. Forty-eight accepted whole A-only components have one CSV row each in `evidence/a_only_reasoning_r3.csv`, including scores, projected centroid, shape, distance to the mapped catalogue, raw contextual band values, a buried-structure interpretation, and competing explanations. These remain model hypotheses, not verified faults. B-only candidates are treated as possible surface artifacts in the fold receipt.

## Research TIFF, format and uniqueness audit

- Filename: `gems52-r3-h1-paired-profile-37654-e42677141dbc-research-only.tif`
- Submission label: `GEMSDOE52-R3-H1-PairedProfile-e4267714`
- Short note (117 chars): `R3-H1 paired DEM profile | local lift +0.000225 vs B (2/4 folds; gate FAIL) | research-only; NOT approved for upload.`
- Decoded SHA-256: `e42677141dbc264dcc0e7b0f7cc96f85fc6ede69c629e50426c205a90669f734`
- File SHA-256: `0a28426785c4125d4560d6279cc763570f791cd1fdb7fb788ba60d6024e1f9db`
- 138,077 bytes; 3,730 × 3,292 cells; one float32 band; EPSG:32611; 100 m cells; sample affine transform; raw values exactly `{0,1}`; 37,654 positive cells; no NaN or infinity; internal mask equals the sample-grid mask.
- Local format gate: PASS. This is an on-disk metadata/range check, not proof of organizer portal acceptance.
- Twelve aligned, accessible prior rasters were checked. No decoded pattern was identical. The candidate's support was 73.9% novel against the accessible prior union (27,838 cells) and 221,770 prior-support cells were not re-emitted; the strict ≥20% support-novelty diagnostic passed. The inventory is finite and cannot prove distinction from inaccessible/private/unlinked artifacts.
- Against separately generated, metric-placed View A and View B outputs, the candidate was not either view or their literal support union. At matched budget against a max-view field, candidate and control intersected at 12,925 pixels and each retained 24,729 pixels the other did not. The candidate was fresh model inference using View B+H1, not a copied TIF, union, or prior-pixel input.
- Official score: **unknown**. Weekly-slot approval: **false**. Slots used: **0**.

## Why the reported 0.2778 appeared strong

The official leaderboard fetch on 2026-10-07 displayed 0.2778 at rank #13, 0.3195 at #7 and 0.3774 at #1. The public board contains participant-level best scores, not submitted filenames, file hashes, upload receipts, or hidden-label maps. Thus the local attribution of a score to a named TIFF remains owner-reported.

The most plausible explanation supported by this repository is *placement*, not a demonstrated geological discovery: local byte-for-byte comparisons of nested sparse rasters show that near-trace off-catalogue mass was removed in the owner-attributed higher-scoring variant. In one tracked comparison, 2,545 dots within 200 m of mapped traces were removed; none were on the mapped mask. Such off-mask mass still participates in the public distance-weighted false-positive accounting unless it receives credit against new truth. Pruning weak flank predictions is therefore consistent with the observed gain. It does not prove that the hidden truth was or was not near a mapped trace, authenticate the score mapping, or recover the organizer's TP/FP/FN terms. See `evidence/reference_forensics_r2.json`, `knowledge/01_why_02778_and_the_bar.md`, and `docs/forensics.html` for the full byte comparison and its limitations.

## Trusted sources and limits

- [Official problem, metric and submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — fault mapping, incomplete known labels, 300 m distance kernel and output requirements.
- [Official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) — dated 2026-10-07 participant-level observation only.
- [Official competition rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf) — entry/submission rules and AI disclosure.
- [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) — reviewed; recurring automated board access remains disabled.
- [Blum & Mitchell, co-training paper](https://www.cs.cmu.edu/~avrim/Papers/cotrain.pdf), DOI [10.1145/279943.279962](https://doi.org/10.1145/279943.279962) — theory motivates testing, but the proxy-negative correlations are not a proof of its premises.
- [USGS 1 m 3DEP DEM catalog](https://data.usgs.gov/datacatalog/data/USGS:77ae0551-c61e-4979-aedd-d797abdcde0e) — public-domain source route for the unselected sub-100 m hypothesis; coverage for this exact footprint and actual tile downloads remain unchecked.

Reproducible receipts: `registry/r3_preregistration.json`; `evidence/features_r3.json`; `evidence/holdout_r3_paired_profile.json`; `evidence/independence_r3.json`; `evidence/cotraining_summary_r3.json`; `evidence/a_only_reasoning_r3.csv`; `evidence/submission_r3.json`; `evidence/format_gate_r3.json`; `evidence/uniqueness_r3.json`; `evidence/not_union_r3.json`; and the independent post-build readback `evidence/independent_tiff_check_r3.json`.

## Three-pass review record

1. **Implement and verify:** froze the hypothesis and gate before evaluation; reran the four-fold validation; built the research-only TIFF only after reviewing the failed-gate receipt; reopened it independently and checked exact template grid/mask, finite `[0,1]` values, note length, file/decoded hashes, accessible-prior uniqueness, non-union placement, and ZIP member/hash.
2. **Inspect and fix:** checked the feed, static-page link paths, downloads-index base paths, old R2 page labels, and exact note/receipt parity. Fixed a missing staged holdout JSON and a nested-page relative link that `check_site.py` caught. Confirmed no automatic DrivenData request or portal upload occurred.
3. **Re-check against the brief:** README retains the full user prompt; the current page exposes the TIF at the top and repeats the failed-gate/no-upload warning; four novel hypotheses are ranked; the top candidate was spatially tested before any slot use; the unique output is explicitly research-only; links, hashes, local byte serving, and the complete test suite were rechecked. These checks do not establish expert geology, portal acceptance, or a leaderboard outcome.
