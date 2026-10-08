# GEMSDOE53 — GEMS Prize research workspace

## Read this first at the start of every session

This repository exists to support rigorous, auditable discovery of **previously unmapped geological faults** in the DOE GEMS Prize study area. The long-form project request has been normalized below into a persistent operating brief so each session starts from the same goal, evidence standards, and constraints. It is not permission to invent data, reuse an earlier submission, or claim that a proxy score is an organizer score.

### Standing project brief

- **Objective:** maximize the probability of a scientifically defensible, high-performing competition result. Treat the competition as a discovery task, not merely a raster-classification task. Own the outcome end to end: investigate defects, disclose failures, and improve shared tooling rather than hiding or forking it.
- **Scientific scope:** find faults that are absent from the supplied USGS/INGENIOUS catalogue, using only features available at prediction time. Use official, freely accessible, properly licensed sources for external data; record provenance, access, license, CRS, resolution, hashes, and transformations.
- **Research discipline:** before testing a method, state its mechanism, non-fault confounder, expected observable signature, relationship to previously tested work, and a spatially blocked evaluation plan. Do not imply that a feature is leak-free merely because it has a plausible geological interpretation.
- **Leakage discipline:** apply learn–predict separation. For each held-out fault segment, construct all catalogue-derived features from visible faults only; never derive training features or training-row selection from the hidden target. Test each feature alone on the holdout. Treat a single-feature AUC above 0.90 as a leakage canary until its provenance and prediction-time legitimacy are demonstrated.
- **Holdout discipline:** hide whole fault segments with a spatial buffer; mask visible faults pixel-exactly; use the official distance-weighted Tversky metric (α = 0.2, β = 0.8, triangular support 300 m); report pooled DTI, evaluator version, withheld-positive count, and a 95% confidence interval. A catalogue hide-and-recover score is a proxy—not an organizer score and not proof of transfer to unmapped faults.
- **Parallel-run discipline:** stay in the session's assigned method lane. Reuse the shared cached stack, evaluator, and writer; do not recreate them in a private fork. If a shared tool is wrong, report the defect for a fix in the shared template. Stop after three experiments or two hours, whichever comes first. Do not choose a competition submission slot; a separate selector step owns that decision.
- **Uniqueness and release discipline:** compare a candidate raster with every available registry raster before placement and again on final dots. A rank-correlation above 0.90 or more than 70% of dots within three pixels of one registry raster is a duplicate warning: record it and stop. Never copy an earlier submission as the deliverable. A negative result is still a deliverable.
- **Submission contract:** the competition requests one-band float32 GeoTIFF predictions in EPSG:32611, at 100 m, with the same bounds/shape/geotransform as the template and predicted values in [0, 1]. A release must be independently reopened and validated across the whole stored array, not just the nominal footprint. The user previously reported a portal range error; test every value including nodata/outside-footprint cells and confirm any zero-outside upload variant against the official template. Clearly expose a unique `.tif` download at the top of any future site, with an unmistakable `Validated / OK to submit` label only after all gates pass; otherwise label it `Research-only / DO NOT SUBMIT`. Include a unique submission name and a note of no more than 140 characters. Never label a projection as a score. Explain the upload steps in an executive-summary page.
- **Research product:** maintain a clean, current evidence feed, a cited source table, a readable executive summary, ranked testable hypotheses, an explicit irregularity register, and a transparent list of data/access limitations. Use official sources and links for manual review. Do not make leaderboard claims without a submission-page receipt.
- **Project delivery:** when implementation is ready, open a pull request from this session branch, verify it, and merge it if repository checks and branch policy permit. Never change this session's branch.

### Core values

**Maximize P(Win).** Every experiment and scarce submission opportunity should be chosen for its expected contribution to a valid result, not for novelty alone.

**Own the Outcome.** Report defects and negative results clearly; fix shared systems where permitted; do not treat a successful file write as proof of scientific validity or organizer acceptance.

## Active lane for the present review

**Formal diagnosis of the GEMSDOE29 catalogue-distance leakage failure.** This pass is limited to the leakage mechanism, the integrity of its hide-and-recover evaluation, and the evidence needed before any candidate can be released. Do not branch into unrelated geological hypotheses or use a weekly competition slot in this lane.

See [`docs/leakage-review.md`](docs/leakage-review.md) for the source-linked diagnosis and [`evidence/parallel-run-card.json`](evidence/parallel-run-card.json) for the required run card.

## Current checkout status — verified at review start

The checked-out repository initially contained only this README. It had **no** feature stack, competition rasters, cached arrays, registry rasters, evaluator, submission writer, site, tests, or existing submission TIFF. The official DrivenData data-tab URL redirected to its login page during this review. Therefore this checkout cannot produce a competition-conformant or holdout-validated TIFF in this session.

No placeholder, all-zero raster, copied prior TIFF, projection, or synthetic template will be presented as a competition submission. **There is no TIFF to download or submit from this repository at present.** The run card is negative, not a score claim. The public GEMSDOE29 files were reviewed read-only for diagnosis; this session did not alter their shared tools or keep a private copy/fork.

## Official sources to start with

| Topic | Source |
|---|---|
| Challenge overview, timeline, rules, and how to compete | [DrivenData GEMS Prize overview](https://www.drivendata.org/competitions/306/competition-doe-gems/) |
| Task definition, datasets, metric, and TIFF contract | [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| Login-gated competition data | [DrivenData data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) |
| Official challenge rules | [DOE/NLR GEMS Prize rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| Organizer reference code | [DrivenData reference solution](https://github.com/drivendataorg/gems-prize-reference-solution) |
| GeoDAWN geophysical survey | [USGS GeoDAWN data release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) |
| INGENIOUS regional compilation | [Geothermal Data Repository, submission 1391](https://gdr.openei.org/submissions/1391) |
| Leakage methodology | [KDD 2011](https://doi.org/10.1145/2020408.2020496) · [ACM TKDD 2012](https://doi.org/10.1145/2382577.2382579) — Kaufman, Rosset, Perlich & Stitelman |
| Non-fault lineament confounder context | [USGS Open-File Report 89-365](https://pubs.usgs.gov/of/1989/0365/report.pdf) |

## What remains blocked

1. Restore the approved, hash-verified competition template and feature stack into this checkout (the official data tab requires a DrivenData login); do not place credentials in chat.
2. Use the actual shared evaluator and writer. The exact filenames named in the run protocol are not in this checkout; the GEMSDOE29 public repository uses different module/script names and its existing fold summaries do not implement the required pooled-DTI-plus-95%-CI report.
3. Resolve the two source-audit risks documented in the leakage review: label-derived filtering of holdout negative candidates, and fold-wise rather than pooled score aggregation. Fix shared tooling in its owning template; do not copy it here.
4. Run the feature-alone leakage canary across the complete, current feature inventory under the required blocked holdout. Only consider a candidate if it beats the comparable holdout best, passes both uniqueness checks, and passes the exact GeoTIFF validator.
5. Build the website, one-click download, executive submission guide, and data/source catalog only after there is a verified candidate and a reproducible build pipeline. Do not scrape or manually monitor the DrivenData website for a current leaderboard feed without prior written consent or an expressly authorized feed; see the official [Terms of Use](https://www.drivendata.org/termsofuse/).
