# GEMSDOE53 — GEMS Prize research workspace (DrivenData competition 306)

> **Session start:** read this README first, then `docs/prompt/` (the verbatim prompt) and the status section.

## ⬇ Download the GeoTIFF (read the label first)

**Label: DO-NOT-SUBMIT.** The file is valid and downloadable for review. It is **not** cleared for a submission slot.
It fails the pre-registered uniqueness gate (G5). Dot-level flags are density artefacts (chance lift ≤ 1.35), but the pre-placement surface shares its top-ranked pixels with two team files far above chance (lift 3.6 and 5.6). So it is not cleared under a chance-corrected rule either. See the status section.

- File: [`submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif`](submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif)
- Comment (≤140 characters): [`submissions/SUBMISSION_COMMENT.txt`](submissions/SUBMISSION_COMMENT.txt)
- Executive summary and how-to-submit steps: [`docs/index.html`](docs/index.html) (GitHub Pages site, `docs/`)

## Status (2026-10-08)

- **Candidate:** H2, a label-free magnetic lineament score (ridge and valley centrelines on the reduced-to-pole field, band 2), packed into 44,090 binary dots at ≥ 2.8 px spacing.
- **Holdout (HOLDOUT-DTI, proxy, 5 folds, shared template evaluator, 95% t-CI df 4):** pooled **0.050097** (CI 0.042504 to 0.057716) at 44,090 dots, against 0.026547 for the 19-band HGB at the same budget, and 0.035233 for the repo's frozen best. Paired difference +0.023615 (CI 0.016962 to 0.030269). Source: `evidence/x2_ridge_holdout.json`.
- **Leakage canary (G3):** worst single ridge feature separability 0.559 (gate 0.90). Source: `evidence/x1_ridge_canary.json`.
- **Format (G4):** passes the shared writer, the shared conformance gate and `scripts/validate_submission.py` (all exit 0). Finite 0/1 inside the official footprint, NaN exactly outside.
- **Uniqueness (G5): FAIL, at two levels.** Byte-level: no exact duplicate. Rank correlation of our dots with every compared registry raster is ≤ 0.09. Dot level: 66 registry rows exceed 70% of our dots within 3 px, but every one has a chance lift of at most 1.35 (density artefacts; the worst is the 5-px lattice raster, lift 1.00). Surface level: the pre-placement ridge surface shares its top-ranked pixels with two team files far above chance: GEMSDOE46 dfa-corroborated (72.9% against 20.1% chance, lift 3.6) and GEMSDOE40 eulerdepth-si0 (70.5% against 12.6%, lift 5.6). The dense GEMSDOE40 Euler map correlates 0.73 with our surface (rule is 0.90). Sources: `evidence/uniqueness_v2.json`, `evidence/overlap_baseline_v2.json`, IR-53-34.
- **Organizer score:** none exists for anything in this repository. Every number is a HOLDOUT-DTI proxy.
- **Slot selection:** none. The protocol says log and stop on a flag, so nothing was promoted.

### Second candidate on main (PR #6, from another session): H1 relay prune

- **File:** `docs/downloads/gems53-h1-relay-prune-q0p0073-nan.tif` (37,722 dots, value 1.0; NaN outside the footprint). Format checks in this session: shared template validator exit 0 and shared conformance gate exit 0 (`evidence/crosscheck_pr6_h1_format.json`).
- **Stated label on main:** `READY_TO_SUBMIT` (its own run card, `evidence/archive/pr6/`). Its holdout: pooled HOLDOUT-DTI **0.0560** (95% CI 0.0488 to 0.0631), computed with the repo's own copy `gems53.core.dti`, not the shared template evaluator. Its own uniqueness check covered 166 rasters in 12 repos (max overlap 61.79%).
- **This session's cross-check (1,200 rasters, 63 repos, same method as ours):** under the literal dot rule the file is **NOT CLEARED**. 60 registry rows exceed 70% overlap, all with chance lift between 0.996 and 1.31, so they are density artefacts (the 5-px lattice family again). A chance-corrected dot rule would clear it. Its surface-level check was **not run**, because no pre-placement surface for that file is in the repository. Sources: `evidence/crosscheck_pr6_h1_uniqueness_v2.json`, `evidence/overlap_baseline_pr6_h1.json`.
- **Holdout comparison:** H1 relay 0.0560 (0.73% of footprint) against H2 ridge 0.0501 (0.85%). The proxy favours H1 because it uses distance to visible catalogue faults, which the catalogue-truth holdout rewards by design. This is not a competition ranking (L-02, L-14).
- **Archive:** the other session's README, pages, run card and selection are kept under `docs/archive/pr6/`, `evidence/archive/pr6/`, and `docs/research/archive/`.

