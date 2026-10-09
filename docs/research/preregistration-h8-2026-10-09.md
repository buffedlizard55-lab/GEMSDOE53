# Pre-registration — session lane H8 (tip/relay continuation corridors), 2026-10-09 UTC

**Written before any experiment in this lane was run.** Deviations will be logged in section 9 as DEV-x.
Every number produced later is labelled HOLDOUT-DTI (evaluator version, withheld positives, 95% CI)
or ORGANIZER-CONFIRMED. Projections are never written as scores.

## 0. Lane assignment (irregularity IR-53-64)

The parallel-run protocol says "Your lane is the single method paragraph below", but the message
arriving in this session contains **no method paragraph** (IR-53-64). To keep the session inside one
lane, the lane is fixed here as:

> **H8 — tip/relay continuation corridors with magnetic-lineament concordance.** Build a hidden-fault
> likelihood surface from the VISIBLE catalogue only: (a) along-strike continuation corridors beyond
> mapped segment tips (fault-growth: displacement dies at the tip, the structure continues), (b)
> relay/step-over corridors between overlapping sub-parallel segments (linkage damage zones = the
> classic permeable geothermal pathway), and (c) label-free magnetic lineament strength on the
> reduced-to-pole field (band 2). Poisson-pack binary dots at 2.8 px (280 m, just inside the 300 m
> metric kernel), pruned to at least 2 px off the visible catalogue. Emission value 1.0 on dots.

This is one method paragraph, one lane. It differs from every known registry family (see §5).

## 1. Hypothesis

