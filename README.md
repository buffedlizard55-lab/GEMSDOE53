# GEMSDOE53 — GEMS Prize research workspace (DrivenData competition 306)

> **Read this first, at the start of every session.** Then read the status below, then the protocol. The full prompt capture is at the end of this README and in [`docs/prompt/verbatim.md`](docs/prompt/verbatim.md).

## Core values (focal points)

- **Maximize P(Win).** Every experiment and every scarce submission slot is chosen for its expected contribution to a valid, defensible result, not for novelty.
- **Own the Outcome.** Report defects and negative results plainly. Fix shared systems where permitted. A successful file write is not proof of scientific validity or of organizer acceptance.

## Status (2026-10-08)

**Short answer: no file from this repository is cleared for submission.** Every file here is research-only. The pre-registered uniqueness gate flags each one, and no organizer score exists for any of them.

| Item | Value |
|---|---|
| Current pointer | `docs/submissions/CURRENT.json` (single status pointer) |
| Label | **RESEARCH-ONLY / DO NOT SUBMIT** |
| File | [`docs/submissions/gems53-s3-bands-top_q0p02-20261009-e67cda00.tif`](docs/submissions/gems53-s3-bands-top_q0p02-20261009-e67cda00.tif) (828,867 bytes). Pre-registered frozen control, not a recommendation. |
| Name (unique) | `gems53-s3-bands-top_q0p02-20261009-e67cda00` |
| Comment (≤140 chars, 107 used) | `RESEARCH-ONLY DO NOT SUBMIT \| GEMS53-S3 bands top_q0p02 \| HOLDOUT-DTI spatial 0.0001 \| not organizer-scored` |
| sha256 (file) | `e746ae6f8028f619bc7ab2a3f848afaf12953a2fa37fe09cb9b1f38060fdb79c` |
| sha256 (pixels, nan→−1, float32 LE) | `e67cda00dd865299b1a7f6a8e635651a78923dc9ca09a78e6459f17b0b3edebd` |
| OK to download? | **Yes, for research and review only.** It is not cleared for submission. |
| OK to submit? | **No.** The pre-registered uniqueness gate fails for this file. |
| Submitted? | No. No submission slot was used. `organizer_score` is null. |

**What the file is.** The pre-registered frozen control (E2 design B, bands top-q 0.02). It is a control, not a recommendation. Its HOLDOUT-DTI proxy is 0.000102, far below H1 `thin_bin_q0p1` (0.004049) on the same proxy (IR-53-60). It passes every format check; see `docs/submission.html`.

**Why it is not cleared.** The uniqueness gate (pre-registered rule, unchanged) flags 172 of 628 unique GEMSDOE registry rasters: 170 by the 70% within-3-px overlap rule and 52 by whole-grid surface rho. The overlap flags come from sparse lattice dot maps that cover 99.87% of the footprint by chance, so no placement can pass the raw 70% rule on this registry (IR-53-46). The surface rho flags disappear on the footprint (0 of 52; IR-53-47). None of the final dots has rho above 0.90 on any basis. Changing the gate needs an explicit decision.

