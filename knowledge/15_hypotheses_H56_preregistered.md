# 15 · H56 hypothesis slate

**Chronology, stated honestly (corrected in the third review pass).** The file name says
"preregistered" because that is what it was meant to be. It is not: file timestamps show the slate
was written at 15:36Z, *after* the build (`work/b5_build_h56.py`, 15:33Z) and after the first
publish (`work/b6_publish_h56.py`, 15:32Z). It is therefore a **retrospective registration of a
slate that had already been decided**, not a blind pre-registration, and no blind-gate claim is
made anywhere. What is true: (a) every *measured* number below comes from the analysis scripts
listed next to it, executed 15:25–15:30Z on bytes whose SHA-256 is pinned in
`registry/data_manifest.json` (plus the two layers pinned in §0), before the build; (b) hypotheses
H56-4, H56-5 and H56-6 were never run, so they remain genuinely untested; (c) the ranking rule
(measured density ÷ implementation cost) was fixed in the slate itself. `registry/h56_preregistration.json`
records the same timestamps and the same `registration_kind`.

**Score/source authentication limit:** all public leaderboard scores are participant-level observations;
no organizer receipt in this checkout maps a score to any particular filename/hash. The credited-pixel
bounds, inferred `|G|`, and score projections below are conditional on owner-reported score-to-file
associations. They are not organizer-authenticated truth credits, a test score, or a holdout result.

## 0 · The measurement that ranks everything else

The repo's revealed-preference inverse (`knowledge/10`) is extended here to **all fourteen**
accessible scored predictions — the 13 in `data/scored` + `data/reference` and the newly fetched
`gemsdoe36-anderson-geothermal-pinn-38854-nan.tif` (owner-reported 0.2750) — using the metric's own
identity `T_i = score_i · (0.2·S_i + 0.8·|G|)`, `|G| = 14,088.7 px`.

* `work/b1_pattern_credit.py` partitions the grid by the 14-bit coverage pattern of every pixel and
  fits an additive per-pattern credit density (`T_i = Σ_p M[i,p] t_p`, `t_p ≥ 0`).
* `work/b2_lp_bounds.py`, `work/b3_monotone_lp.py` compute the **exact LP interval** for any
  aggregate, first with algebra alone and then with the physically motivated monotone constraint
  *more independent detectors agreeing on a pixel cannot earn less credit*. Checks: the LP
  reproduces the champion's credit independently (`A`: 5,171–5,275 vs published 5,223.1).
* `work/b4_tier_optimum.py` refits the model with scaled equations and reports core-family LOO.

Measured result that decides the slate (`work/b3_monotone_lp.json`, `work/b4_tier_optimum.json`):

| tier (coverage of the 8 well-predicted core files) | px | credit (monotone LP) | density |
|---|---|---|---|
| all 8 | 17,435 | [3,835, 5,213] | **22.0 – 29.9 %** |
| ≥7 | 21,826 | [4,010, 5,214] | 18.4 – 23.9 % |
| ≥6 | 37,440 | [5,061, 5,275] | 13.5 – 14.1 % |
| ≥5 | 62,046 | [5,680, 6,732] | 9.2 – 10.8 % |
| ≥3 | 108,394 | [6,566, 6,883] | 6.1 – 6.4 % |
| champion file `A` (reference) | 37,033 | 5,171 – 5,270 | 13.9 – 14.2 % |

Consequences. (i) The **all-8 consensus tier is the only structure in the whole accessible
ensemble whose credit density is more than 1.5× the champion's**, and it is the tier every
LOO-validated instrument agrees on. (ii) Every pixel outside that tier earns ≤ 5.8 % per cell
(fitted), i.e. below the metric's own break-even at the live scores (`0.2·DTI ≈ 0.056 – 0.064`).
(iii) The champion file's own marginal cell is worth 6.0 % (its published credit minus the tier's
fitted credit, over the difference in mass) — which is *why* the champion is hard to beat by
re-thinning its family. All further gains must come from mass the family has never emitted.

