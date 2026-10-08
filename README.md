# GEMSDOE53 — GEMS Prize research workspace (DrivenData competition 306)

> **Read this first, at the start of every session.** Then read the status below, then the protocol.

## Core values (focal points)

- **Maximize P(Win).** Every experiment and every scarce submission slot is chosen for its expected contribution to a valid, defensible result, not for novelty.
- **Own the Outcome.** Report defects and negative results plainly. Fix shared systems where permitted. A successful file write is not proof of scientific validity or of organizer acceptance.

## Status (2026-10-08)

| Item | Value |
|---|---|
| Label | **RESEARCH-ONLY / DO NOT SUBMIT** (decided by the pre-registered gates, see `docs/submissions/CURRENT.json`) |
| File | [`docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif`](docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif) (443,170 bytes) |
| Name | `gems53-h1-thin_bin_q0p1-20261008-aefc7582` |
| Comment (≤140 chars) | `RESEARCH-ONLY DO NOT SUBMIT \| GEMS53 h1 thin_bin_q0p1 \| proxy DTI 0.0040 \| not organizer-scored` |
| sha256 (file) | `a20fad19d19f62317721cb0819d4e5a7d0960a4c9bac2b1d3094563c693aeb1b` |
| OK to download? | Yes, for research and review. It is not cleared for submission. |
| OK to submit? | **No.** The uniqueness gate flags the file (below). |
| Submitted? | No. No submission slot was used, and no organizer score exists. |

**Why it is not cleared.** The file passes every format and conformance check (the shared template validator and `validate-conformant` both exit 0, all in-lane checks pass). The holdout gate passes (the paired lower bound is above 0). The uniqueness gate flags 103 of 621 unique GEMSDOE registry rasters, so the pre-registered verdict is research-only. The flags are explained in `evidence/uniqueness_diagnostics_*.json`, and they show a deeper problem with the gate: on this registry, the raw 70% overlap rule cannot be satisfied by any placement. A GEMSDOE13 lattice raster covers 99.87% of the footprint within 3 px (**IR-53-46**). Rho flags depend on the method and disappear on the footprint (**IR-53-47**). Fixing this needs a decision by you (see "Decisions needed").

## Other files in this repository (other sessions; not ours)

