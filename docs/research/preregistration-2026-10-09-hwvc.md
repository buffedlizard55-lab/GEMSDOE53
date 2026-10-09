# Pre-registration — session 2026-10-09 (lane: HWVC, hanging-wall vector concordance)

Written and committed **before** any experiment in this session was run (session start 2026-10-09T00:36Z,
pre-registration 2026-10-09T00:44Z). Budget: at most **3 experiments** or **2 hours** (hard stop 02:36Z).
This is a new session with a new budget; the previous session's budget (E1–E3 of 2026-10-08) is closed and its
receipts are not overwritten.

## 0. Why a new lane, and the governance decisions this session makes itself

The user instruction for this session is explicit: no manual input, decide autonomously, and make it obvious
whether a file is OK to download and submit. The previous session left two decisions open. They are decided
here, before any result is seen, and are not changed afterwards:

* **D-1 Uniqueness gate definition (v2, chance-corrected).** The raw rule ("> 70 % of our dots within 3 px of one
  registry raster's dots") cannot be passed by *any* file while the registry contains lattice/dense rasters
  (IR-53-46: a lattice covers 99.87 % of the footprint within 3 px, so even random dots score 99.9 %). v2:
  * registry raster "dots" = its in-footprint pixels with value > 0 (NaN treated as 0); if that set exceeds 5 % of the
    footprint (a dense surface, not a dot map), its dots are its **top-K pixels**, K = our dot count (rank-matched).
  * `overlap` = fraction of our dots within 3 px (Euclidean) of the registry dots; `chance` = fraction of footprint
    pixels within 3 px of the registry dots; `kappa = (overlap − chance)/(1 − chance)`.
  * **Duplicate if `overlap > 0.70` and `kappa > 0.40`**, or if `|Spearman rho| > 0.90` between our continuous
    pre-placement surface (or our final raster) and the registry raster, computed on a fixed seeded sample of
    500,000 footprint pixels (seed 53).
  * The raw (uncorrected) numbers are reported next to v2 for every registry raster; nothing is hidden.
* **D-2 Output format.** The organizer-accepted 0.2778 file (GEMSDOE32 H33-2-B2, zeros variant, measured here) is
  float32, `nodata=None`, **0.0 outside the footprint (no NaN anywhere)**, binary dots. The user reported the portal
  error "Predicted values must be in range [0, 1]" for a NaN-outside file. Our primary file is therefore all-finite:
  dots = 1.0, everything else (inside and outside the footprint) = 0.0, `nodata` unset. The template's NaN-outside
  conformance check is expected to differ on this one point and is reported, not hidden.

## 1. Hypothesis (H53-HWVC)

A Basin-and-Range normal fault drops its hanging wall. Four **independent** measurements in the competition stack
should then point to the *same* "down side" across the fault: lower detrended elevation (band 12 `det_elev`),
lower isostatic gravity from low-density basin fill (band 13 `iso_grav_anom`), higher surface conductivity from
wet clay-rich fill (band 17 `cond_surf`), and deeper basement (band 15 `depth_to_base_surf`). A fault — mapped or
not — should sit where these down-side vectors are both **strong** and **co-directional**. The feature is the
resultant length of the magnitude-weighted unit down-side vectors (a circular-statistics concordance), at two
Gaussian scales (σ = 2 px and 5 px), plus a Canny-style non-maximum-suppressed centreline of that field.

* **Mechanism:** hanging-wall subsidence + sediment fill makes topography, density, conductivity and basement depth
  co-vary across the same line.
* **Named non-fault process that could mimic it:** a depositional (non-faulted) range-front onlap contact or a
  pediment/erosional lithologic contact between dense, resistive bedrock and conductive alluvium, which produces
  the same co-directional gradients without displacement.
* **Why it could find faults absent from the USGS/INGENIOUS catalogue:** the Qfault catalogue requires Quaternary
  surface evidence; buried or older basin-margin faults keep the multi-physics juxtaposition even without a scarp.
  This is a rationale, not evidence that the expert test set contains such faults.
* **How it differs from this repo and the registry:** H1 (catalogue distance) and H2 (single-band magnetic Hessian
  ridges) use one input each. GEMSDOE41's "basin-margin" surface is a different construction (its README describes
  3DEP scarp + RTP corroboration); HWVC is a sign-aware vector-concordance of four bands. Novelty is judged on the
  raster (gate D-1), not on the name.