**Previous pointer (H1, regenerated on `main` by PR #9).** [`docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif`](docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif) (445,801 bytes, sha256 `aeaa9a46236a658d91a05be48d54f14b44804c967d590314caeb2c0a82511f60`). Label: **RESEARCH-ONLY / DO NOT SUBMIT**. Its comment: `RESEARCH-ONLY | HOLDOUT-DTI 0.0040; g53 DTI v1.0, withheld=60,988; Δ+0.0035 CI95 +0.0006..+0.0064; NOT ORGANIZER-SCORED | DO NOT SUBMIT`. The uniqueness verdict in its own receipt is **PROTOCOL DUPLICATE / STOP**: 99.599% of its final dots are within 3 px of the GEMSDOE13 `r13-lattice-s5_v2` raster (threshold 70%; chance coverage 99.87%, lift 0.9973), and the whole-grid pre-placement surface-rho maximum is 0.953943 (>0.90). This is not a claim of byte-identical predictions. The `*_refresh.json` file is a partial 3-raster check, not the canonical verdict (IR-53-49). The H1 file is no longer the pointer; it is kept for the record.

## Decisions needed (not made here)

1. **Gate definition (IR-53-46, IR-53-47, IR-53-48).** Approve or reject a footprint-only, chance-corrected overlap rule, and a registry scope that counts submission-type dot maps. Then re-run the gate under a fresh pre-registration. Until then, no file from this repository can be labelled OK to submit (L-27).
2. **Candidate choice (IR-53-60).** H1 `thin_bin_q0p1` has the higher holdout proxy (0.0040) but also fails the gate, and the S3 control file is weaker (0.0001). Decide which candidate, if any, should be tested under a changed gate.
3. **Next experiment.** H12 (potential-field edge coincidence) is recommended for spatially blocked validation. It has not been run: this session used its three-experiment cap (S3-A, S3-B, S3-C).
4. **Slot selection.** Not made. Promotion is a separate selector step within the weekly cap (three per week, NLR rules §3.4).
5. **Verbatim prompt (IR-53-27, IR-53-38).** `docs/prompt/verbatim.md` is a normalized capture, not a byte-for-byte transcript. Confirm it against your original message, or supply the exact text.
6. **Deadline (IR-53-55).** Confirm the exact deadline on the competition page. NLR Appendix A.1 says 5:00 p.m. ET; the template guide says 11:59 pm UTC on Dec 3, 2026.
7. **Leaderboard conflict (IR-53-01).** The prompt says 0.3774 (line 49) and also 0.3195 "is the highest score right now" (line 449). The repository snapshot says #1 0.3774. Confirm the value from the official page yourself; we do not scrape the live leaderboard (DrivenData Terms).

## Other files in this repository (other sessions; not ours)

Other sessions merged their work into `main` (PRs #5 to #9). Their files are kept, and their labels are quoted from their own receipts. Our gate was run on the same registry (623 unique rasters, the 621 from our rebuild plus the three rasters added since, minus the file under test). The S3 gate used 628 unique rasters on the grid.

| File | Label in its own receipt | Our gate (full registry) |
|---|---|---|
| `docs/downloads/gems53-h1-relay-prune-q0p0073-nan.tif` (PR #6) | `READY_TO_SUBMIT` in its archived run card (`evidence/archive/pr6/run_card_pr6_h1.json`). The same session's README on `main` says the literal dot rule does **not** clear it. | **Flagged**: 82 registry rasters (`evidence/uniqueness_gate_other-session_h1_relay.json`). |
| `submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif` (PR #7) | `DO-NOT-SUBMIT` (`evidence/x3_candidate_receipt.json`) | **Flagged**: 86 registry rasters (`evidence/uniqueness_gate_other-session_h2_ridge.json`). |

**Do not upload the H1 relay file on the strength of its archived `READY_TO_SUBMIT` label.** The label predates that session's own cross-check, and under the pre-registered rule it is not cleared. None of the candidate files in this repository is cleared by the pre-registered rule.

## Merge notes (2026-10-08)

- **PR #10 (this branch) merged with `main` (PR #9, commit `acb44b6`).** The conflicts were resolved as follows. Registry IDs that already existed on `main` keep `main`'s text. Our non-colliding entries are kept, and our colliding entries are renumbered: irregularity band-18 item IR-53-49 → IR-53-63; limitations L-28/L-29 → L-36/L-37; sources S29–S32 → S40–S43. Counts after the merge: irregularities 63 (IR-53-01 to IR-53-63), limitations 37 (L-01 to L-37), sources 43 (S1 to S43). The H1 file and its receipts on `main` are the regenerated versions; the S3 control is our pointer.
- The branch was earlier merged with `origin/main` (other sessions' PRs #5 to #7). All of `main`'s files are kept. Where this session regenerates a page or script that `main` also overwrote, the `main` version is archived: `docs/archive/main-2026-10-08/`, `scripts/archive/main-2026-10-08/`, `evidence/archive/main-2026-10-08/`.
- Identifier collisions from that earlier merge were resolved in favour of `main`'s numbering: this session's hypothesis H6 (trend prior) is now H7, because `main` uses H6 for its radiometric hypothesis (IR-53-35).
- Name collision in `src/gems53/core.py`: this session's segment-exact distance function is `h1_segment_exact_distance`. `main`'s `segment_exact_distance_grid` (its own signature) is unchanged for its scripts.
- The GEMSDOE53 repository is itself a `GEMSDOE*` repository and is part of the registry. Its three files on `main` are included in the comparison above.

## Prompt and session charter (read in full at every session start)

Before project work, read this README (including the prompt in the section at the end) and [`docs/prompt/verbatim.md`](docs/prompt/verbatim.md) in full, then check `docs/submissions/CURRENT.json`, `evidence/run_card.json`, and the experiment budget. The prompt holds the operational requirements: leakage-safe learn-predict separation; one lane; per-feature canaries (single-feature separability above 0.90 counts as leakage until proven otherwise); no more than three experiments or two hours; pooled DTI and uncertainty; strict registry checks before and after placement; a unique name and an optional comment of at most 140 characters; a visible download link; and an explicit do-not-submit state when any gate fails.

**Capture status:** `docs/prompt/verbatim.md` is a **normalized capture** of the operative request, not a byte-for-byte transcript; repeated paragraphs were consolidated and the supplied score list is not an official leaderboard receipt. No exact wording or score provenance is inferred. IR-53-27 and IR-53-38 remain open until a genuine full transcript is stored. The local summary is not a substitute for the prompt's stop rules.

## Review outcome (2026-10-08; no new experiment)

- The H1 candidate TIF (now the previous pointer) exists and is downloadable for review, but **must not be submitted**. It fails the raw duplicate rule. Its filename is an identifier, not proof of raster uniqueness.
- The H1 TIF was re-opened and validated against the cached competition sample using shared template commit `dcbbb192e56b2b32c0a131eba791dc363305d4a3`: single-band float32, EPSG:32611, 3730×3292, 100 m, exact transform/footprint, NaN outside only, values in [0,1], nodata=NaN. Both shared validators returned exit 0.
- Competition data were fetched to `/tmp/gems53-data` by `scripts/fetch_data.py` from the public GitHub mirror and matched its pinned hashes (S7). This verifies the mirror against its manifest, **not** against a direct DrivenData download. No data were added to Git.
- Prior hypotheses H2 (magnetic Hessian ridges), H5 (thermal/paleo geothermal evidence), and H7 (strike/trend priors) are not all novel: H2 is already implemented in this repo and related H5/H7 methods occur in the public GEMSDOE inventory. H2 was tested only under the invalid design A (X2), not rerun (IR-53-37).

## What was done in this session (three experiments, pre-registered)

Pre-registrations: [`docs/research/preregistration-2026-10-08.md`](docs/research/preregistration-2026-10-08.md) (E1–E3, with deviations DEV-1 and DEV-1b in section 9) and [`docs/research/preregistration-2026-10-08-S3.md`](docs/research/preregistration-2026-10-08-S3.md) (S3-A to S3-C, H8).

| Experiment | What | Result (labels as stated) |
|---|---|---|
| E1 (design A, reference only) | Exploration on segment folds with the first negative pool | **Not used for decisions.** Its negative pool depended on withheld labels (IR-53-37). Reproduction of the earlier exp2 numbers: PASS. Metric parity with the shared template `src/metrics.py`: PASS (difference 1.3e-13). |
| E2 (design B) | Stage 1: 24 variants on segment folds (seed 53, 5 folds, 10 px buffer). Stage 2: paired spatial confirmation on contiguous super-regions (template `src/blocks.py`). | HOLDOUT-DTI (evaluator `gems53.core.dti` v1.0.0; 60,988 withheld positives / 3,199 segments): baseline bands top-q 0.02 = **0.010562** (95% CI 0.008337–0.012812). Stage-1 selected H1 with binary thinning at q 0.10 = **0.141319** (95% CI 0.133780–0.148921; selected on these folds, optimistic). Stage-2 spatial pooled baseline **0.000102** vs selected **0.004049**; primary paired mean difference **+0.003533** (95% paired t CI +0.000619–+0.006447, df 4). The rule accepts; this remains a catalogue proxy. |
| E3 (H1 build) | Train on all known faults; write with the shared template writer; validate; uniqueness gate on 621 unique registry rasters; label | 56,605 dots (from 516,737 candidates before thinning). Validators PASS. Canary: bands max separability **0.5912** (band 7), H1 **0.7680**, both below the 0.90 gate. Uniqueness: **flagged**. Label: **Research-only / DO NOT SUBMIT**. |
| **S3-A** leakage reproduction (no selection) | Reproduce the GEMSDOE29 distance construction and test the canary | Leaky distance feature: separability **1.0** on design-B fold 0, so the canary flags it. Legitimate H1 distance on the same fold: **0.768**. Verdict: canary sensitive, leaky construction rejected. (`evidence/s3a_leakage_repro.json`) |
| **S3-B** H8 gravity-gradient ridges (band 13) | Blakely–Simpson maxima; design B; pre-registered decision rule | Stage 1 selected `thin_bin_q0p1` (0.0914, segment folds). Stage 2 spatial, HOLDOUT-DTI: H8 **0.00402**, H1 0.00405, bands 0.000102. Paired H8 minus H1: **+0.000424, CI [−0.003746, +0.004594]**, lower bound not above 0. Verdict: **NEGATIVE**. Canary (fold maxima): R 0.502, S 0.502, log1pD 0.572 (all pass). (`evidence/s3b_h8_holdout.json`) |
| **S3-C** build and gate | Frozen control, validators, uniqueness gate, label | Validators PASS (template validate exit 0, conformant exit 0). Final dots 103,348. Gate: 172 of 628 flagged; label **Research-only / DO NOT SUBMIT**. (`evidence/candidate_gems53-s3-bands-top_q0p02-20261009-e67cda00.json`) |

Every holdout number above is **HOLDOUT-DTI** (evaluator `gems53.core.dti` v1.0.0, checked against the official formulas on the DrivenData problem page, S36 in `registry/sources.json`: TP uses the max over the kernel, FP weights each prediction by 1 − max kernel, α = 0.2, β = 0.8, R = 3 px). No number is **ORGANIZER-CONFIRMED**. Projections are never scores.

## Answers (short)

- **GEMSDOE29 leakage.** Confirmed and diagnosed (`docs/leakage-review.md`, including S3-A). Its distance-to-known-faults feature is built from the full label raster, so it is exactly 0 on every known-fault pixel (separability 1.0). The fix is learn-predict separation: the distance must use visible faults only. The canary catches the leaky feature. Our own earlier holdout also leaked (IR-53-37); it is corrected to design B.
- **GEMSDOE32 H33-2-B2 (0.2778).** Measured on the registry copy (`evidence/gemsdoe32_measured.json`): 37,654 dots (0.73% of the footprint); **0.0%** within 2 px of a mapped fault; median nearest-dot distance **3.0 px**, the metric radius. This geometry is compatible with metric-aware thinning, but is not proof of the score mechanism. Owner claims (0.2708 base, no organizer score) are labelled as owner claims. The link from the 0.2778 row to this file is **not established** (IR-53-02). The file's `zeros` variant fills the grid with 0 (IR-53-41).
- **Can we beat 0.2778 or 0.3774?** Not shown. No organizer score exists for any file here. The leaderboard values are the repository's snapshot (IR-53-01): #1 **0.3774** (xiaofanhu), #7 **0.3195** (DARD), #13 **0.2778** (extradr19). The prompt names 0.3195 as the top score, and the snapshot disagrees. We did not scrape the live leaderboard (DrivenData terms, IR-53-51).
- **Hypotheses.** H1 (segment-exact distance) and M1 (thinning) were tested. H8 was tested and is **negative**. H2 was attempted under the invalid design-A holdout (X2) and not rerun. Untested and ranked in [`docs/research/hypotheses.md`](docs/research/hypotheses.md): **H12** (rank 1: potential-field edge coincidence, bands 13 and 3), **H10** (rank 2: basement-cover gradient maxima, band 15), **H9** (rank 3: curvature ridges, band 12). H11 (seismicity alignments) is **blocked** (the sandbox cannot reach USGS ComCat; L-31). Bands 10 and 16 already carry earthquake-derived features, so H11 may partly duplicate them (not checked). Three earlier candidates from `main` remain screened in the same file: **C1** (conductivity–magnetic cross-scale phase coherence; existing bands, not run), **C2** (ComCat-based; blocked by the same USGS reachability limit), **C3** (Landsat; needs source-access verification).

## Protocol (how to read the numbers)

- Labels: HOLDOUT-DTI (proxy) or ORGANIZER-CONFIRMED (receipt only). Projections are never scores.
- Leakage canary: a single feature with separability above 0.90 counts as leakage until proven otherwise (separability = max(AUC, 1 − AUC)).
- Holdouts: design B (IR-53-37, DEV-1). Negatives are every footprint pixel that is not a visible fault, so the training pool does not depend on withheld labels.
- Shared tools: the GEMSDOE template at commit `dcbbb192e56b2b32c0a131eba791dc363305d4a3` (imported by file path, never copied). Two protocol names do not exist in the template (`evaluate_holdout.py`, `submission_writer.py`), and the mapping is recorded (IR-53-39).
- Budget: 3 experiments and 2 hours. E1 started 2026-10-08 22:04:10 UTC (from the E1 receipt). Times are read from the receipts, not estimated.

## Layout

| Path | What |
|---|---|
| `docs/index.html` | Executive summary (top of the Pages site): the S3 file block first (download, name, comment, gates, decisions), then the H1 material |
| `docs/submission.html` | The file: gates, validators, in-lane checks, uniqueness receipt and diagnostics |
| `docs/evidence.html` | E1, E2, canaries, GEMSDOE29 and GEMSDOE32, hypotheses, irregularities, limitations, sources, run card |
| `docs/submissions/` | Candidate GeoTIFFs and `CURRENT.json` (the single status pointer; now the S3 control) |
| `docs/research/` | Pre-registrations (E-series and S3), hypotheses |
| `docs/prompt/` | `verbatim.md` (normalized prompt capture) and its README |
| `docs/leakage-review.md` | GEMSDOE29 formal diagnosis, design-B update, S3-A reproduction |
| `evidence/e1_h1_thin_holdout.json` | E1 record (design A, reference) |
| `evidence/e2_leakfree_holdouts.json` | E2 record (design B, stages 1 and 2) |
| `evidence/s3a_leakage_repro.json` | S3-A canary reproduction |
| `evidence/s3b_h8_holdout.json` | S3-B H8 holdout (stages 1 and 2, verdict) |
| `evidence/candidate_*.json` | Candidate receipts (decision, gates, validators, in-lane checks, holdout, canary, uniqueness) |
| `evidence/uniqueness_gate_*.json` | Uniqueness gate receipts (full registry) |
| `evidence/uniqueness_diagnostics_*.json`, `evidence/diagnostic_surface_rho_*.json` | Diagnostics that explain the flags (not gates) |
| `evidence/gemsdoe32_measured.json` | Measured structure of the GEMSDOE32 registry files |
| `evidence/run_card.json` | The run card (one JSON), with `s3_lane` |
| `evidence/superseded/`, `evidence/previous-session/` | Superseded outputs, kept for the record |
| `registry/` | `irregularities.json` (IR-53-01 to 63), `limitations.json` (L-01 to 37), `sources.json` (S1 to 43) |
| `src/gems53/core.py` | Lane library: loaders, folds, H1 segment-exact distance, M1 thinning, template loader, DTI |
| `src/gems53/h8.py` | H8 gravity-gradient maxima (Blakely–Simpson) |
| `src/gems53/ridge.py` | Ridge arm (earlier session) |
| `scripts/` | `fetch_data.py`, `e1_h1_thin_holdout.py`, `e2_leakfree_holdouts.py`, `e3_build_candidate.py`, `s3a_leakage_repro.py`, `s3b_h8_holdout.py`, `s3c_build_candidate.py`, `uniqueness_gate.py`, `uniqueness_diagnostics.py`, `surface_rho_footprint.py`, `measure_gemsdoe32.py`, `build_run_card.py`, `build_site.py` |
| `tests/` | `test_h1_thin.py`, `test_metric.py`, `test_submission.py`, `test_outputs.py`, `test_s3.py` |

## Reproduce

The commands below document historical reproducibility only. **Do not execute E1/E2/E3 or S3-A/B/C in this lane now**: the three-experiment budget is exhausted. A future rerun needs a fresh preregistration and budget authorization, and it must not overwrite the current receipts.

```bash
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install numpy rasterio scipy scikit-learn pyproj matplotlib pytest
git clone --depth 1 https://github.com/buffedlizard55-lab/GEMSDOE.git /tmp/gems-template   # shared template, commit dcbbb19
/tmp/venv/bin/python scripts/fetch_data.py --data-dir /tmp/gems53-data                      # sha256-pinned competition rasters
/tmp/venv/bin/python scripts/e1_h1_thin_holdout.py                                          # E1 (design A, reference)
/tmp/venv/bin/python scripts/e2_leakfree_holdouts.py                                        # E2 (design B)
/tmp/venv/bin/python scripts/e3_build_candidate.py --registry /tmp/g53/uniq                 # E3 (needs the registry rebuilt; see IR-53-43)
/tmp/venv/bin/python scripts/s3a_leakage_repro.py                                           # S3-A
/tmp/venv/bin/python scripts/s3b_h8_holdout.py                                              # S3-B
/tmp/venv/bin/python scripts/s3c_build_candidate.py --template-root /tmp/gems-template --registry /tmp/gems53-registry-now   # S3-C
/tmp/venv/bin/python scripts/build_run_card.py && /tmp/venv/bin/python scripts/build_site.py
/tmp/venv/bin/python -m pytest -q tests
```

The GEMSDOE* registry is rebuilt from the GitHub repositories (`scripts/fetch_registry.py`, which uses `gh`; the copy loop is described in the run card). Its 1.3 GB are not committed (IR-53-56, L-33). The S3 gate used 628 unique rasters on the grid, from a 1212-file rebuild.

## Remaining work

1. Resolve the raw uniqueness-gate scope/definition only through an explicit governance decision; then pre-register and rerun it (IR-53-46 to IR-53-49). Until then, do not promote any candidate.
2. Run H12 on the spatially blocked holdout, with a named mimic as negative control (next experiment; IR-53-58). Do not spend a submission slot on a hypothesis that has not beaten the current holdout best.
3. Reconcile the registry counts and commit the manifest used by the gate (IR-53-56, L-33).
4. Test H10 and H9 (ranks 2 and 3), after checking where band 15 (depth to basement) comes from; its origin is not documented in this workspace.
5. Test H5 (verify the INGENIOUS licence first; IR-53-44), H2 and H7 (their designs were not valid as run; see Answers).
6. Build a non-catalogue validation population so that holdout gains are not catalogue-proximity gains (IR-53-42, L-22).
7. Add seed replicates and a model-variance estimate (L-25).
8. Obtain a portal receipt for any uploaded file before making an ORGANIZER-CONFIRMED claim (none exists).
9. Confirm the stored prompt capture against the original message (IR-53-27, IR-53-38).
10. Resolve the leaderboard conflict (IR-53-01) and the deadline conflict (IR-53-55) from the official competition page.

## Limitations

See `registry/limitations.json` (L-01 to L-37). The main ones: no organizer score exists; the holdout truth is the catalogue (proximity-dominated, IR-53-42); shell egress is limited to github.com, codeload.github.com, api.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org, so USGS ComCat (curl exit 35 in this sandbox), ScienceBase and similar sources cannot be fetched from the shell (L-31); USGS publication pages S31/S32 were read via the page tool, and no external layers were downloaded; compute is 2 vCPU with no GPU; the shared template's CNN pipeline was not run; the registry is not committed (L-33).

## Irregularities

See `registry/irregularities.json` (IR-53-01 to IR-53-63). Open items that change a decision: IR-53-01 (leaderboard conflict: 0.3774 vs 0.3195), IR-53-02 (0.2778 not linked to a file), IR-53-16 (the 70% rule), IR-53-27 and IR-53-38 (the prompt capture is normalized, not verbatim), IR-53-37 (design A leak, corrected), IR-53-40 (H3 blocked), IR-53-42 (catalogue-proximity holdout), IR-53-46 (the raw overlap rule is unsatisfiable on this registry), IR-53-47 (rho flags depend on whole-grid NaN handling), IR-53-49 (partial refresh is not a clearance), IR-53-54 (sandbox clock is one day ahead of the session date), IR-53-55 (deadline differs between sources), IR-53-56 (registry counts not reconciled), IR-53-58 (no pre-registered mimic), IR-53-60 (the S3 file is a weak control), IR-53-62 (named scripts missing in the workspace).

## Prompt (normalized capture; read at every session start)

**Provenance (IR-53-27, IR-53-38):** the text below is the capture stored in [`docs/prompt/verbatim.md`](docs/prompt/verbatim.md). It is **normalized, not a verbatim transcript**. Consolidated paragraphs, dropped repetitions and the supplied score list are not an official receipt. Confirm it against your original message before relying on exact wording.

<details open><summary>Prompt capture (from docs/prompt/verbatim.md)</summary>

> **Capture status: normalized, not byte-for-byte verbatim.** This file consolidates repeated paragraphs from the current user request. The long registry/result list is a partial transcription, not an official leaderboard snapshot. Read the user's original message for exact wording; do not cite this file as a receipt or source of truth for scores.

Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Formally diagnose the GEMSDOE29 leakage bug using the standard methodology for exactly this failure. An AUC of 1.0 from a single feature isn’t good news dressed up as a red flag — it’s close to a textbook example. Kaufman, Rosset, Perlich, and Stitelman’s “Leakage in Data Mining” (KDD 2011 / ACM TKDD 2012) formalizes this: leakage is information about the target that shouldn’t legitimately be available, and their core diagnostic is to ask, for any suspiciously strong feature, whether it could only take its observed value because the label is already known — which is exactly what “distance to the existing fault catalogue” risks being, since the catalogue itself is the thing this competition’s target is defined against. Their proposed fix, “learn-predict separation,” means recomputing that feature using only information that would genuinely be available at prediction time for an unmapped fault, not derived from the very catalogue the target is scored against. Treat GEMSDOE29’s bug as a template, not an isolated incident: audit every feature in the current stack by asking the same question before trusting any of their holdout numbers.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_[holdout.py](http://holdout.py) and submission_[writer.py](http://writer.py). Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition.  Must be unique submission unlike any within the GEMDOE sites above.  Verify working line by line no hallucinations.

Current competition leaderboard GEMSDOE high score:

0.3774

[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

gems-submission-20260925T001403Z-7f00890a: 0.1563

....

[https://buffedlizard55-lab.github.io/6GEMSDOE/](https://buffedlizard55-lab.github.io/6GEMSDOE/)

gems6_hgb88-topk03_33cec71ff0: 0.0286

....

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

pindrop-v4-nodes-20260925T152420Z-f347b70daa: 0.1193

pindrop-v4-discovery-20260925T152423Z-37f9d5b855: 0.0830

pindrop-v4-ridge-20260925T152422Z-4e03fc9705: 0.1152

....

[https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html)

gemsdoe2-dual-family-union-20260925T160406Z-f68e590f: 0.1560

....

[https://buffedlizard55-lab.github.io/GEMSDOE4/](https://buffedlizard55-lab.github.io/GEMSDOE4/)

gems-submission-20260926T163915Z-237f0063: 0.0343

....

[https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html)

gems-submission-20260926T175114Z-7f00890a: 0.1563

....

[https://buffedlizard55-lab.github.io/7GEMSDOE/](https://buffedlizard55-lab.github.io/7GEMSDOE/)

lidarscarp-ridge-top2pct-36c3a3f341c8: 0.1461

....

[https://buffedlizard55-lab.github.io/8GEMSDOE/](https://buffedlizard55-lab.github.io/8GEMSDOE/)

Hedge-v2_submission: 0.1563

....

[https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html)

2314b599: 0.0107

....

[https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html)

gems-structural-area06-v1: 0.0202

....

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

r7-nms3-dem10-scarp_0c9199f14e62:0.1294

r7-nms3-dem10-scarp_0c9199f14e62_allfinite:0.1294

....

[https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html)

gems-tso1-20260929T005627Z-conj_alteration_mag: 0.0782

....

[https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html)

GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f: 0.0020

....

[https://buffedlizard55-lab.github.io/17GEMSDOE/](https://buffedlizard55-lab.github.io/17GEMSDOE/)

17GEMSDOE_F-ensemble-2pct_20260930T050626Z:0.0187

....

[https://buffedlizard55-lab.github.io/18GEMSDOE/](https://buffedlizard55-lab.github.io/18GEMSDOE/)

H19-C_20260930T212401Z_c11e495e: 0.0297

....

[https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html)

h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan: 0.1894

h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan: 0.1922

....

[https://buffedlizard55-lab.github.io/GEMSDOE10/](https://buffedlizard55-lab.github.io/GEMSDOE10/)

h16-continuation-20260927T065521077735Z-3431b83c7c: 0.0461

h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686: 0.0921

H25-ctx-ridge-20260927T232947704150Z-6452ae1d00: 0.1280

h28-dotted-ridge-20260928T020256236880Z-6452ae1d00: 0.1839

....

[https://buffedlizard55-lab.github.io/13GEMSDOE/](https://buffedlizard55-lab.github.io/13GEMSDOE/)

20261001_r13-lattice-s5_v2_nan-outside:0.0904

....

[https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html)

h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan: 0.1855

h18-3a-topo-geophys-x-complexity-prior-20260930-c502dfab-nan: 0.0976

h18-4-usgs-geologic-map-faults-gap-20260930-aef8f42c-nan: 0.0360

....

[https://buffedlizard55-lab.github.io/GEMSDOE21/](https://buffedlizard55-lab.github.io/GEMSDOE21/)

h19-4-reference-20260930-691e4dfa: 0.1894

....

[https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html)

h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-20260930-be0e8f6b-nan: 0.1890

h20-5-continuous-pu-proxy-unverified-20260930-824ce73a-nan: 0.1859

....

[https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html)

h23-a-dti-optimal-emission-6pct-20261002-e2ec4b49-nan: 0.1002

h23-b-dti-optimal-emission-10pct-20261002-86176698-nan: 0.0748

....

[https://buffedlizard55-lab.github.io/GEMSDOE23/](https://buffedlizard55-lab.github.io/GEMSDOE23/)

h30-arrangement-matched-habitat-20261002-0d4e02e8-nan: 0.1352

....

[https://buffedlizard55-lab.github.io/GEMSDOE24/](https://buffedlizard55-lab.github.io/GEMSDOE24/)

h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan: 0.2477

....

[https://buffedlizard55-lab.github.io/GEMSDOE25/](https://buffedlizard55-lab.github.io/GEMSDOE25/)

dotted-h19-5-d2-8-20261002-e56ea318af89-nan: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE26/](https://buffedlizard55-lab.github.io/GEMSDOE26/)

dilcond-oof-v1-20261003-47629f496133-nan: 0.1223

....

[https://buffedlizard55-lab.github.io/GEMSDOE27/](https://buffedlizard55-lab.github.io/GEMSDOE27/)

topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan: 0.2449

....

[https://buffedlizard55-lab.github.io/GEMSDOE30/](https://buffedlizard55-lab.github.io/GEMSDOE30/)

d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE31/docs/](https://buffedlizard55-lab.github.io/GEMSDOE31/docs/)

h27-4-solo-d28-20261004-8acb75e1-nan:0.2708

....

[https://buffedlizard55-lab.github.io/GEMSDOE33/](https://buffedlizard55-lab.github.io/GEMSDOE33/)

h33d-analog-tip-stepover-r30-20261004-cb490425926e: 0.2632

....

[https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html)

h34-scatter-q50-arr-matched-20261004T223317Z: 0.0778

....

[https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html)

h35-06-aaa86efb25-20261004T225420098147Z-candidate: 0.0418

....

[https://buffedlizard55-lab.github.io/GEMSDOE36/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE36/docs/index.html)

anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros: 0.2750

....

[https://buffedlizard55-lab.github.io/GEMSDOE37/](https://buffedlizard55-lab.github.io/GEMSDOE37/)

h6-physics-dotted-80k-20261005T055000Z-0bef9211631c: 0.1193

....

[https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html)

D-step-3p0-07pct-tipProt-20261005-ecfbf59e2b48-zero: 0.0763

....

[https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html)

xscale-worm-persistence-20261006T000541Z-nan: 0.0581

....

[https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html)

sup01-hgb21-sep40-n40000-20261006-bc2e4e9a8d6f-nan: 0.0424

....

[https://buffedlizard55-lab.github.io/GEMSDOE45/](https://buffedlizard55-lab.github.io/GEMSDOE45/)

h51-km-faultzone-20261006-zeros: 0.0106

....

[https://buffedlizard55-lab.github.io/GEMSDOE49/](https://buffedlizard55-lab.github.io/GEMSDOE49/)

gate_ortho_w0.25-40k-20261006T213721Z-nan: 0.2376

....

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

....

[https://buffedlizard55-lab.github.io/GEMSDOE28/](https://buffedlizard55-lab.github.io/GEMSDOE28/)

h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan: 0.2708

h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan: 0.2649

h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan: 0.2710

h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan: 0.2707

....

[https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html)

efd28-repro-20261003-1cc7dc534d51-nan: 0.2600

repo-c0-habitat-emission-20261003-a4d439b07426-nan: 0.0041

sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan: 0.0512

wormrank-d28-20261003-59dcaf6dd11d-zeros:0.2560

wormsurv-filter-20261003-921f10960d6e-zeros:

xfit-c0-habitat-20261003-ca879db0089a-zeros:

xfit-h41-union-qfaults-20261003-9edb34b99e3a-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE46/](https://buffedlizard55-lab.github.io/GEMSDOE46/)

r11f-scarp-radiometric-fusion-00e049b51218-zeros:0.1589

r12-scarp-rad-concordance-23e807e2de9f-zeros: 0.0843

....

[https://buffedlizard55-lab.github.io/GEMSDOE39/](https://buffedlizard55-lab.github.io/GEMSDOE39/)

h40-e-disc-h40e-30k-zeros: 0.0339

....

[https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html)

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1:

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1-hard:

h45-eulerdepthreadcluster-20261006-f28e5cff6826-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html)

h42-submission-primary: 0.0245

....

[https://buffedlizard55-lab.github.io/GEMSDOE44/docs/](https://buffedlizard55-lab.github.io/GEMSDOE44/docs/)

h46-twostageAB_20261006T160000Z_b0cfe956-zeros:

....

[https://buffedlizard55-lab.github.io/GEMSDOE47/](https://buffedlizard55-lab.github.io/GEMSDOE47/)

h60-sharpened-scarp-scatter-90k-20261007T171954Z-allfinite:

....

[https://buffedlizard55-lab.github.io/GEMSDOE51/](https://buffedlizard55-lab.github.io/GEMSDOE51/)

h53-twostage-20261008T040951Z-9a0b32c871:

....

53GEMSDOE

:

....

54GEMSDOE

:

....

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

See below for more links and information related to the competition:

[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution)

[https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)

[https://gbcge.org/current-projects/ingenious/](https://gbcge.org/current-projects/ingenious/)

[https://epsg.io/32611](https://epsg.io/32611)

[https://en.wikipedia.org/wiki/Tversky_index](https://en.wikipedia.org/wiki/Tversky_index)

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.

0.3195	is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submitNo file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;st=wz4kofki&amp;dl=0](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)

[https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&amp;st=8junzdyw&amp;dl=0](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)

[https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&amp;st=rnino7ya&amp;dl=0](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)

[https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&amp;st=zj1lag1r&amp;dl=0](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)

[https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&amp;st=srhhir10&amp;dl=0](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Site creation

Create a github page for this repo that has clean ui, user friendly, simple and easy to use.  It should be organized and clean.

It should include all relevant information in an easy to read format with official verified links as sources for review.  Work line by line verify everything no hallucinations.

**The single remaining blocker to training is data placement**: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself.  Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.

---

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.



Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submitNo file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;st=wz4kofki&amp;dl=0](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)

[https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&amp;st=8junzdyw&amp;dl=0](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)

[https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&amp;st=rnino7ya&amp;dl=0](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)

[https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&amp;st=zj1lag1r&amp;dl=0](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)

[https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&amp;st=srhhir10&amp;dl=0](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.



The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.



Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;st=wz4kofki&amp;dl=0](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)

[https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&amp;st=8junzdyw&amp;dl=0](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)

[https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&amp;st=rnino7ya&amp;dl=0](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)

[https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&amp;st=zj1lag1r&amp;dl=0](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)

[https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&amp;st=srhhir10&amp;dl=0](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.

---

This file is a working charter normalized from the task text supplied in the current user turn. It is not a verbatim transcript, and the result list above is not complete. The listed values remain user-reported/owner-claimed unless an official receipt says otherwise; see `README.md`, `registry/sources.json`, and `docs/research/gemsdoe32.md` for evidence labels. No value in this capture is an ORGANIZER-CONFIRMED score by itself.

</details>