Other sessions merged their work into `main` while this session ran (PRs #5, #6, #7). Their files are kept, and their labels are quoted from their own receipts. Our gate was run on the same registry (623 unique rasters, the 621 from our rebuild plus the three rasters added since, minus the file under test).

| File | Label in its own receipt | Our gate (full registry) |
|---|---|---|
| `docs/downloads/gems53-h1-relay-prune-q0p0073-nan.tif` (PR #6) | `READY_TO_SUBMIT` in its archived run card (`evidence/archive/pr6/run_card_pr6_h1.json`). The same session's README on `main` says the literal dot rule does **not** clear it. | **Flagged**: 82 registry rasters (`evidence/uniqueness_gate_other-session_h1_relay.json`). |
| `submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif` (PR #7) | `DO-NOT-SUBMIT` (`evidence/x3_candidate_receipt.json`) | **Flagged**: 86 registry rasters (`evidence/uniqueness_gate_other-session_h2_ridge.json`). |

**Do not upload the H1 relay file on the strength of its archived `READY_TO_SUBMIT` label.** The label predates that session's own cross-check, and under the pre-registered rule it is not cleared. The cause is the same as for our file: a lattice raster and dense rasters in the registry (IR-53-46, IR-53-48). Three candidate files now carry three different positions, and none is cleared by the pre-registered rule.

## Merge notes (2026-10-08)

- The branch was merged with `origin/main` (other sessions' PRs #5 to #7). All of `main`'s files are kept. Where this session regenerates a page or script that `main` also overwrote, the `main` version is archived: `docs/archive/main-2026-10-08/`, `scripts/archive/main-2026-10-08/`, `evidence/archive/main-2026-10-08/`.
- Identifier collisions were resolved in favour of `main`'s numbering. This session's irregularities are now IR-53-37 to IR-53-48 (were IR-53-19 to 30), limitations L-20 to L-27 (were L-11 to 18), and sources S25 to S28 (were S19 to 22). This session's hypothesis H6 (trend prior) is now H7, because `main` uses H6 for its radiometric hypothesis (IR-53-35).
- Name collision in `src/gems53/core.py`: this session's segment-exact distance function is `h1_segment_exact_distance`. `main`'s `segment_exact_distance_grid` (its own signature) is unchanged for its scripts.
- The GEMSDOE53 repository is itself a `GEMSDOE*` repository and is part of the registry. Its three files on `main` are included in the comparison above.

## Verbatim prompt

**Not available in this workspace (IR-53-38).** The verbatim user message was never stored here, and this session has only a condensed record of it. The text below is therefore a recorded summary, not a verbatim copy. **Please paste the verbatim prompt into this section.** Nothing has been reconstructed or invented to fill the gap.

<details><summary>Recorded requirements (summary, not verbatim)</summary>

1. Produce a unique, downloadable GeoTIFF for DrivenData GEMS (DOE) competition 306, in the required format (single band, float32, EPSG:32611, 100 m, same shape and transform as the sample, values in [0,1], NaN outside the footprint), with a unique name and a comment of at most 140 characters. It must be obvious whether downloading and submitting the file is allowed. Do not copy a previous submission except for learning.
2. Explain why GEMSDOE32 H33-2-B2 (0.2778) scored high, and whether a higher-scoring file is possible. Use only verified sources and label owner claims as owner claims.
3. Diagnose the GEMSDOE29 leakage formally, citing learn-predict separation (Kaufman et al.). Audit each feature with the canary rule (single-feature separability above 0.90 counts as leakage until proven otherwise).
4. Generate 3–5 untried geological hypotheses, rank them by expected DTI gain and cost, and validate the top one on a spatially blocked holdout before spending any submission slot.
5. Add an executive-summary page at the top of the GitHub Pages site, explaining how to submit, including the name and comment fields.
6. Read the prompt at the start of every session. Keep the Core Values as focal points.
7. Parallel-run protocol: stay in one lane. Stop after 3 experiments or 2 hours. Stop if rank correlation with a registry raster exceeds 0.90, or if more than 70% of dots fall within 3 px of one registry raster. Reuse shared template tools; do not keep a private fork.
8. Label every number HOLDOUT-DTI (evaluator version, withheld positives, 95% CI) or ORGANIZER-CONFIRMED. Never write a projection as a score. End with one JSON run card.
9. Create a PR into `main` and merge it. List remaining work and limitations. Flag irregularities. No manual input. No hallucinations; verify with official links.

</details>

## What was done in this session (three experiments, pre-registered)

Pre-registration (committed before the runs): [`docs/research/preregistration-2026-10-08.md`](docs/research/preregistration-2026-10-08.md), with deviations DEV-1 (the holdout design) and DEV-1b (a stage-2 code bug, IR-53-45) logged in section 9.

| Experiment | What | Result (labels as stated) |
|---|---|---|
| E1 (design A, reference only) | Exploration on segment folds with the first negative pool | **Not used for decisions.** Its negative pool depended on withheld labels (IR-53-37). Reproduction of the earlier exp2 numbers: PASS. Metric parity with the shared template `src/metrics.py`: PASS (difference 1.3e-13). |
| E2 (design B) | Stage 1: 24 variants on segment folds (seed 53, 5 folds, 10 px buffer). Stage 2: paired spatial confirmation on contiguous super-regions (template `src/blocks.py`). | Baseline bands top-q 0.02: **HOLDOUT-DTI 0.0106** (95% CI 0.0083 to 0.0128; 60,988 withheld positives in 3,199 segments). Stage-1 selection, H1 with binary thinning at q 0.10: **HOLDOUT-DTI 0.1413** (CI 0.1338 to 0.1489; selected on these folds, so optimistic). Stage-2 spatial: baseline **0.0001**, selected **0.0040**, paired mean difference **+0.0035** (CI +0.0006 to +0.0064). Accepted by the rule. |
| E3 (build) | Train on all known faults; write with the shared template writer; validate; uniqueness gate on 621 unique registry rasters; label | 56,605 dots (from 516,737 candidates before thinning). Validators PASS. Canary: bands max separability **0.5912** (band 7), H1 **0.7680**, both below the 0.90 gate. Uniqueness: **flagged**. Label: **Research-only / DO NOT SUBMIT**. |

Every holdout number above is **HOLDOUT-DTI** (evaluator `gems53.core.dti` v1.0.0, parity with the template metric). None is **ORGANIZER-CONFIRMED**.

## Answers (short)

- **GEMSDOE29 leakage.** Confirmed and formally diagnosed (`docs/leakage-review.md`). Its distance-to-known-faults feature is built from the full label raster, so it is exactly 0 on every known-fault pixel (separability 1.0). Learn-predict separation is the fix. The write-up now also records our own holdout leak (IR-53-37), which is corrected to design B.
- **GEMSDOE32 H33-2-B2 (0.2778).** Measured on the registry copy (`evidence/gemsdoe32_measured.json`): 37,654 dots (0.73% of the footprint); **0.0%** within 2 px of a mapped fault, which confirms the owner's pruning claim; median nearest-dot distance **3.0 px**, the metric radius (the same structure that thinning produces). Owner claims (0.2708 base, no organizer score) are labelled as owner claims. The link from the 0.2778 row to this file is **not established** (IR-53-02). The file's `zeros` variant fills the whole grid with 0 (IR-53-41).
- **Can we beat 0.2778 / 0.3774?** Not shown. We have no organizer score for any file here. The leaderboard values are the repository's snapshot (IR-53-01): #1 0.3774 (xiaofanhu), #7 0.3195 (DARD), #13 0.2778 (extradr19). The request named 0.3195 as the top score, and the snapshot disagrees.
- **Hypotheses.** Ranked in [`docs/research/hypotheses.md`](docs/research/hypotheses.md). H1 (segment-exact distance) and M1 (metric-aware thinning) were tested. H3 is blocked because the public strain data have no orientation (IR-53-40). H4 is rejected. H2, H5 (thermal and paleo-geothermal evidence from a pinned mirror) and H7 (regional trend prior) remain untested. The budget is used up.

## Decisions needed (not made here)

0. **Which candidate, if any.** Three files carry different positions (this session's research-only file, the other sessions' `READY_TO_SUBMIT` H1 relay, and the `DO-NOT-SUBMIT` H2 ridge). None is cleared by the pre-registered rule. No slot is selected.

1. **The uniqueness gate (IR-53-46, IR-53-47, IR-53-48).** Choose a registry scope that counts submission-type dot maps only, a chance-corrected overlap rule (lift over chance), and a footprint-only rank correlation. Any such change needs explicit approval and a fresh pre-registered gate run. Until then, no candidate from this repository can be labelled OK to submit (L-27).
2. **Verbatim prompt (IR-53-38).** Paste the original text into the section above.
3. **Slot selection.** Not made. Promotion is a separate selector step within the weekly cap.

## Protocol (how to read the numbers)

- Labels: HOLDOUT-DTI (proxy) or ORGANIZER-CONFIRMED (receipt only). Projections are never scores.
- Leakage canary: a single feature with separability above 0.90 counts as leakage until proven otherwise (separability = max(AUC, 1 − AUC)).
- Holdouts: design B (IR-53-37, DEV-1). Negatives are every footprint pixel that is not a visible fault, so the training pool does not depend on withheld labels.
- Shared tools: the GEMSDOE template at commit `dcbbb192e56b2b32c0a131eba791dc363305d4a3` (imported by file path, never copied). Two protocol names do not exist in the template (`evaluate_holdout.py`, `submission_writer.py`), and the mapping is recorded (IR-53-39).
- Budget: 3 experiments and 2 hours. E1 started 2026-10-08 22:04:10 UTC (from the E1 receipt). Times are read from the receipts, not estimated.

## Layout

| Path | What |
|---|---|
| `docs/index.html` | Executive summary (top of the Pages site): label, download, name and comment, how to submit, answers |
| `docs/submission.html` | The file: gates, validators, in-lane checks, uniqueness receipt and diagnostics |
| `docs/evidence.html` | E1 and E2 tables, canary, GEMSDOE29 and GEMSDOE32, hypotheses, irregularities, limitations, sources |
| `docs/submissions/` | The candidate GeoTIFF and `CURRENT.json` (the single status pointer) |
| `docs/research/` | Pre-registration, hypotheses |
| `docs/leakage-review.md` | GEMSDOE29 formal diagnosis, with the design-B update |
| `evidence/e1_h1_thin_holdout.json` | E1 record (design A, reference) |
| `evidence/e2_leakfree_holdouts.json` | E2 record (design B, stages 1 and 2) |
| `evidence/candidate_*.json` | E3 receipt (decision, gates, validators, in-lane checks) |
| `evidence/uniqueness_gate_*.json` | Uniqueness gate receipt (all 621 registry rasters) |
| `evidence/uniqueness_diagnostics_*.json` | Diagnostics that explain the flags (not a gate) |
| `evidence/gemsdoe32_measured.json` | Measured structure of the GEMSDOE32 registry files |
| `evidence/run_card.json` | The run card (one JSON) |
| `evidence/superseded/` | Invalid output kept for the record (E2 stage 2 before the DEV-1b fix) |
| `evidence/previous-session/` | Earlier session outputs (design A canary and holdout, the blocked candidate); superseded |
| `registry/` | `irregularities.json` (IR-53-01 to 30), `limitations.json` (L-01 to 18), `sources.json` (S1 to 22) |
| `src/gems53/core.py` | Lane library: loaders, folds, H1 segment-exact distance, M1 thinning, template loader, DTI |
| `scripts/` | `fetch_data.py`, `e1_h1_thin_holdout.py`, `e2_leakfree_holdouts.py`, `e3_build_candidate.py`, `uniqueness_gate.py`, `uniqueness_diagnostics.py`, `measure_gemsdoe32.py`, `build_run_card.py`, `build_site.py` |
| `tests/` | `test_h1_thin.py` (brute-force checks of H1 and M1, and metric parity), `test_metric.py`, `test_submission.py`, `test_outputs.py` (re-check of the shipped file and the site) |

## Reproduce

```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install numpy rasterio scipy scikit-learn pyproj matplotlib pytest
git clone --depth 1 https://github.com/buffedlizard55-lab/GEMSDOE.git /tmp/gems-template   # shared template, commit dcbbb19
/tmp/venv/bin/python scripts/fetch_data.py --data-dir /tmp/gems53-data                      # sha256-pinned competition rasters
/tmp/venv/bin/python scripts/e1_h1_thin_holdout.py                                          # E1 (design A, reference)
/tmp/venv/bin/python scripts/e2_leakfree_holdouts.py                                        # E2 (design B)
/tmp/venv/bin/python scripts/e3_build_candidate.py --registry /tmp/g53/uniq                 # E3 (needs the registry rebuilt; see IR-53-43)
/tmp/venv/bin/python scripts/build_run_card.py && /tmp/venv/bin/python scripts/build_site.py
/tmp/venv/bin/python -m pytest -q tests
```

The GEMSDOE* registry is rebuilt from the GitHub repositories (`scripts/uniqueness_gate.py` reads a directory of TIFs; the copy loop is described in the run card). Its 1.3 GB are not committed.

## Remaining work

1. Decide the gate definition (Decisions needed, item 1). Then re-run the uniqueness gate with a fresh pre-registration.
2. Test H5 (INGENIOUS 2 m temperature probes, paleo-geothermal deposits, wells and springs) on the segment and spatial holdouts. Verify the licence first (IR-53-44).
3. Test H2 (magnetic ridges on the native GeoDAWN grids) and H7 (regional trend prior).
4. Build a non-catalogue validation population so that holdout gains are not catalogue-proximity gains (IR-53-42, L-22).
5. Seed replicates and a model-variance estimate (L-25).
6. Get a portal receipt for any file before any ORGANIZER-CONFIRMED claim (none exists).
7. Paste the verbatim prompt (IR-53-38).

## Limitations

See `registry/limitations.json` (L-01 to L-27). The main ones: no organizer score exists; the holdout truth is the catalogue (proximity-dominated, IR-53-42); egress is limited to GitHub and PyPI, so USGS, ScienceBase, OSTI and GDR cannot be reached; compute is 2 vCPU with no GPU; the shared template's CNN pipeline was not run.

## Irregularities

See `registry/irregularities.json`. Open items that change a decision: IR-53-01 (leaderboard conflict), IR-53-02 (0.2778 not linked to a file), IR-53-16 (the 70% rule), IR-53-37 (design A leak, corrected), IR-53-38 (verbatim prompt missing), IR-53-40 (H3 blocked), IR-53-42 (catalogue-proximity holdout), IR-53-46 (the raw overlap rule is unsatisfiable on this registry).