## 2. Experiments (exactly three)

* **E1 — features + leakage canary.** Build HWVC features (label-free). Canary: every feature that enters the model
  (19 bands, H1, each HWVC channel) alone, withheld positives vs all non-visible footprint pixels (design B), segment
  folds seed 53, separability = max(AUC, 1 − AUC). Any feature > 0.90 = leakage until proven otherwise → excluded.
* **E2 — holdout comparison (hide-and-recover).**
  * Stage 1: segment folds (5 folds, seed 53, whole 8-connected segments, 10 px buffer excluded from training),
    design-B negatives (300k per fold, `default_rng(53)`, identical across arms), H1 recomputed from visible faults
    only (learn-predict separation), HGB as in E2/2026-10-08.
    * Arm A (current holdout best, reproduced): 19 bands + H1.  Arm B: 19 bands + H1 + HWVC.
    * Decoders (both arms, identical): (i) M1 `thin_bin` q = 0.10 (the decoder of the current best, 0.141319);
      (ii) the submission decoder D-S (below) with visible-fault flank prune 2 px.
    * Metric: pooled DTI (α 0.2, β 0.8, R 3 px) scored on footprint pixels that are **not visible faults**
      (visible faults masked pixel-exactly), truth = withheld faults. Paired per-fold differences, t-interval df 4.
  * Stage 2: spatial contiguous super-regions (template `src/blocks.py`, 5 folds, 512 px blocks), arm A vs arm B,
    decoder M1 q 0.10, paired t-interval.
  * **Promotion rule:** arm B is promoted only if the stage-1 paired mean difference (B − A, decoder M1) has a
    95 % lower bound > 0 **and** the stage-2 paired mean difference is > 0. Otherwise HWVC is a **negative**
    result (reported as such), and E3 builds the fallback: arm A (the current holdout best model, bands + H1)
    with the new decoder D-S. The fallback is labelled as the H1 lane, never as HWVC.
* **E3 — build + gates.** Train the promoted arm on all catalogue faults (H1 for training positives excludes the
  pixel's own segment; for prediction pixels it is the distance to all catalogue faults). Decoder D-S. Write with
  the shared template writer, validate, run gate D-1 against every registry raster, write the run card.

## 3. Submission decoder D-S (fixed now, not tuned on any holdout)

* Exclude every pixel within **2 px** (Euclidean) of a catalogue fault (organizer-evidenced: in the GEMSDOE32
  lineage the 1 px prune went 0.2600 → 0.2708 and the 2 px prune → 0.2778, both USER-REPORTED leaderboard reads;
  the test set is defined as faults *not* in the USGS database, problem page S1).
* Greedy dots in decreasing model score with minimum spacing **> 2.8 px** (the d2.8 geometry of the scored family).
* Stop at **N = 40,000** dots (between the 37,654 and 44,090 dot counts of the scored family).
* Dots = 1.0, everything else 0.0 (D-2).

## 4. What would make this a negative result

Arm B not beating arm A under the promotion rule; any HWVC channel above the canary threshold; the final raster
flagged by gate D-1. A negative result is reported as a deliverable and no file is labelled OK to submit.

## Outcome (appended after the runs; nothing above was edited except the logged wording fix IR-53-54)

- E1 canary: no feature above 0.90 (max HWVC 0.5997, H1 0.7683).
- E2: promote B = **False** (stage-1 paired M1 lower bound −0.003732; stage-2 mean +0.000344). HWVC is negative as an add-on feature.
- E3: arm A + D-S built (40,000 dots). Gate v2 verdict: **DUPLICATE** (27 rows), so **DO NOT SUBMIT** (IR-53-57). No slot used.
- Receipts: `evidence/h53_e1_canary.json`, `evidence/h53_e2_holdout.json`, `evidence/h53_e3_build.json`, `evidence/h53_gate_v2_e3_armA_ds40000.json`, `evidence/h53_run_card.json`.
