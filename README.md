# GEMSDOE53 — GEMS (DOE) competition 306: submission workbench

> **Session start:** read this README (the full prompt is below, then the status and protocol sections) before doing anything else in this repository.

**Live site (GitHub Pages, served from `docs/`):** executive summary → `docs/index.html`, submission file page → `docs/submission.html`, evidence → `docs/evidence.html`.

## Current status (one paragraph)

One unique, valid candidate GeoTIFF was built (`gems53-hgb-bands-q0p02`, the holdout-selected arm `bands` at 2% of the footprint). It passes the shared template validator and the rules' format checks, and it has no NaN inside the official footprint. It is **blocked and not submitted**: 79.5% of its dots sit within 3 px of one public registry file's dots, above the 70% stop threshold in the parallel-run protocol. Rank correlation is low (max 0.164). **No organizer score exists for anything in this repository.** Every number is a HOLDOUT-DTI proxy unless it is labelled ORGANIZER-CONFIRMED (none yet).

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
| `scripts/overlap_baseline.py` | Chance baseline for the overlap flag (diagnostic; does not change flags). |
| `scripts/build_run_card.py`, `scripts/build_site.py` | Compose `evidence/run_card.json` and the Pages site from the JSON. No number is typed by hand. |
| `registry/` | `sources.json` (official links with access status), `irregularities.json`, `limitations.json`. |
| `docs/` | GitHub Pages site (`index.html`, `submission.html`, `evidence.html`, `data/`, `research/`). |
| `docs/research/hypotheses.md` | Ranked hypotheses H1–H4 (H4 rejected). |
| `docs/research/gemsdoe32.md` | Analysis of the 0.2778 file: what is measured and what is an owner claim. |
| `tests/` | `test_metric.py` (metric checks), `test_submission.py` (validator and nodata regression). |

## Reproduce

```bash
python -m venv /tmp/venv && /tmp/venv/bin/pip install numpy rasterio scipy scikit-learn pyproj matplotlib pytest
/tmp/venv/bin/python scripts/fetch_data.py                      # verified inputs to /tmp/gems53-data
/tmp/venv/bin/python -m pytest -q tests/
/tmp/venv/bin/python scripts/exp1_leakage_canary.py --data-dir /tmp/gems53-data
/tmp/venv/bin/python scripts/exp2_holdout_arms.py --data-dir /tmp/gems53-data
/tmp/venv/bin/python scripts/exp3_build_submission.py --data-dir /tmp/gems53-data --arm bands --q 0.02 --name gems53-hgb-bands --outdir /tmp/gems53-held
# shared template validator (in the GEMSDOE template clone):
#   python scripts/validate_submission.py --pred /tmp/gems53-held/gems53-hgb-bands-q0p02-nan.tif --sample /tmp/gems53-data/sample_submission.tif --train /tmp/gems53-data/training_features.tif
/tmp/venv/bin/python scripts/build_run_card.py && /tmp/venv/bin/python scripts/build_site.py
```

The candidate raster (49 MB) is kept outside the repository (`/tmp/gems53-held/`). Its sha256 is in `evidence/candidates/` and in the run card.

## Where to look next

- Limitations and remaining work: `docs/evidence.html#limitations` and `registry/limitations.json`.
- Irregularities for manual review: `registry/irregularities.json`.
