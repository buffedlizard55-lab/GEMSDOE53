# 20 — H59 hypotheses, preregistered (2026-10-08, before any H59 fit, score, or artifact)

Session brief: the two-view co-training brief (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962),
read against the metric algebra of `knowledge/01` and the exact credit atoms of
`knowledge/10`. Inputs for every H59 number are the manifest-pinned owner-mirror bytes restored to
`work/h59_pinned` (23/23 SHA-256 matches; receipt `work/h59_pinned/restore_receipt.json`), **not**
the tracked `data/*.tif` grid stubs, which H58's preflight measured as different bytes
(`evidence/h58_preflight_integrity.json`). This document is frozen before any H59 code runs; the
hash pinned in `registry/h59_preregistration.json` is the proof of ordering.

## What is already established (and therefore is *not* re-hypothesized here)

* Emitting nothing inside the ≤200 m ring around a mapped trace (knowledge/01 §5, knowledge/10 §2).
* Binary {0,1} emission; per-pixel mass 1.0 is optimal (knowledge/01 §2, pinned by `tests/test_metric.py`).
* The exactly-accounted core `P1 = h33-2-b2 ∩ gems24-d1-5` = 25,517 px with credit bounded in
  [4,168, 5,223], density 16.3–20.5 % vs 2.79 % random (knowledge/10 §3). Core emission alone
  projects DTI 0.2546–0.3190 — it is carried, unchanged, into the artifact.
* The union field `max(p_A,p_B)` is the validated incumbent arm ranking field: 4.6× the matched
  random control, rank 1 of 8 fields, fold-mean lift +0.0037 to +0.0048 (below the registered
  +0.005 promotion bar) — `evidence/h57_validation.json`, `evidence/h57_slot_gate.json`.
* Pseudo-label exchange moves out-of-fold AUC by ≈ +0.003 (noise): knowledge/03 N-1, knowledge/18 §3.
  The exchange is still run here because the brief prescribes it; its result is reported, never used
  to train the shipped artifact.
* A-only as a *population* is refuted (0.000785 vs 0.001057 random): knowledge/18 §4. A-only remains
  a labelled stratum with written reasoning for every emitted candidate.
* Anisotropic 5×3 placement is refuted (+0.000055 tip): knowledge/18 §5. The isotropic 3-px emitter
  is the shipped emitter in every H59 arm.

## The five candidate hypotheses (ranked by expected DTI improvement ÷ implementation cost)

All five are ranking-field transforms of the *already-fitted* out-of-fold view fields, or pools
defined by them, so none requires new external data; every layer cited exists in the pinned staging
(`evidence/band_inventory.json`, `src/gems52/h57.py` layer inventory). All are scored under the
identical registered protocol: whole-component folds, 4-px buffer, prevalence 0.2 %, both
instruments (`tip`, `hide`), budgets 15,000 and 37,654, isotropic 3-px emitter, pool =
`fold region ∧ permitted(∧~200 m ring) ∧ ~dilate(visible catalogue, 2 px)`, plus a uniform random
control rebuilt at each budget.

### H59-A — Pixel-level dual-instrument corroboration of union mass (promoted challenger)

* **Layer(s):** union classifier field `max(p_A,p_B)` (gravity bands 5/11/13/18, magnetic
  1/2/3/9/14, strain 4/7/8, seismicity 10/16, depth 15, conductivity 17 → p_A; DEM 12/19,
  radiometric TC 6 + GeoDAWN K/Th/U ratios → p_B) multiplied by an *independent* high-resolution
  surface instrument: 3DEP 1-m LiDAR scarp coherence × expression (`B_lidar_coh100_val`,
  `B_lidar_ex_max_val`).
* **Physical signature:** ridge-on-lineament coincidence — a thin, laterally coherent scarplike
  curvilinear feature *at* a potential-field edge, i.e. the same line seen by two instruments with
  unrelated error processes. Transform: `x_corroborated = u · (0.55 + 0.45·ℓ)`, ℓ = normalized
  geometric mean of the two LiDAR bands, u = union field.
* **Why it should catch an uncatalogued fault:** the mapped catalogue is a geomorphic/geologic-map
  product; the LiDAR scarp stack contributes resolution the map never had (fault scarps under thin
  alluvial cover are detectable at 1 m even where the field crew saw no scarp), while the potential
  field contributes the buried offset. A pixel where *both independent instruments* corroborate the
  classifier's candidate is exactly the corroboration regime that knowledge/10 §3 measured as a
  ~10× credit-density multiplier at file level (P1 vs single-selection atoms) — H59 tests that law
  at pixel level for the first time.
