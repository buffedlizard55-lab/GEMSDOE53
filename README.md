# GEMSDOE53 — GEMS Prize research workspace (DrivenData competition 306)

> **Read this first, at the start of every session.** Then read the status below, then the protocol.

## Core values (focal points)

- **Maximize P(Win).** Every experiment and every scarce submission slot is chosen for its expected contribution to a valid, defensible result, not for novelty.
- **Own the Outcome.** Report defects and negative results plainly. Fix shared systems where permitted. A successful file write is not proof of scientific validity or of organizer acceptance.

## Status (2026-10-09, session 2) — current

| Item | Value |
|---|---|
| Label | **RESEARCH-ONLY / DO NOT SUBMIT** (pre-registered verdict matrix: uniqueness gate failed; see `docs/submissions/CURRENT.json`) |
| File | [`docs/submissions/gems53-c1-condmag-thin_bin_q0p1-20261009T011720Z-8cb3456b.tif`](docs/submissions/gems53-c1-condmag-thin_bin_q0p1-20261009T011720Z-8cb3456b.tif) (54,959 dots; sha256 `57251042b8d2565a9085cb1a8dbb12129201884635789411f359ebccb69a5d09`) |
| OK to download? | Yes, for research and review. |
| OK to submit? | **No.** Corrected uniqueness gate (GD-1) flags 25 registry rasters (overlap > 70% with lift > 1.5). Verdict: negative. |
| Submitted? | No. No slot used. No organizer score exists for any file in this repo. |

**What session 2 did (3 experiments, pre-registered 2026-10-09):** lane C1 — conductivity–magnetic cross-scale edge coherence (`bc1` arm = 19 stack bands + 14 label-free C1 features, **no catalogue feature**), pre-registration [`docs/research/preregistration-2026-10-09-session2.md`](docs/research/preregistration-2026-10-09-session2.md).

| Experiment | Result (all HOLDOUT-DTI, evaluator `gems53.core.dti` v1.0.0; 60,988 withheld positives in 3,199 segments) |
|---|---|
| S2-E1 canary | max single-feature separability of the 14 C1 features = **0.5726** (band-2 RTP edge, σ=4) → **pass** (gate 0.90). No leakage signal. |
| S2-E2 holdout | Stage 1: same-run baseline `bands:top_q0p02` = **0.010562** (CI 0.008337–0.012812, reproduces session 1 exactly); selected `bc1:thin_bin_q0p1` = **0.092172** (CI 0.080924–0.103406). Stage 2 spatial: baseline 0.000102 vs selected **0.004182**, paired Δ **+0.004085**, 95% CI **[+0.000336, +0.007834]** → **accepted**. Note: 0.004182 slightly exceeds session-1 H1's 0.004049 — pure geophysics matching a catalogue-distance model on the honest spatial holdout. |
| S2-E3 build + gates | Validators: template `validate_submission.py` exit 0, `validate-conformant` exit 0 (0 NaN inside the scored region, values in [0,1], EPSG:32611/shape/transform match). Uniqueness gate v2: max footprint rho **0.8857** (< 0.90) vs 5GEMSDOE bands-only surfaces; but 25 rasters exceed the corrected overlap rule → **PROTOCOL DUPLICATE / STOP**, label applied. |

**Why it is still not cleared (read IR-53-53).** The C1 surface ranking is genuinely distinct (max footprint rho 0.8857 < 0.90), yet its dots overlap 25 unrelated dot maps above chance (lift 1.5–4.2). Those 25 files span many methods — dot overlap measures shared *fault geography* (structural corridors), not shared *method*. Under the pre-registered rule the verdict is negative anyway; the gate definition needs a geography-stratified null or an explicit governance decision before any dot-based candidate can clear it. The raw literal rule remains provably unsatisfiable (IR-53-46/50).

