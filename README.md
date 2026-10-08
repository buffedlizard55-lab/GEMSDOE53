# GEMSDOE53 — GEMS Prize research workspace (GEMS DOE competition 306)

> **Session start:** read this README (the full prompt is below, then the status and protocol sections) before doing anything else in this repository.

**Live site (GitHub Pages, served from `docs/`):** executive summary → `docs/index.html`, submission file page → `docs/submission.html`, evidence → `docs/evidence.html`.

## Current status (session 2, this PR)

- **Submission:** no file is offered for download or submission. Label: **Research-only / DO NOT SUBMIT.**
- **Why:** the only format-valid candidate (`gems53-hgb-bands-q0p02`, the holdout-selected `bands` arm at 2% of the footprint) passes the shared template validator (PASSED, template commit `dcbbb19`). It fails the uniqueness gate: **163 of 613** single-band registry rasters exceed the 70% dot-overlap flag. The closest is `17GEMSDOE F-ensemble-2pct` (103,347 dots vs our 103,348; 75.8% overlap; lift 15.2; rank correlation 0.507). Our recipe duplicates an existing one (IR-53-21).
- **Organizer score:** none exists for anything in this repository. Every number is HOLDOUT-DTI (our proxy) or MEASURED. Holdout DTI for the candidate is 0.0352 (95% CI 0.0282 to 0.0422, 5 folds, 60,988 withheld fault px, evaluator 1.0.0). It is not comparable with the leaderboard.
- **Leaderboard bars (re-fetched 2026-10-08, snapshot time not shown):** #1 xiaofanhu 0.3774; #7 DARD 0.3195; #13 extradr19 0.2778. The "0.3195 is the highest" premise in the request is incorrect: 0.3195 is #7.
- **Hypotheses:** H1 (segment-exact separation, rank 1) is **rejected**: its paired pixel-neighbour canary AUC is 1.000, so it encodes the label. H2 (magnetic ridge) passes the leakage canary but is **negative** on the holdout. H3 is not run.
- **Leakage audit:** the GEMSDOE29 defect is reproduced (in-sample separability 1.0). The current leak-free arm passes the exhaustive pixel-neighbour check (170,638 pairs, AUC 0.4995). The 19 label-free bands are below the 0.90 gate (max 0.597).
- **Format root cause for "Predicted values must be in range [0, 1]":** the shared template validator (`scripts/validate_submission.py`) documents that 3,061 NaN pixels inside the template's valid region trigger this portal rejection. It is owner-documented and not independently verified (no portal receipt). The current candidate has no NaN inside the footprint and passes the template check.
- **Irregularities for review:** `registry/irregularities.json` (IR-53-19 to IR-53-25). Most important: the mirrored `example_submission.tif` is identical to the known-fault labels, although the rules say it predicts total absence (IR-53-19). The overlap gate is confounded for dense, non-submission rasters (IR-53-20).

Run card: `evidence/run_card.json` (also `docs/data/run_card.json`). Executive summary: `docs/index.html`. Submission page: `docs/submission.html`. Evidence: `docs/evidence.html`.