* **Difference from anything implemented in this repo:** H57 tested binary strata (`q≥0.6` both /
  either) and the *continuous union*, never a continuous corroboration-weighted field; no
  LiDAR-coherence-weighted union field appears in any round's field list (`scripts/validate_h57.py`
  RIDGE_FIELDS, `evidence/h57_strata.json`). Sibling sites fused scarps with radiometrics or DEM at
  file level (GEMSDOE12/46); none did pixel-level corroboration of a *co-trained* union field on
  blocked folds.
* **Rank: 1. Expected relative DTI effect: medium (×1–3 arm-density redistribution at fixed
  budget); implementation cost: low (all layers already in the cached stack).**

### H59-B — The brief's artefact hypothesis as a *suppression*, not a population

* **Layer(s):** B-only stratum (`p_B ≥ 0.60 ∧ p_A ≤ 0.40`) crossed with LiDAR corroboration:
  `x_artifact_suppressed = max(p_A, p_B·(1 − 0.5·[B-only ∧ ℓ < median ℓ of the permitted pool]))`.
* **Physical signature:** linear surface anomalies with no independent scarp-step character and no
  potential-field edge — the signature of roads, irrigation levees, and ephemeral erosion lines that
  dominate LiDAR-derived slope/curvature products of the arid Great Basin (the exact confound the
  brief names for the B-confident/A-abstains case).
* **Why it should raise score without finding anything:** DTI charges mass that no truth pixel can
  reach (knowledge/01 §2). H57 measured that B-only mass is *not* worthless (2.73× random), so the
  honest transform demotes only the *uncorroborated* subset — a strictly narrower veto than dropping
  the stratum.
* **Difference:** `build_h57_submission.py` exposes `--veto-b-only` explicitly documented as "off by
  default because evidence never measured it". H59 *measures* the never-run variant as a first-class
  gate-tested field transform. No prior round scored an uncorroborated-B veto arm.
* **Rank: 2. Expected effect: low-to-medium (precision recovery of a few % at fixed budget); cost: low.**

### H59-C — Active-deformation lineaments: strain-gradient coherence gated by seismicity proximity

* **Layer(s):** geodetic second invariant (band 4) and shear rate (band 7) gradients; structure
  tensor over 12-px scale for strike and coherence; seismicity distance band 10 (inverted rank:
  near events count) as a linear weight; gravity-slope ridge as the existing reference arm.
* **Physical signature:** GPS/InSAR strain localizes in *corridors* along faults that creep or have
  crept recently, expressed as coherent gradient lineaments that survive thick cover precisely
  because they are measured at the surface from space, not from exposed rock.
* **Why it should catch an uncatalogued fault:** the catalogue is a surface-geology product; a
  blind basement fault with measurable elastic strain-rate localization and nearby microseismicity
  has *no geomorphic expression to map* — this is the brief's "buried beneath cover" population
  measured with the instrument the brief under-uses (strain).
* **Difference:** this repo used strain bands as *amplitude features* inside View A's classifier;
  it never tested a label-free strain-lineament coherence field as a *ranking field*, and never
  combined it with seismicity proximity. GEMSDOE sites list none like it.
* **Rank: 3. Expected effect: medium if the 100-m grid preserves the corridor (uncertain — strain
  fields are smoothed at exactly this resolution, so we declare the risk up front); cost: medium
  (one ridge+structure-tensor pass per fold region).**

### H59-D — Corroborated halo beyond the core edge (budget-economics bet on the acceptance bar)

* **Layer(s):** the P1 core (exactly accounted, 25,517 px) and its 3–6 px annulus, intersected with
  `x_corroborated` above and with the global ring/prior-support exclusions.
* **Physical signature:** none new — this is a *population* hypothesis: faults propagate along
  strike, so mass adjacent to double-corroborated mass inherits its density (knowledge/10 §3
  P1 = 16–20 %; the acceptance bar at DTI ≈ 0.30 is ρ ≈ 0.067).
* **Why it should catch an uncatalogued fault:** the truncation instrument (`holdout.tips_of`,
  added exactly because whole-component folds cannot see near-trace mass) measures whether
  continuation of mapped structure earns credit where mapped structure stops; H53/H54 shipped
  strike continuation *without* corroboration weighting — this is the corroboration-gated variant
  at the halo radius the 3-px emitter can actually service.