## 1 · Ranked hypotheses (rank = expected DTI gain ÷ implementation cost)

### H56-1 · Consensus-core retention + continuation arm — **RANK 1, implemented**
* **Layers.** Core: `P1 = h33-2-b2 ∩ gems24-d1-5` (25,517 px), whose conditional implied-credit
  interval is `[4,168, 5,223]` (central 5,140) under unauthenticated owner-reported file/score links.
  Selected continuation/scarp arm, three layers never
  used together before: (a) the strike field of the credited cloud (structure tensor of the
  smoothed core, σ = 3 px — the H54-2 mechanism, coherence 1.57× a matched random cloud and strike
  100–110° agreed to cosine 0.9952 between two independent thinnings); (b) **NEW**: the 3 m DEM
  scarp gates `h_gate07`/`h_gate12` from `data/external/h52_scarp3m_100m.tif`; (c) the 1 m LiDAR
  `step_max`/`relief`×`coh100` stack.
* **Physical signature.** A fault trace continues along its own strike; the continuation is
  expressed as a metre-scale scarp (3 m DEM gate) and/or a Lidar step with coherent fabric. The
  metric rewards exactly this: `TPw = Σ_g max_x k`, and a cell 250 m along-strike of the last
  credited dot covers truth pixels that dot's kernel cannot reach, while a cell placed across-strike
  re-covers the same truth and pays the full tax.
* **Why the catalogue cannot contain it.** The core is ≥ 200 m from every mapped trace by
  construction (the dead ring of `knowledge/10` §2), and the continuation is further out.
* **Difference from repo history.** H52–H55 emitted *ranked points of a detector*; this emits the
  **budget-optimal mix** of an exactly-bounded core and a novel arm whose size is chosen by
  `revealed.budget_rule` (`P(DTI > 0.2778)` over the exact `t_core` interval × the ρ_novel prior
  U[0.03, 0.14]) — the size is a decision, not a taste. First use of the 3 m DEM layer anywhere in
  the repo.
* **Post-build report (see `knowledge/16` and `evidence/h56_slot_gate_review_2026-10-07.json`)**:
  40,517 px (sha256 `1308083dcf09b4c6…`, 153,815 B), no exact decoded match among 33 checked priors,
  12,941/40,517 = 31.9% support outside their union; format and canonical-pattern checks pass, but the
  full-file ≥3 px nearest-neighbour diagnostic fails at 2.83 px inside the fixed core. The 15,000-cell
  selected arm is not wholly support-novel. Projection mean DTI 0.308 / P(>0.2778)=0.83 /
  P(>0.3195)=0.37 is conditional arithmetic, not a holdout. H56 is not approved for upload.

### H56-2 · All-8 consensus tier emitted alone — **RANK 2, not selected**
* **Layers.** Only the intersection of the eight aligned, well-predicted scored files (no external
  layer). **Signature.** Eight independent modelling pipelines agreeing on one 100 m cell.
* **Measured.** Density 22.0–29.9 %, the highest in the ensemble — but its own projected DTI tops
  out at 0.353 and its *worst case* (0.26) is below the champion's, because 17,435 px is too little
  mass to cover `|G|` and the file cannot satisfy the ≥ 20 % support-novelty gate at all (0 % of its
  pixels are new). **Cost:** zero. **Verdict:** folded into H56-1's core analysis, not shipped alone.

### H56-3 · Out-of-family union (corridor family ∪ PINN family) — **RANK 3, measured rejection**
* **Layers.** `P1` and `gemsdoe36-anderson-geothermal-pinn-38854` (live 0.2750).
* **Measured.** `|A ∩ PINN| = 37,654 = |A|` — **the champion file is a literal subset of the PINN
  file**, and the 1,200 extra PINN pixels carry `T(PINN) − T(A) = 13.4` credit, density **1.1 %**.
  A union therefore adds mass at a density 50× below the break-even bar. **Verdict: never build.**

