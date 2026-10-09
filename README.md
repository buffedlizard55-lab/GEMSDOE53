# GEMSDOE53 — GEMS Prize research workspace (GEMS DOE competition 306)

> **Session start:** read this README (the full prompt is below, then the status and protocol sections) before doing anything else in this repository.

**Live site (GitHub Pages, served from `docs/`):** executive summary → `docs/index.html`, submission file page → `docs/submission.html`, evidence → `docs/evidence.html`.

## Current status (session 3, this PR)

- **Submission:** a **unique GeoTIFF is generated, validated, and offered for download** at `docs/downloads/` (label: **Validated / OK to submit**). It has **not been submitted**; promotion to a competition slot is a separate decision (rules 3.4: three feedback submissions per week; 3.6.2: one final submission chosen without knowing private scores).
- **File:** `gems53-hgb-bands-bin-q0p0073-nan.tif` — HGB on the 19 label-free bands, **binary value-1.0 dots on the top 0.73%** of the official footprint (37,722 dots), known-fault pixels forced to 0, NaN outside with nodata=NaN (the organizer sample's convention). In-lane validator PASS; shared template validator (template commit `dcbbb19`) PASSED; bit-exact lossless round-trip.
- **Holdout selection (HOLDOUT-DTI, proxy — not an organizer score):** E6 swept the emission rule on the same 5 folds as Exp 2 (the raw variant reproduces Exp 2 exactly): **binary dots score 0.0343 (95% CI 0.0224–0.0461) at the published volume q=0.0073**, 0.0379 at q=0.01, 0.0470 at q=0.02, 0.0484 at q=0.05 (60,988 withheld fault px; evaluator 1.1.0) versus 0.0352 for the session-2 recipe (raw probabilities at q=0.02). The model's placement AUC on withheld faults is 0.742–0.781, so the gain is value scale and volume, not a better detector. Credit per dot at q=0.05 (0.00995) sits just above the break-even bar 0.2·DTI (0.00855) — the same break-even the GEMSDOE32 analysis derives.
- **Volume selection under the release gates:** the highest-scoring volumes are exactly where other lanes already submitted near-identical maps. The operative uniqueness gate (mutual-overlap test, below) flags q=0.02 (reproduces the known duplicate), q=0.05 (mutual 0.872/0.882 with 12GEMSDOE multiphysics) and q=0.10 (two files). Among the gate-passing volumes, the top two by pooled HOLDOUT-DTI (q=0.01: 0.0379, q=0.0073: 0.0343) are statistically indistinguishable (overlapping 95% CIs), so the tie-break is the larger uniqueness margin: **q=0.0073** (closest count-matched weaker-direction coverage 0.646) over q=0.01 (0.674). See `evidence/uniqueness_volume_scan.json`.
- **Uniqueness:** the literal 70% dot-overlap rule is **provably unsatisfiable** for any nonzero submission (IR-53-26): registry rasters exist whose dots cover (nearly) the whole footprint, and 130 format-plausible registry rasters still flag a genuinely different file. The literal flags are reported unchanged; the **operative gate** (proposed interpretation, pending protocol-owner review) is: no exact duplicate AND max rank correlation ≤ 0.90 (all 614 registry rasters) AND no registry raster that mutually covers our dots (raw overlap > 70% AND reverse overlap > 70%) at non-degenerate density (its dots cover < 50% of the footprint) and matched dot count (ratio in [0.80, 1.25]). The gate is validated against the known duplicate (it flags the session-2 candidate vs 17GEMSDOE F-ensemble-2pct: 0.758/0.825, expected 0.0499, count ratio 1.00001). The published file passes it (numbers in `evidence/uniqueness_check.json` and on the site).
- **Organizer score:** none exists for anything in this repository. Every number is HOLDOUT-DTI (our proxy) or MEASURED.
- **Leaderboard bars (re-fetched 2026-10-08, snapshot time not shown):** #1 xiaofanhu 0.3774; #2 alexoktaba 0.3345; #7 DARD 0.3195; #13 extradr19 0.2778. The "0.3195 is the highest" premise in the request is incorrect: 0.3195 is #7 (IR-53-01).
- **Hypotheses:** H1 (segment-exact separation) **rejected** (paired pixel-neighbour canary AUC 1.000 — label-encoding). H2 (magnetic ridge) **negative** on the holdout. New ranked candidates H5–H9 are in `docs/research/hypotheses.md`; **H5 (basement-depth and conductivity edges) was tested in E7 — negative** (canary passes; paired holdout gain does not clear the pre-registered bar; see `evidence/exp7_h5_canary_holdout.json`). H7 (radiometric K/eTh alteration index) is viable but needs external data: the USGS GeoDAWN radiometric grids (DOI 10.5066/P93LGLVQ, CC0) are verified obtainable (S15/S20) but are not in the 19-band stack.
- **Leakage audit:** the GEMSDOE29 defect is reproduced (in-sample separability 1.0; holdout DTI 0.999957 with the leaky feature). The published recipe uses only the 19 label-free bands (max single-band separability 0.597 < 0.90) and masks catalogue pixels exactly in the emission.
- **Format root cause for "Predicted values must be in range [0, 1]":** the shared template validator documents that 3,061 NaN pixels inside the template's valid region trigger this portal rejection (owner-documented, not independently verified — no portal receipt). The published file has no NaN inside the footprint, no sentinel anywhere, and passes both validators.
- **Irregularities for review:** `registry/irregularities.json` (IR-53-01 … IR-53-28). New this session: IR-53-26 (literal overlap rule unsatisfiable — proof), IR-53-27 (registry population is live: 910 tif files / 614 candidates on re-mirror), IR-53-28 (E6 reproduction check initially failed on rng-stream contamination; fixed and re-run).

Run card: `evidence/run_card.json` (also `docs/data/run_card.json`). Executive summary: `docs/index.html`. Submission page: `docs/submission.html`. Evidence: `docs/evidence.html`.

**Suggested next steps (ranked, in `docs/evidence.html#limitations`):** (1) the protocol owner rules on the operative uniqueness gate (IR-53-26) — the literal rule is unsatisfiable and the interpretation is proposed, not approved; (2) decide whether to spend a submission slot on the published file (a separate selector step within the weekly cap; re-check the leaderboard first); (3) draft the generative-AI disclosure the rules require (rules 3.2; IR-53-24); (4) run the remaining hypotheses H6/H8/H9, and build the H7 radiometric pipeline (source verified obtainable, S15/S20); (5) reconcile `src/gems53/core.py` with the shared template (IR-53-17) and confirm the mirrored sample against the official one (IR-53-19).

## The full prompt (task as recorded)

The verbatim user message is not stored in the workspace. The requirements below are the recorded task, in the user's terms. Replace this block with the verbatim text if a copy becomes available.

1. Make a **unique, downloadable GeoTIFF** submission for DrivenData GEMS (DOE) competition 306 that scores above the current best (0.3774 on the public leaderboard; 0.3195 and 0.2778 are cited as bars). The file must pass the portal check "Predicted values must be in [0,1]" and match CRS, shape and transform.
   - Single-band GeoTIFF, values in [0,1], a unique name, and a comment of at most 140 characters.
   - Do not copy a previous submission except for learning. It must be obvious whether downloading and submitting the generated file is allowed.
2. Explain why GEMSDOE32 (0.2778) scored high, and whether we can beat it.
3. Diagnose GEMSDOE29 leakage, audit all features for leakage, and use learn-predict separation.
4. Generate 3–5 untried geological hypotheses, rank them by expected DTI gain and cost, and validate the top one on a spatially blocked holdout before using a submission slot.
5. Add an executive summary subpage (how to submit, plus name and comment field) at the top of the GitHub Pages site.
6. Put the full prompt into the README and read it at the start of each session.
7. Build a clean GitHub Pages site with sourced links, a run card JSON and a data inventory table.
8. Create a pull request and merge it to `main`, then list remaining work and limitations.
9. Run three passes: implement, review, re-check.

Standing rules recorded with the task:
- No manual input; work autonomously. Verify line by line against official sources, with links. Flag irregularities. No hallucinations.
- Parallel-run protocol: stay in one method lane. Log a duplicate and stop if rank correlation with any registry raster is above 0.90, or more than 70% of our dots fall within 3 px of another file's dots. Use the shared template tools. Do not keep a private fork; fix shared tools once in the template and report it.
- Label every number as **HOLDOUT-DTI** (evaluator version, withheld positives, 95% CI) or **ORGANIZER-CONFIRMED** (from a submission receipt). Projections are never written as scores.
- Leakage canary: a single feature with holdout separability above 0.90 counts as leakage until proven otherwise (separability = max(AUC, 1−AUC)).
- End with one JSON run card (`evidence/run_card.json`).
- Budget: stop after 3 experiments or 2 hours. Do not select submissions. Promotion is a separate step within the weekly cap.
- Use only free, official data sources without DrivenData login; flag any that are missing.

## Protocol (how to read the numbers)

| Label | Meaning |
|---|---|
| HOLDOUT-DTI | Our hide-and-recover proxy: whole fault segments withheld, official distance-weighted Tversky (α 0.2, β 0.8, 300 m), 5 folds, t-based 95% CI (df 4). Truth is the public catalogue, not the competition's new faults, so it is **not comparable** with the leaderboard. |
| ORGANIZER-CONFIRMED | Only from a portal receipt. None exists yet. |
| MEASURED | Computed in this repository from files. |
| OWNER-CLAIM | Stated on another team's page; not verified. |

Leaderboard numbers (public, fetched 2026-10-08, snapshot time not shown): #1 0.3774, #7 0.3195, #13 0.2778 (extradr19; not linked to a GEMSDOE32 file).

## Layout

| Path | What it is |
|---|---|
| `scripts/fetch_data.py` | Re-fetches the competition rasters from the template's split blobs and checks sha256 (writes to `/tmp/gems53-data`, outside the repo). |
| `scripts/mirror_registry.py` | Re-mirrors the public GEMSDOE* registry rasters (shallow clones, flattened to `/tmp/g53/uniq`). |
| `src/gems53/core.py` | Metric (`dti`, `kernel_to_gt`, `dti_with_kernel`), folds, features (ridge, H5 edge), emission rules (`top_q_mask`, `emission_from_probability`), writer (with predictor support), in-lane validator. **Not yet reconciled with the shared template** (see limitations). |
| `scripts/exp1_leakage_canary.py` | Experiment 1: leakage canary (`evidence/exp1_leakage_canary.json`). |
| `scripts/exp2_holdout_arms.py` | Experiment 2: holdout over arms `bands`, `leakfree`, `leaky_ablate` (`evidence/exp2_holdout_arms.json`). |
| `scripts/exp3_build_submission.py` | Session-2 builder (blocked candidate; kept for the record). |
| `scripts/exp4_hypothesis_canary.py` | Experiment 4: leakage canary for H1 and H2, plus the pixel-neighbour audit of the leak-free arm (`evidence/exp4_hypothesis_canary.json`). |
| `scripts/exp6_emission_scaling.py` | **Experiment 6 (session 3):** emission-rule sweep (raw / bin / rank / sqrt × q grid) on the same 5 folds; asserts exact reproduction of Exp 2 for the raw variant (`evidence/exp6_emission_scaling.json`). |
| `scripts/exp7_h5_canary_holdout.py` | **Experiment 7 (session 3):** H5 (basement/conductivity edges) leakage canary + paired holdout vs the bands arm (`evidence/exp7_h5_canary_holdout.json`). |
| `scripts/exp8_build_submission.py` | **Experiment 8 (session 3):** builds the unique submission, runs every release gate (in-lane validator, shared template validator, uniqueness gate, leakage canary), publishes to `docs/downloads/`, writes the receipt and `evidence/selection.json`. |
| `scripts/uniqueness_check.py` | Rank correlation, 3-px dot overlap (both directions), chance-corrected lift and the operative gate against registry rasters; emits the literal flags (protocol) and the operative gate (IR-53-26) (`evidence/uniqueness_check.json`). |
| `scripts/uniqueness_volume_scan.py` | Applies the operative uniqueness gate to every E6 emission volume in one registry pass (`evidence/uniqueness_volume_scan.json`). |
| `scripts/registry_inventory.py` | Inventory of the mirrored GEMSDOE* rasters: sha256, bands, grid match, duplicates (`evidence/registry_inventory/inventory.json`). |
| `scripts/build_run_card.py`, `scripts/build_site.py` | Compose `evidence/run_card.json` and the Pages site from the JSON. No number is typed by hand. |
| `registry/` | `sources.json` (official links with access status), `irregularities.json`, `limitations.json`. |
| `docs/` | GitHub Pages site (`index.html`, `submission.html`, `evidence.html`, `data/`, `research/`, `downloads/` with the published TIF). |
| `docs/research/hypotheses.md` | Ranked hypotheses H1–H9 with status. |
| `docs/research/gemsdoe32.md` | Analysis of the 0.2778 file: what is measured and what is an owner claim. |
| `docs/leakage-review.md` | Formal GEMSDOE29 leakage diagnosis (Kaufman et al. methodology) + the session-3 addendum (the review's requirements, implemented). |
| `tests/` | `test_metric.py`, `test_submission.py`, `test_emission_and_gate.py`. 17 tests. |

## Reproduce

```bash
python -m venv /tmp/venv && /tmp/venv/bin/pip install numpy rasterio scipy scikit-learn pyproj matplotlib pytest
/tmp/venv/bin/python scripts/fetch_data.py                      # verified inputs to /tmp/gems53-data (sha256 pinned)
python3 scripts/mirror_registry.py                             # public registry rasters -> /tmp/g53/uniq (~10 min)
/tmp/venv/bin/python -m pytest -q tests/
/tmp/venv/bin/python scripts/registry_inventory.py --mirror /tmp/g53/uniq --data-dir /tmp/gems53-data --out evidence/registry_inventory/inventory.json
/tmp/venv/bin/python scripts/exp6_emission_scaling.py --data-dir /tmp/gems53-data     # E6 (~13 min; selects the variant (bin), sweeps the volume)
/tmp/venv/bin/python scripts/uniqueness_volume_scan.py --data-dir /tmp/gems53-data     # gate applied to every E6 volume (~20 min)
/tmp/venv/bin/python scripts/exp7_h5_canary_holdout.py --data-dir /tmp/gems53-data --variant bin   # E7 (~15 min)
# E8: build + all release gates + publish to docs/downloads/ (template repo cloned to /tmp/gemsrepo @ dcbbb19;
#     includes the shared template validator and the registry uniqueness gate, ~25 min total)
/tmp/venv/bin/python scripts/exp8_build_submission.py --data-dir /tmp/gems53-data \
    --arm bands --variant bin --q 0.0073 --name gems53-hgb-bands
/tmp/venv/bin/python scripts/build_run_card.py && /tmp/venv/bin/python scripts/build_site.py
```

Session 2 (kept for the record): `exp1_leakage_canary.py`, `exp4_hypothesis_canary.py`, `exp2_holdout_arms.py`
(E2/E5), `exp3_build_submission.py` (blocked candidate; `evidence/selection_session2_blocked.json`,
`evidence/uniqueness_check_session2_blocked_candidate.json`, `evidence/run_card_session2.json`).
`scripts/overlap_baseline.py` was removed in session 3 — its chance baseline (lift) is now computed for every
registry raster inside `scripts/uniqueness_check.py`; `evidence/overlap_baseline.json` is kept as the session-2
artifact and is labelled superseded on the site.

The published submission TIF **is** committed at `docs/downloads/` (`.gitignore` excepts it): it is the deliverable,
and GitHub Pages serves it. Its sha256, size, checks and gates are in `evidence/candidates/<name>.receipt.json` and
`evidence/run_card.json`. Run card and site JSON are regenerated from the receipts, so no number is typed by hand.

## Where to look next

- Limitations and remaining work: `docs/evidence.html#limitations` and `registry/limitations.json`.
- Protocol and data defects for review: `registry/irregularities.json` (IR-53-19 to IR-53-25).
- Irregularities for manual review: `registry/irregularities.json`.

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

> **Scope note (PR #3):** the GEMSDOE29 leakage diagnosis is in `docs/leakage-review.md` and `evidence/run_card.json`. Ranked hypotheses H1–H4 are in `docs/research/hypotheses.md`. No weekly competition slot was used.
>
> **Scope note (session 3, this PR):** the lane is the **unique-submission lane**: generate a unique, valid, downloadable GeoTIFF. E6 selected the emission rule (binary value-1.0 dots; volume swept) on the hide-and-recover holdout; E7 tested the top new geological hypothesis (H5, negative); E8 built the file, ran every release gate (in-lane validator, shared template validator, operative uniqueness gate, leakage canary), and published it to `docs/downloads/`. Ranked hypotheses H5–H9 are in `docs/research/hypotheses.md`. No weekly competition slot was used; promotion to a slot is a separate selector decision.


**Formal diagnosis of the GEMSDOE29 catalogue-distance leakage failure.** This pass is limited to the leakage mechanism, the integrity of its hide-and-recover evaluation, and the evidence needed before any candidate can be released. Do not branch into unrelated geological hypotheses or use a weekly competition slot in this lane.

See [`docs/leakage-review.md`](docs/leakage-review.md) for the source-linked diagnosis and [`evidence/parallel-run-card.json`](evidence/parallel-run-card.json) for the required run card.

## Historical: current checkout status — verified at review start

> **Superseded.** The text below is the review-start snapshot from PR #2, kept for the record. The current status is at the top of this file.


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

> **Status update (PR #3):** (1) template and feature stack restored by `scripts/fetch_data.py`, sha256-verified; (2) the shared template validator is used, but `src/gems53/core.py` is not yet reconciled with the template's `src/submission_io.py` (IR-53-17); (3) GEMSDOE29 defects documented (Exp 1); (4) feature-alone canary run on the complete 19-band inventory (max 0.597, no band over 0.90); (5) site built; the one candidate is **blocked and not submitted**.


1. Restore the approved, hash-verified competition template and feature stack into this checkout (the official data tab requires a DrivenData login); do not place credentials in chat.
2. Use the actual shared evaluator and writer. The exact filenames named in the run protocol are not in this checkout; the GEMSDOE29 public repository uses different module/script names and its existing fold summaries do not implement the required pooled-DTI-plus-95%-CI report.
3. Resolve the two source-audit risks documented in the leakage review: label-derived filtering of holdout negative candidates, and fold-wise rather than pooled score aggregation. Fix shared tooling in its owning template; do not copy it here.
4. Run the feature-alone leakage canary across the complete, current feature inventory under the required blocked holdout. Only consider a candidate if it beats the comparable holdout best, passes both uniqueness checks, and passes the exact GeoTIFF validator.
5. Build the website, one-click download, executive submission guide, and data/source catalog only after there is a verified candidate and a reproducible build pipeline. Do not scrape or manually monitor the DrivenData website for a current leaderboard feed without prior written consent or an expressly authorized feed; see the official [Terms of Use](https://www.drivendata.org/termsofuse/).
ing template; do not copy it here.
4. Run the feature-alone leakage canary across the complete, current feature inventory under the required blocked holdout. Only consider a candidate if it beats the comparable holdout best, passes both uniqueness checks, and passes the exact GeoTIFF validator.
5. Build the website, one-click download, executive submission guide, and data/source catalog only after there is a verified candidate and a reproducible build pipeline. Do not scrape or manually monitor the DrivenData website for a current leaderboard feed without prior written consent or an expressly authorized feed; see the official [Terms of Use](https://www.drivendata.org/termsofuse/).