* **Difference:** H56's continuation arm was selected by whole-grid field top-k; this is
  core-annulus-constrained, ring-aware, corroboration-weighted, and — unlike every prior arm —
  scored with a *registered pool statistic* (≥2× the random control's held-truth adjacency density
  inside the same legal pool) rather than an unscorable novelty claim.
* **Rank: 4. Expected effect: medium-to-large on budget (up to +15 % on core-alone arithmetic if halo
  density holds), but it inherits H57's honest caveat: the simulator measures catalogued truth;
  hidden-truth density stays a prior. Cost: low.**

### H59-E — Conductivity-paired geothermal plumb-line modifier

* **Layer(s):** surface conductivity (band 17) anomaly × thick-cover flag (basement depth 15 > pool
  median) × union field: `x_geoconj = u · (0.6 + 0.4·rank(cond|cover))`.
* **Physical signature:** hydrothermal alteration/clay corridors raise surface conductivity along
  fluid pathways focused by the very fault structures the competition targets; where cover hides
  the outcrop, conductivity is the only surface-accessible witness.
* **Why it should catch an uncatalogued fault:** the USGS/INGENIOUS maps carry no radiometric or
  conductivity information; a conductivity corridor with a coincident potential-field edge under
  cover is a fault hypothesis that neither the catalogue nor the DEM-based views can produce.
* **Difference:** H55 screened thermal layers and shipped `h55_thermal_layers.json` (band 6 identity
  work); the *modifier* role (weighting an existing co-trained field rather than selecting on
  conductivity itself) is new, and it is the only hypothesis here that speaks to the competition's
  geothermal-systems purpose directly rather than to fault geometry alone.
* **Rank: 5. Expected effect: low on DTI (clays are spatially broad, the metric rewards thin
  placement; risk of diluting precision); cost: low.**

## Decision rules, frozen before the run

* **Independence / abandonment:** per-50×50-block out-of-fold error correlation on labelled
  negatives, whole-segment folds, 4-px buffer; `max|r| ≥ 0.60` ⇒ abandon co-training, report the
  refutation, and fall back to the better single view as the arm field (labeled as such).
* **Field promotion (the only rule that changes the artifact):** a challenger field replaces the
  incumbent union field for arm selection **iff** its fold-mean DTI exceeds the union's in **all
  four** cells {tip, hide} × {15,000, 37,654}. Ties and single-cell wins do not promote. If none
  promotes, the artifact ships with the union field, and that is reported as the incumbent result,
  not a new one.
* **Slot-approval bar (repo's standing registered rule):** mean lift vs the matched random control
  ≥ **+0.005** on **both** instruments at 37,654 **and** ≥ 3/4 folds positive on each. No artifact
  is approved to spend a weekly slot below this bar regardless of gate passing otherwise. The
  site's status line will say "OK to download; **do not** spend a weekly slot" unless this bar is
  met by the field that actually shipped.
* **H59-D gate (population statistic):** corroboration-weighted halo pool must reach ≥ 2.0× the
  random control's held-truth (k-weighted) density in the same legal pool on the `tip` instrument;
  failure ⇒ halo not emitted, arm falls back to full-grid field top-k.
* **Novelty / not-a-union / ring / format gates:** unchanged repo gates (`src/gems52/gates.py`):
  decoded pattern differs from every accessible aligned prior; arm 100 % outside the prior-support
  union; min distance to catalogue ≥ 200 m; single band float32 EPSG:32611, 3,730 × 3,292,
  transform pinned to `[100, 0, 243350, 0, -100, 4508550]`, all finite, values exactly {0,1}, no
  nodata tag; artifact is not the union of any two accessible priors; the `not merely union of the
  two views` check is literal: fraction of arm pixels outside the top-k of the *plain* union field
  must be > 0 when a challenger ships, and the report says so either way.
* **A-only reasoning:** every emitted A-only arm pixel and every whole-segment A-only candidate
  above the field threshold (top 5,000 segments by mean union mass) gets a written reasoning row
  with measured band values and an explicit falsifier; reasoning strings are generated from
  measurements, never from prose.

## Seeds, runs, and reproducibility

`SEED = 20261009` everywhere (new seed, distinct from H57's 20261007, so no repeated-run guard
collides and no result can be back-fitted to the incumbent's fold draws). Fold geometry, thresholds
(0.60/0.40), prevalence target 0.002, budgets (15,000; 37,654), BLOCK = 50, MIN_NEG = 300 are
verbatim from `scripts/run_h57_cotrain.py` so challengers and the incumbent's published numbers are
comparable; the incumbent union arm is **re-measured inside this run** and the incumbent-vs-frozen
delta is reported (guards against any environment drift).