### H56-4 · Two-meter INGENIOUS temperature-probe residual corridors — **RANK 4, queued**
* **Layers.** `data/external/gdr_wellspring_in_footprint.csv` (3,346 columns, incl. T2m),
  `gdr_volcanic_vents_in_footprint.csv`, INGENIOUS 2 m probe grid (sibling mirror only).
* **Signature.** A ≥ 60 °C discharge point requires a permeable fault within a few hundred metres;
  anchor there and expand *perpendicular* to the local potential-field strike.
* **Why off-catalogue.** The catalogue is a geomorphic scarp product; discharge does not require a
  scarp. **Difference.** H19-5/H55 used springs as a *count feature*; this uses each spring as an
  anchor with its own temperature. **Cost:** ~30 min (mirror route only — the GDR asset terms are
  unverified, so it cannot decide an emission by itself). **Gain:** unknown, priced by GEMSDOE48 at
  0.2727–0.2880 on their model; kept queued because H56-1 already spends the slot.

### H56-5 · 1 m DEM acquisition on a GitHub runner — **RANK 5, blocked, named source**
* **Source.** USGS 3DEP 1 m bare-earth DEM (public domain), tile list in the competition's own
  `1m_DEM_links.csv`. **Obtainability check:** this sandbox cannot reach the TNM/S3 hosts (not in
  the egress allow-list). The documented route that worked for the sibling is a GitHub Actions
  runner (GEMSDOE48 `.github/workflows/dem-pilot.yml`, `source_run = 37561683197`). **Cost:** one
  workflow dispatch + hours of CI; **not run this session** because the 3 m layer already covers
  5,900,588 cells.

### H56-6 · Earthquake point-geometry lineaments (ComCat / NV relocated) — **RANK 6, queued**
* **Layers.** `usgs_comcat_earthquakes.csv.gz`, `nvreloc_catalog_newmag.txt.gz` (public domain,
  mirrored in `buffedlizard55-lab/GEMSDOE50`). **Signature.** Declustered hypocentre covariance →
  linear, well-sampled clusters with no mapped trace. **Cost:** 30–60 min to restore + QC, and the
  instrument is unvalidated against this metric. **Verdict:** next session.

## 2 · Pre-registered decision rule for H56-1

1. Core = `P1` (exact credit interval); the novel arm must supply ≥ 35 % of the file's support
   (`budget_rule`'s own `min_novel_fraction`) and may not touch the ≤ 200 m ring.
2. The novel arm is emitted at mass 1.0 under a ≥ 3 px minimum separation (the metric's demonstrated
   optimum geometry — two dots closer than the kernel share truth pixels and the second pays tax).
3. Size chosen by maximising `P(DTI > 0.2778)` over the exact `t_core` interval × ρ_novel prior,
   ties to the larger novel fraction.
4. Promotion rule unchanged: report any projection as conditional, never as a point claim; the file
   must be *zeros-outside, all-finite, footprint-only*, and the site must state both the projection and
   that P(beat the board top 0.3195) is ≈ 0.37, not 1. This retrospective slate is not a holdout.

## 3 · Review correction and slot decision (2026-10-07)

The user-required comparable spatial holdout is absent. Do not upload or spend a slot. A post-build
reconciliation found that an earlier description of all 15,000 selected-arm cells as outside the
33-prior support union was too strong: only 12,941 cells in the complete 40,517-cell raster are outside
that union. The full nearest-neighbour ≥3 px diagnostic is also false (2.828 px), inherited inside the
core; the arm itself is ≥3.162 px from the rest. No H56 per-cell A-only dossier can be reproduced from
the committed checkout. See the linked slot-gate and A-only-scope receipts; neither the 33-prior audit
nor the projection validates H56 against hidden labels.