**Suggested next steps (ranked, in `docs/evidence.html#limitations`):** (1) the protocol owner decides on the gate population and lift rule (IR-53-20) and whether the 613-file population is correct; (2) confirm the official sample on the DrivenData data tab (IR-53-19); (3) choose a candidate from a method family not already in the registry (IR-53-21), then run the validator, uniqueness, and holdout gates; (4) draft the generative-AI disclosure the rules require (IR-53-24); (5) run H3 (fault-parallel strain) as the third experiment in a new budget.

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
| `src/gems53/core.py` | Metric, folds, features, writer, in-lane checks. **Not yet reconciled with the shared template** (see limitations). |
| `scripts/exp1_leakage_canary.py` | Experiment 1: leakage canary (`evidence/exp1_leakage_canary.json`). |
| `scripts/exp2_holdout_arms.py` | Experiment 2: holdout over arms `bands`, `leakfree`, `leaky_ablate` (`evidence/exp2_holdout_arms.json`). |
| `scripts/exp3_build_submission.py` | Builds the candidate raster and its receipt from the selected arm and q (`--outdir`). |
| `scripts/uniqueness_check.py` | Rank correlation and 3-px overlap against registry rasters (`evidence/uniqueness_check.json`). |
| `scripts/registry_inventory.py` | Inventory of the mirrored GEMSDOE* rasters: sha256, bands, grid match, duplicates (`evidence/registry_inventory/inventory.json`). |
| `scripts/exp4_hypothesis_canary.py` | Experiment 4: leakage canary for H1 and H2, plus the pixel-neighbour audit of the leak-free arm (`evidence/exp4_hypothesis_canary.json`). |
| `docs/research/hypotheses.md` | Ranked hypotheses H1–H4 with their status after Exp 4–5. |
| `scripts/overlap_baseline.py` | Chance baseline (lift) for the overlap flag. Takes `--receipt`/`--out` (diagnostic; does not change flags). |
| `scripts/build_run_card.py`, `scripts/build_site.py` | Compose `evidence/run_card.json` and the Pages site from the JSON. No number is typed by hand. |
| `registry/` | `sources.json` (official links with access status), `irregularities.json`, `limitations.json`. |
| `docs/` | GitHub Pages site (`index.html`, `submission.html`, `evidence.html`, `data/`, `research/`). |
| `docs/research/hypotheses.md` | Ranked hypotheses H1–H4 (H4 rejected). |
| `docs/research/gemsdoe32.md` | Analysis of the 0.2778 file: what is measured and what is an owner claim. |
| `tests/` | `test_metric.py` (metric checks), `test_submission.py` (validator, NaN-only outside, nodata, LZW round-trip). 13 tests. |

## Reproduce

```bash
python -m venv /tmp/venv && /tmp/venv/bin/pip install numpy rasterio scipy scikit-learn pyproj matplotlib pytest
/tmp/venv/bin/python scripts/fetch_data.py                      # verified inputs to /tmp/gems53-data (sha256 pinned)
/tmp/venv/bin/python -m pytest -q tests/
/tmp/venv/bin/python scripts/exp1_leakage_canary.py --data-dir /tmp/gems53-data          # E1 (~80 s)
/tmp/venv/bin/python scripts/exp4_hypothesis_canary.py --data-dir /tmp/gems53-data       # E4 (~30 s)
/tmp/venv/bin/python scripts/exp2_holdout_arms.py --data-dir /tmp/gems53-data            # E2 (~13 min)
/tmp/venv/bin/python scripts/exp2_holdout_arms.py --data-dir /tmp/gems53-data --arms bands,bands_ridge --out evidence/exp5_holdout_bands_vs_ridge.json   # E5
/tmp/venv/bin/python scripts/exp3_build_submission.py --data-dir /tmp/gems53-data --arm bands --q 0.02 --name gems53-hgb-bands --outdir /tmp/gems53-held
# shared template validator (template repo cloned to /tmp/gemsrepo, commit dcbbb19):
#   python scripts/validate_submission.py --pred /tmp/gems53-held/gems53-hgb-bands-q0p02-nan.tif --sample /tmp/gems53-data/sample_submission.tif --train /tmp/gems53-data/training_features.tif
# registry mirror (public GEMSDOE* repos, shallow clones; tifs flattened into /tmp/g53/uniq) then:
#   python scripts/registry_inventory.py --mirror /tmp/g53/uniq --out evidence/registry_inventory/inventory.json
#   python scripts/uniqueness_check.py --ours /tmp/gems53-held/gems53-hgb-bands-q0p02-nan.tif --registry <dir of prediction candidates> --out evidence/uniqueness_check.json
#   python scripts/overlap_baseline.py --receipt evidence/uniqueness_check.json --out evidence/overlap_baseline.json
/tmp/venv/bin/python scripts/build_run_card.py && /tmp/venv/bin/python scripts/build_site.py
```

The candidate raster (49 MB) is not in the repository and not offered for download. Its sha256 is in `evidence/run_card.json`. Run card and site JSON are regenerated from the receipts, so no number is typed by hand.

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

> **Scope note (PR #3):** the current task extends this lane. The GEMSDOE29 leakage diagnosis is in `docs/leakage-review.md` and `evidence/run_card.json`. Ranked hypotheses H1–H4 are in `docs/research/hypotheses.md`. No weekly competition slot was used.


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