**Other session-2 deliverables:** verified KDD'11/TKDD'12 leakage citations and the formal KRS diagnostic applied to GEMSDOE29 ([`docs/leakage-review.md`](docs/leakage-review.md), IR-53-12 resolved); expanded 5-candidate hypothesis screen C1/C5/C4/C7 + blocked C2/C3 ([`docs/research/hypotheses.md`](docs/research/hypotheses.md)); GD-2 evidence: 196 registry `-zerofill` files measured zeros-outside, and none of the three files ever shipped from this repo can reproduce the user-reported platform range error (IR-53-51, unresolved — needs the user's exact submitted file); IR-53-52 logged a prompt-injection attempt observed inside fetched web content.

## Status (2026-10-08, session 1) — superseded as current, receipts frozen

| Item | Value |
|---|---|
| Label | **RESEARCH-ONLY / DO NOT SUBMIT** (decided by the pre-registered gates, see `docs/submissions/CURRENT_session1_archived.json`) |
| File | [`docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif`](docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif) (445,801 bytes after a metadata-only note update; pixels unchanged) |
| Name | `gems53-h1-thin_bin_q0p1-20261008-aefc7582` |
| Comment (≤140 chars) | `RESEARCH-ONLY | HOLDOUT-DTI 0.0040; g53 DTI v1.0, withheld=60,988; Δ+0.0035 CI95 +0.0006..+0.0064; NOT ORGANIZER-SCORED | DO NOT SUBMIT` (135 chars) |
| sha256 (file) | `aeaa9a46236a658d91a05be48d54f14b44804c967d590314caeb2c0a82511f60` |
| OK to download? | Yes, for research and review. It is not cleared for submission. |
| OK to submit? | **No.** The uniqueness gate flags the file (below). |
| Submitted? | No. No submission slot was used, and no organizer score exists. |

**Why it is not cleared.** The file passes the format/conformance validators (the shared template validator and `validate-conformant` both exit 0), and the feature canary is below its threshold. The holdout gate passes its pre-registered paired rule (lower bound above 0), but the registry uniqueness/stop gate fails. The uniqueness gate flags 103 of 621 unique GEMSDOE registry rasters, so the pre-registered verdict is research-only. Under the literal parallel-run rule the candidate is a **protocol duplicate / stop**: 99.599% of its final dots are within 3 px of the GEMSDOE13 `r13-lattice-s5_v2` raster (threshold 70%; chance coverage 99.87%, lift 0.9973), and the whole-grid pre-placement surface-rho maximum is 0.953943 (>0.90). This is not a claim of byte-identical predictions; it is the required raw-rule duplicate disposition. The diagnostics also expose the gate's coverage confounding and method-sensitive whole-grid rho (IR-53-46 to IR-53-48). The `*_refresh.json` file is a partial 3-raster check, not the canonical verdict (IR-53-49). Fixing the gate scope/definition needs an explicit decision (see "Decisions needed").

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

## Prompt and session charter (read in full at every session start)

Before project work, read this README and [`docs/prompt/verbatim.md`](docs/prompt/verbatim.md) in full, then check `docs/submissions/CURRENT.json`, `evidence/run_card.json`, and the experiment budget. The prompt capture holds the operational requirements: leakage-safe learn-predict separation; one lane; per-feature canaries; no more than three experiments/two hours; pooled DTI and uncertainty; strict registry checks before and after placement; a unique-name/comment; a visible download link; and an explicit do-not-submit state when any gate fails.

**Capture status:** `docs/prompt/verbatim.md` is a normalized capture of the operative request, not a byte-for-byte transcript; repeated paragraphs were consolidated and the supplied score list is not an official leaderboard receipt. No exact wording or score provenance is inferred. IR-53-27 and IR-53-38 remain open until a genuine full transcript is stored. The local summary is not a substitute for the prompt's stop rules.

## Review outcome (2026-10-08; no new experiment)

- The already-generated candidate TIF exists and is downloadable for review, but **must not be submitted**. It fails the raw duplicate rule. Its filename is an identifier, not proof of raster uniqueness.
- The TIF itself was re-opened and validated against the cached competition sample using shared template commit `dcbbb192e56b2b32c0a131eba791dc363305d4a3`: single-band float32, EPSG:32611, 3730×3292, 100 m, exact transform/footprint, NaN outside only, values in [0,1], nodata=NaN. Both shared validators returned exit 0.
- Competition data were fetched to `/tmp/gems53-data` by `scripts/fetch_data.py` from the public GitHub mirror and matched its pinned hashes (S7). This verifies the mirror against its manifest, **not** against a direct DrivenData download. No data were added to Git.
- QA: 30 tests passed, 0 skipped, with two non-failing Rasterio deprecation warnings; the shared metric parity test ran against the pinned template. No new holdout or submission slot was used; the three-experiment budget was already exhausted.
- Prior hypotheses H2 (magnetic Hessian ridges), H5 (thermal/paleo geothermal evidence), and H7 (strike/trend priors) are not all novel: H2 is already implemented/tested in this repo and related H5/H7 methods occur in the public GEMSDOE inventory. Three future candidates are screened in [`docs/research/hypotheses.md`](docs/research/hypotheses.md); only C1 uses the existing cached feature stack, and it was not run.

## What was done in this session (three experiments, pre-registered)

Pre-registration (committed before the runs): [`docs/research/preregistration-2026-10-08.md`](docs/research/preregistration-2026-10-08.md), with deviations DEV-1 (the holdout design) and DEV-1b (a stage-2 code bug, IR-53-45) logged in section 9.

| Experiment | What | Result (labels as stated) |
|---|---|---|
| E1 (design A, reference only) | Exploration on segment folds with the first negative pool | **Not used for decisions.** Its negative pool depended on withheld labels (IR-53-37). Reproduction of the earlier exp2 numbers: PASS. Metric parity with the shared template `src/metrics.py`: PASS (difference 1.3e-13). |
| E2 (design B) | Stage 1: 24 variants on segment folds (seed 53, 5 folds, 10 px buffer). Stage 2: paired spatial confirmation on contiguous super-regions (template `src/blocks.py`). | HOLDOUT-DTI (evaluator `gems53.core.dti` v1.0.0; 60,988 withheld positives / 3,199 segments): baseline bands top-q 0.02 = **0.010562** (95% CI 0.008337–0.012812). Stage-1 selected H1 with binary thinning at q 0.10 = **0.141319** (95% CI 0.133780–0.148921; selected on these folds, optimistic). Stage-2 spatial pooled baseline **0.000102** vs selected **0.004049**; primary paired mean difference **+0.003533** (95% paired t CI +0.000619–+0.006447, df 4). The rule accepts; this remains a catalogue proxy. |
| E3 (build) | Train on all known faults; write with the shared template writer; validate; uniqueness gate on 621 unique registry rasters; label | 56,605 dots (from 516,737 candidates before thinning). Validators PASS. Canary: bands max separability **0.5912** (band 7), H1 **0.7680**, both below the 0.90 gate. Uniqueness: **flagged**. Label: **Research-only / DO NOT SUBMIT**. |

Every holdout number above is **HOLDOUT-DTI** (evaluator `gems53.core.dti` v1.0.0, parity with the template metric). None is **ORGANIZER-CONFIRMED**.

## Answers (short)

- **GEMSDOE29 leakage.** Confirmed and formally diagnosed (`docs/leakage-review.md`). Its distance-to-known-faults feature is built from the full label raster, so it is exactly 0 on every known-fault pixel (separability 1.0). Learn-predict separation is the fix. The write-up now also records our own holdout leak (IR-53-37), which is corrected to design B.
- **GEMSDOE32 H33-2-B2 / 0.2778.** S2's public leaderboard snapshot shows `extradr19` at 0.2778 (#13), but no submission receipt links it to H33-2-B2 (IR-53-02). Registry-copy measurements (`evidence/gemsdoe32_measured.json`) show 37,654 dots (0.73% of footprint), 0.0% within 2 px of mapped faults, and median nearest-dot spacing 3.0 px. This geometry is compatible with metric-aware thinning, but is not proof of the score mechanism. The owner's 0.2708 is an OWNER-CLAIM, not ORGANIZER-CONFIRMED. The `zeros` variant fills the grid with 0 (IR-53-41).
- **Can we beat 0.2778 / 0.3774?** Not shown. We have no organizer score for any file here. The leaderboard values are the repository's snapshot (IR-53-01): #1 0.3774 (xiaofanhu), #7 0.3195 (DARD), #13 0.2778 (extradr19). The request named 0.3195 as the top score, and the snapshot disagrees.
- **Hypotheses.** H1/M1 has a design-B spatial confirmation. H2 was attempted, but its X2 holdout used the invalid design-A negative pool and was not rerun (IR-53-37). H5/H7 have close portfolio analogues and should not be advertised as new. Three future candidates (C1–C3) are screened in [`docs/research/hypotheses.md`](docs/research/hypotheses.md). C1 uses existing bands but was not run; C2/C3 need external source-access verification. The experiment budget is used up.

## Decisions needed (not made here)

0. **Which candidate, if any.** Three files carry different positions (this session's research-only file, the other sessions' `READY_TO_SUBMIT` H1 relay, and the `DO-NOT-SUBMIT` H2 ridge). None is cleared by the pre-registered rule. No slot is selected.

1. **The uniqueness gate (IR-53-46, IR-53-47, IR-53-48).** Choose a registry scope that counts submission-type dot maps only, a chance-corrected overlap rule (lift over chance), and a footprint-only rank correlation. Any such change needs explicit approval and a fresh pre-registered gate run. Until then, no candidate from this repository can be labelled OK to submit (L-27).
2. **Exact prompt transcript (IR-53-27, IR-53-38).** The current session brief is normalized, not byte-for-byte. Preserve a true verbatim transcript if one becomes available; until then, do not claim that it is exact.
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
| `registry/` | `irregularities.json` (IR-53-01 to 49), `limitations.json` (L-01 to 29), `sources.json` (S1 to 32) |
| `src/gems53/core.py` | Lane library: loaders, folds, H1 segment-exact distance, M1 thinning, template loader, DTI |
| `scripts/` | `fetch_data.py`, `e1_h1_thin_holdout.py`, `e2_leakfree_holdouts.py`, `e3_build_candidate.py`, `uniqueness_gate.py`, `uniqueness_diagnostics.py`, `measure_gemsdoe32.py`, `build_run_card.py`, `build_site.py` |
| `tests/` | `test_h1_thin.py` (brute-force checks of H1 and M1, and metric parity), `test_metric.py`, `test_submission.py`, `test_outputs.py` (re-check of the shipped file and the site) |

## Reproduce

The commands below document historical reproducibility only. **Do not execute E1/E2/E3 in this lane now**: the three-experiment budget is exhausted, and the current candidate failed the uniqueness gate. A future rerun needs a fresh preregistration and budget authorization; it must not overwrite the current receipts.

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

## Remaining work (updated 2026-10-09)

1. **Unblock the gate (highest leverage).** IR-53-53 shows dot-overlap rules measure shared fault geography, not method drift: C1's surface is distinct (max footprint rho 0.8857) yet its dots overlap 25 unrelated methods above chance. Options, each needing an explicit governance decision + fresh pre-registration: (a) geography-stratified lift null; (b) restrict the overlap rule to surface rho only; (c) user ratification of GD-1 clearance for files with footprint rho < 0.90. Until resolved, no dot-based candidate from any session clears an overlap rule on this registry.
2. **Selector decision (human).** Session-2 C1 passed every scientific gate (canary, design-B spatial holdout accepted, format validators) and failed only the overlap reading of the uniqueness rule. Whether to spend a weekly slot on it is a separate selector step that this lane does not make — but it is the strongest leak-free candidate this repo has produced.
3. For C2/C3, confirm official USGS source reachability and terms (S29/S30, L-32) — blocked in this environment.
4. Next-budget candidates from the ranked screen: C5 strain-budget residual, C4 gravity–basement collinearity, C7 seismic–conductive concurrence (`docs/research/hypotheses.md`).
5. Build a non-catalogue validation population so holdout gains are not catalogue-proximity gains (IR-53-42, L-22/L-31).
6. Add seed replicates and model-variance estimates (L-25).
7. Obtain a portal receipt for any uploaded file before making an ORGANIZER-CONFIRMED claim (none exists). Confirm with the user which file produced the reported "Predicted values must be in range [0, 1]" error (IR-53-51) — none of this repo's files can reproduce it.
8. Retain the prompt capture as normalized until an exact transcript is available (IR-53-27, IR-53-38).

## Limitations

See `registry/limitations.json` (L-01 to L-29). The main ones: no organizer score exists; the holdout truth is the catalogue (proximity-dominated, IR-53-42); shell egress blocks direct USGS/ScienceBase/OSTI/GDR data downloads (USGS publication pages S31/S32 were read via the page tool, but no external layers were downloaded); compute is 2 vCPU with no GPU; the shared template's CNN pipeline was not run.

## Irregularities

See `registry/irregularities.json`. Open items that change a decision: IR-53-01 (leaderboard conflict), IR-53-02 (0.2778 not linked to a file), IR-53-16 (the 70% rule), IR-53-37 (design A leak, corrected), IR-53-38 (verbatim prompt missing), IR-53-40 (H3 blocked), IR-53-42 (catalogue-proximity holdout), IR-53-46 (the raw overlap rule is unsatisfiable on this registry), IR-53-49 (partial refresh is not a clearance), **IR-53-50 (GD-1 gate interpretation, needs ratification)**, **IR-53-51 (user-reported platform rejection unreproducible from shipped files)**, **IR-53-53 (chance-corrected overlap still flags convergent fault geography)**. IR-53-52 logs a prompt-injection attempt observed in fetched web content.