**H8.** Hidden (unmapped) fault segments concentrate in structurally prepared corridors that the
visible catalogue itself defines: continuations beyond mapped tips and relay zones between
overlapping segments, corroborated by magnetic lineaments. A metric-spaced dot emission confined to
these corridors and pruned ≥2 px off the visible catalogue will recover withheld fault segments at
higher HOLDOUT-DTI per dot than (i) uniform placement and (ii) magnetic-ridge placement alone
(x2's ridge_pack family), because it spends its false-positive budget only where hidden faults are
physically expected.

## 2. Mechanism and the named mimicking process

- Mechanism: fault segments grow by propagation (tips) and interact by linkage (relays). Unmapped
  Quaternary segments sit beyond the mapped tips and inside relay/step-over damage zones; those
  zones also localize hydrothermal permeability (the competition's geothermal context).
- **Named non-fault process that could mimic it:** mafic dyke swarms and buried lithologic contacts
  produce linear magnetic lineaments with no Quaternary fault, and alluvial-fan berm/terrace edges
  mimic scarps near basin margins. Both can place dots in corridors that hide no fault (false
  positives) and pull the surface toward mapped-but-nonseismic structure. Reported in the run card.

## 3. Experiments (budget: 3 experiments / 2 hours)

| ID | What | Decision rule |
|---|---|---|
| X4 | Leakage canary (single-feature separability, design-B segment folds, seed 53, K=5, 10 px buffer): tip surface, relay surface, band-2 ridge strength, combined surface, plus the deliberately leaky full-catalogue distance (positive control) | Any lane feature with separability (max(AUC, 1−AUC)) above 0.90 = leakage until proven otherwise; expected control ≈ 1.0 |
| X5 | Hide-and-recover holdout of four placement arms at N = 44,090 and N = 80,000 dots: `null` (uniform), `halo` (2–3 px ring around visible faults), `ridge` (band-2 NMS centrelines), `h8` (tip+relay corridors, ridge as tie-break). ALL arms pruned ≥2 px from visible faults. Pooled DTI vs withheld segments (shared template `src/metrics.py` GtContext), 5 folds, 95% t-CI on the fold mean (df 4) and paired differences vs `ridge` | Candidate arm = highest pooled DTI at N = 44,090 among ridge/h8/halo. Budget rule: the candidate's N with higher pooled DTI becomes the submission budget. The lane is "promote-worthy" only if the candidate's paired lower bound vs `ridge` is > 0 AND the pooled value exceeds the design-B stage-1 best of the repo (0.1413 is selection-optimistic; the stage-2 spatial 0.0040 is the honest floor) |
| X6 | Build the final GeoTIFF on the FULL catalogue (all faults visible at prediction time, which is legitimate), prune ≥2 px from the full catalogue, write with the SHARED template writer (`src/submission_io.py`), conform to the official template, run validators, uniqueness gate vs the full registry, write receipts + run card | Label rules in §6 |

## 4. Holdout definition (design B, IR-53-37)

- Withhold whole fault segments (8-connected components; 3,199 segments; K=5, seed 53; 10 px buffer
  only for arms that train a model — none in X5).
- Every catalogue-derived feature (tip, relay) is computed from **visible segments only**.
- Score against withheld segments only; visible faults are NOT truth, so dots on visible faults are
  false positives — this is what makes the ≥2 px prune measurable in the holdout.
- Negatives are every footprint pixel that is not a visible fault (the training pool never depends on
  withheld locations).

## 5. Uniqueness gate (pre-registered decision, user-directed)

IR-53-46 shows the raw "70% of your dots within 3 px of one registry raster" rule cannot be satisfied
by any placement: GEMSDOE13's lattice (206,895 dots) covers 99.87% of the footprint within 3 px, so
every candidate overlaps it at chance (measured lift 0.997). The user's instruction this session is
that it **must be obvious whether the generated TIF is OK to download and submit**, which requires a
gate that can actually clear. The gate for this session is therefore (all recorded):

1. **Byte and pixel identity:** must differ from every registry raster (sha256 and pixel-sha256).
2. **Rank correlation:** Spearman rho on FOOTPRINT pixels only (IR-53-47) vs every registry raster:
   flag if > 0.90. (Whole-grid rho is also recorded; NaN-as-0 ties make it a method artefact.)
3. **Dot overlap, chance-corrected:** share of our dots within 3 px of a registry dot map, with the
   lift over that raster's chance coverage (IR-53-46). Flag if overlap > 0.70 **and** lift > 2.0
   (measured reference points: GEMSDOE13 lattice lift 0.997 = chance; GEMSDOE46 dfa-corroborated lift
   3.6 and GEMSDOE40 eulerdepth-si0 lift 5.6 = genuine method drift on the prior session's H2 file).
4. The raw 0.70 rule is still reported on every row so the change is auditable.

Verdict: OK-TO-SUBMIT only if (1)–(3) pass and all format validators pass. Otherwise DO-NOT-SUBMIT,
naming the gate. This decision supersedes IR-53-46's "decision needed" and is logged as DEV-2.

## 6. File contract (the [0,1] platform error)

The user received `Predicted values must be in range [0, 1]` on the submission form. The shared
template documents the same rejection (src/submission_io.py `conform_to_template` docstring,
platform rejection 2026-09-24): NaN is not in [0,1], and the platform counts NaN inside the scored
region. Two files are produced from the identical emission:

- **Primary — `...-zeros.tif`:** every pixel finite in [0,1]; 0.0 outside the footprint. Passes any
  range check that counts NaN as out of range. Organiser-scored ledger rows named `...-zeros`
  (including the 0.2778 row) show zeros outside is accepted by the platform. (Numbers: USER-REPORTED.)
- **Twin — `...-nan-outside.tif`:** template-conformant (NaN outside, nodata nan), passes
  `python -m src.submission_io validate-conformant`. This is the exact mask of `sample_submission.tif`.
- Both have identical pixels inside the footprint; DTI gives them identical scores (p=0 and NaN
  outside both contribute nothing to TP/FP/FN).

## 7. Submission identity

- Name pattern: `gems53-h8-tiprelay-ridgeconcord-pr2-n<N>-20261009-<pixel_sha8>`.
- Comment (≤140 chars) records the lane, the prune, the budget and the label.

## 8. Canary rule

Separability = max(AUC, 1−AUC) of the single feature for withheld positives vs design-B background,
per fold; the reported value is the max over folds. Above 0.90 ⇒ leakage until proven otherwise.

## 9. Deviations

- DEV-1 (this file, before the runs): lane paragraph missing from the prompt; lane fixed in §0
  (IR-53-64).
- DEV-2 (this file, before the runs): uniqueness gate corrected per §5 (user-directed decision;
  IR-53-46/47/48).
- DEV-3 (this file, before the runs): protocol tool names `evaluate_holdout.py` / `submission_writer.py`
  do not exist in the template (IR-53-39). Reused mapping: evaluator = template `src/metrics.py`
  `GtContext` (parity with `gems53.core.dti` at 1.3e-13, tests/test_metric.py); writer = template
  `src/submission_io.py`; folds = `gems53.core.segment_folds` (same as x2/e2).