### Decisions needed from you

1. **Overlap rule.** A chance-corrected dot rule would clear all 66 dot-level rows (lift ≤ 1.35). It would not clear the 16 surface-level rows (lift 3.6 and 5.6), so the file stays blocked under either reading. A rule change alone does not make this file submittable. A unique file needs a different top tail, which is a new pre-registered variant and needs a decision on budget. We have not changed the rule.
2. **Verbatim prompt.** The original prompt is not in the workspace. The section below is a reconstruction (IR-53-27). Paste the verbatim text into `docs/prompt/verbatim.md`.
3. **Leaderboard figures.** 0.3774, 0.3195 and 0.2778 come from the brief, and the owner's ledger disagrees (IR-53-26). Confirm them with a dated official read.
4. **Radiometric data (H6).** Provide the grids or allow the USGS/ScienceBase host, or drop H6.
5. **Which candidate, if any.** Two files now carry different labels: H1 relay (READY_TO_SUBMIT on main, literal dot rule not cleared here) and H2 ridge (DO-NOT-SUBMIT). Neither slot is selected in this session.

## The prompt (reconstruction; not verbatim)

> The verbatim text is pending (see `docs/prompt/`, IR-53-27). The items below restate the user's request in the user's terms. They are not a quotation.

1. Make a **unique, downloadable GeoTIFF** for DrivenData GEMS competition 306 that scores above the current bar (user-reported public leaderboard: 0.3774 at #1, 0.3195 at #7, 0.2778 at #13; unverified, IR-53-26). It must pass the portal check "Predicted values must be in range [0, 1]" and match CRS, shape and transform. Single band, values in [0, 1], a unique name and a comment of at most 140 characters. Do not copy a previous submission except to learn from it. It must be obvious whether downloading and submitting the file is allowed.
2. Explain why GEMSDOE32 (0.2778 claim) scored high, and whether we can beat it.
3. Give a formal diagnosis of GEMSDOE29 leakage, and audit every feature for leakage with learn-predict separation.
4. Generate 3–5 untried geological hypotheses, rank them by expected DTI gain and cost, and validate the top one on a spatially blocked holdout before any submission slot is used.
5. Add an executive summary page (how to submit, the name and the comment) at the top of the GitHub Pages site, with the download link at the top.
6. Put the full prompt into this README and read it at the start of each session.
7. Build a clean GitHub Pages site with sourced links, a JSON run card and a data inventory table.
8. Create a pull request and merge it to `main`, then list the remaining work and limitations.
9. Run three passes: implement, review, re-check.

Standing rules recorded with the task:
- No manual input; work autonomously. Verify line by line against official sources, with links. Flag irregularities. No hallucinations.
- Parallel-run protocol: stay in one method lane. Log a duplicate and stop if rank correlation with any registry raster is above 0.90, or if more than 70% of our dots fall within 3 px of another file's dots. Use the shared template tools. Do not keep a private fork; fix shared tools once in the template and report it.
- Label every number **HOLDOUT-DTI** (evaluator, withheld positives, 95% CI) or **ORGANIZER-CONFIRMED** (from a submission receipt). Projections are never written as scores.
- Leakage canary: a single feature with holdout separability above 0.90 is leakage until proven otherwise (separability = max(AUC, 1 − AUC)).
- End with one JSON run card (`evidence/run_card.json`).
- Budget: stop after 3 experiments or 2 hours. Do not select submissions. Promotion is a separate step within the weekly cap.
- Use only free, official data sources without DrivenData login; flag any that are missing.

## Protocol (how to read the numbers)

| Label | Meaning |
|---|---|
| HOLDOUT-DTI | Our hide-and-recover proxy: whole fault segments withheld, the official distance-weighted Tversky (α 0.2, β 0.8, 300 m kernel) from the template's shared evaluator, 5 folds, t-based 95% CI (df 4). The truth is the public catalogue, not the competition's new faults, so it is **not comparable** with the leaderboard. |
| ORGANIZER-CONFIRMED | Only from a portal receipt. None exists yet. |
| MEASURED | Computed in this repository from files, at build time. |
| USER-REPORTED | A score from the brief or a ledger, not checked against an official dated read. |
| OWNER-CLAIM | Stated on another team's own page or repo; not verified. |

## Layout

| Path | What it is |
|---|---|
| `submissions/` | The candidate GeoTIFF (committed on purpose; `.gitignore` has an explicit exception) and its comment. |
| `docs/index.html` | Executive summary: download, how to submit, name and comment, answers, labels. |
| `docs/submission.html` | The file's checks, the gates and the uniqueness result. |
| `docs/evidence.html` | Experiments, GEMSDOE29 and GEMSDOE32 analysis, registry check, irregularities, limitations, sources. |
| `docs/research/hypotheses.md` | Ranked hypotheses: H2 (tested here), H5, H3, H6 (untried), H1 (validated in PR #6; cross-check here not cleared), H4 (rejected). |
| `docs/research/gemsdoe32.md` | The 0.2778 claim: what is verified, the mechanism we measured, and whether we can beat it. |
| `docs/leakage-review.md` | GEMSDOE29 leakage diagnosis and the measured feature audit. |
| `docs/prompt/` | Verbatim prompt placeholder (IR-53-27). |
| `src/gems53/ridge.py` | The H2 candidate (label-free; pinned by hash in the pre-registration). |
| `src/gems53/core.py` | Earlier in-lane helpers (folds, features, earlier metric). Verified against the shared metric by `tests/test_ridge.py`. |
| `scripts/fetch_data.py` | Re-fetches the competition rasters from the template's split blobs and checks sha256 (writes to `/tmp/gems53-data`). |
| `scripts/fetch_registry.py` | Enumerates the public GEMS repos and downloads every TIF/ZIP to `/tmp/gems53-registry`, with a manifest (`evidence/registry_manifest.json`). |
| `scripts/x1_ridge_canary.py` | X1: leakage canary for the ridge features (`evidence/x1_ridge_canary.json`). |
| `scripts/x2_ridge_holdout.py` | X2: pre-registered holdout, H2 vs HGB vs unpacked ablation (`evidence/x2_ridge_holdout.json`). |
| `scripts/x3_build_candidate.py` | X3: builds the GeoTIFF with the shared writer, runs the shared validators and the uniqueness check. |
| `scripts/uniqueness_check.py` | Registry check, version 2 (`evidence/uniqueness_v2.json`). |
| `scripts/overlap_baseline.py` | Chance baseline for the overlap flag (diagnostic; does not change flags) (`evidence/overlap_baseline_v2.json`). |
| `scripts/exp1_leakage_canary.py`, `scripts/exp2_holdout_arms.py` | Earlier experiments E1 and E2 (kept for the record). |
| `scripts/build_run_card.py`, `scripts/build_site.py` | Compose `evidence/run_card.json`, `evidence/parallel-run-card.json` and the Pages site from the JSON. No number is typed by hand. |
| `registry/` | `sources.json` (S1–S24), `irregularities.json` (IR-53-01 to IR-53-33), `limitations.json` (L-01 to L-19). |
| `tests/` | `test_metric.py`, `test_submission.py`, `test_ridge.py` (ridge behaviour and metric parity with the shared template). |

## Reproduce

```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install numpy scipy scikit-learn rasterio pyproj matplotlib pytest
/tmp/venv/bin/python scripts/fetch_data.py                                  # verified inputs to /tmp/gems53-data
git clone --depth 1 https://github.com/buffedlizard55-lab/GEMSDOE.git /tmp/gems-template   # shared template (commit dcbbb19)
/tmp/venv/bin/python -m pytest -q tests/
/tmp/venv/bin/python scripts/fetch_registry.py --dest /tmp/gems53-registry   # ~1,200 public rasters, ~1.6 GB
/tmp/venv/bin/python scripts/x1_ridge_canary.py --data-dir /tmp/gems53-data
/tmp/venv/bin/python scripts/x2_ridge_holdout.py --data-dir /tmp/gems53-data --template /tmp/gems-template
/tmp/venv/bin/python scripts/x3_build_candidate.py --data-dir /tmp/gems53-data --template /tmp/gems-template --registry /tmp/gems53-registry
/tmp/venv/bin/python scripts/overlap_baseline.py
/tmp/venv/bin/python scripts/build_run_card.py && /tmp/venv/bin/python scripts/build_site.py
```

Earlier runs (E1, E2 and the blocked 2026-09 candidate) are kept in `evidence/` for the record. Their numbers are
reproduced by the shared evaluator (`evidence/x2_ridge_holdout.json`, `E2_reproduction_hgb_top_q`).
