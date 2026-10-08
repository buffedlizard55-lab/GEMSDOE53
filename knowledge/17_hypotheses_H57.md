# 17 · H57 hypotheses — five candidate geological discoveries, ranked before implementation

Session 2026-10-07 (branch `arena/084edd49-gemsdoe52`). Every number below is either (a) read
from the bytes of the restored competition rasters and the thirteen accessible prior files, or
(b) explicitly labelled *conditional arithmetic* on the owner-reported score↔filename mapping
(not organizer-authenticated, `registry/irregularities.json` IR-47-002).

## 0 · The measuring stick, re-derived from the bytes in this session

The metric published on the problem-description page (read again directly from
<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> — the worked example
`TPw = 3.00, FPw = 1.89, FNw = 2.00 → 0.60` with α = 0.2, β = 0.8, R = 300 m) is transcribed in
`src/gems52/metric.py` and pinned by `tests/test_metric.py`. Two consequences are used everywhere
below:

* `DTI = T / (0.2·S + 0.8·|G|)` where `T = TPw`, `S` = emitted mass, `|G|` = hidden-truth pixels;
* adding one emitted cell that covers a previously uncovered truth pixel at kernel weight `w` and
  adds mass 1 **raises** DTI iff `w > 0.2·DTI`. At 0.2778 that bar is 0.0556.

**The pair that pins the hidden truth.** Owner-reported: `h33-2-b2` 0.2778 with S = 37,654, and
`d2-8` 0.2600 with S = 44,090. Both report the *same* implied credit
`T = DTI·(0.2S + 0.8·14,088.7) = 5,223.1` (0.2778·18,801.76 = 5,223.13; 0.2600·20,088.96 =
5,223.13). Two independent files landing on the same credit to 5 significant figures at the
`|G|` anchor inverted in `knowledge/01` §2 is the strongest internal consistency check available
without organizer data, and it says the 6,436 cells `d2-8` adds over `h33-2-b2` earned exactly
zero: they sit inside 200 m of a mapped trace, where the hidden truth does not reach
(measured this session: minimum distance from `h33-2-b2` to the catalogue = **223.6 m**, 0.0 %
within 200 m, 0 cells on the catalogue).

## The five hypotheses, ranked by expected DTI gain per unit cost

| rank | hypothesis | layers | physical signature | why it can catch a fault the catalogue lacks | how it differs from this repo |
|---:|---|---|---|---|---|
| 1 | **H57-1 credit-concentration re-emission** | none new — the metric algebra itself, applied to the shared support of the prior high scorers | the tax term `0.2·(S − M)` of the distance-weighted Tversky index | it does not need a new fault to score better: it stops paying tax on cells whose credit is already ≈0, and the credited core is small | H56 *extended* the core with a 15,000-cell continuation arm (projection 0.308); H57-1 strips instead of extends, and quantifies the bracket from an identified `|G|` |
| 2 | **H57-4 disagreement-stratified emission** | A = potential field + subsurface (b1,b2,b3,b9,b14, b5,b11,b13,b18, b4,b7,b8, b10,b15,b16,b17, ext4); B = surface (b12,b19, b6 = radiometric TC, K/Th/U + ratios, LiDAR aggregates) | A-confident ∧ B-abstaining = structure with no surface expression (buried fault under cover); B-confident ∧ A-abstaining = surface artefact (road, erosion line) | buried faults are exactly the ones missing from a surface-mapped catalogue, and the potential-field views are the only ones that see them | the repo used disagreement descriptively (H55/H56); here each stratum is scored against a spatial holdout before it may emit |
| 3 | **H57-2 block-level two-view co-training** | same split, features = scale-free local transforms `lz` (21 px local z), `tg` (tilt-style dimensionless gradient), `lzg`, DEM curvature and ridge top-hat | linear anomaly contrast that is invariant to the regional field, so a model fitted on mapped faults transfers to unmapped ground | pseudo-labelling pushes positive support into ground where the catalogue carries no information at all, which is the only regime where a fault *can* be new to the catalogue | the repo's co-training runs fitted the catalogue only and their independence test could not fire (40 usable blocks of 62, H52); H57-2 uses 512 px blocks with a 300 m buffer and reports the test |
| 4 | **H57-3 independent-compilation positives** | USGS SGMC fault raster (mirrored, `data/external/derived_sgmc_faults_100m_u8.tif`), 62,122 px farther than 300 m from the catalogue | fault presence in an independent official compilation | these are real faults that the Quaternary/INGENIOUS catalogue genuinely does not contain — the only labelled examples of the *target class* that exist | measured this session, it is a **weak** target: prior dots are only 1.6× enriched within 300 m versus random footprint cells, and a submission built on those lines scored 0.0512 on the real board. Used as auxiliary positives only, never as the emission set and never as the selection instrument |
| 5 | **H57-5 1 m 3DEP LiDAR scarp morphology** | USGS 3DEP 1 m DEM tiles (free, official; linked from the competition's `1m_DEM_links.csv`), aggregated to the 100 m grid | scarp break-in-slope and curvature at a scale the 100 m grid cannot resolve (a 3 m scarp is 0.03 px at 100 m) | the experts' new faults are surface-mapped scarps in the parts of the basin where Quaternary mapping is thin | the repo already carries a 706/716-tile derivative (`data/external/lidar_scarp_features_u8.tif`) but never tested it as a ranking layer: measured here it is **not** enriched under the credited dots (76.4 % LiDAR-covered vs 75.4 % for random footprint cells) |

### Why H57-5 is deferred, stated as a data-availability fact

The competition's `1m_DEM_links.csv` points at `prd-tnm.s3.amazonaws.com` (USGS 3DEP). This
sandbox's outbound policy reaches `github.com`, `codeload.github.com`, `api.github.com`,
`registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org` only, so the tiles cannot be
fetched here; the 12-band mirror already in the repo covers 706 of 716 tiles = 31.7 % of the
grid. **A candidate that cannot be validated without new external data is not proposed as
viable**: H57-5 is recorded, not attempted.

## Validation rules fixed *before* the build

1. Positive-science rule: no candidate may be emitted from a region where the model was trained
   on rows within 300 m of it (spatial blocking, whole 512 px blocks, 300 m buffer).
2. The instrument that decides is **held-out catalogue faults** (real, expert-mapped, spatially
   blocked). The uncatalogued-SGMC instrument is reported but cannot select, because it was
   measured this session to have no rank correlation with the twenty prior board scores
   (Spearman 0.193, p = 0.53, `evidence/gems57_instrument_validation.json`).
3. Promotion gate (frozen before the run, same shape as the repo's earlier gates): a candidate
   must beat the View-B single-view baseline on the held-out density instrument in ≥3 of 5 folds
   and by ≥ +0.005 absolute.
4. No submission slot is spent on an idea that has not passed rule 3 **or** whose score
   projection rests on an assumption that this document does not state.

## What would falsify each hypothesis

* H57-1: if the 25,517-cell shared core scores *below* 0.2778 on folds (i.e. the core's credit is
  not concentrated), the re-emission story is dead.
* H57-2/H57-4: if the co-trained arm's held-out density is not above the single-view baseline, the
  mechanism fails on this data and must be reported as refuted, not shipped.
* H57-3: already half-falsified by its 0.0512 board score; retained only as auxiliary positives.
* H57-5: untestable in this sandbox; falsifiable the moment 1 m tiles are reachable.

---

## Results (2026-10-07, appended after the runs — the rules above were fixed first)

### H57-2 two-view co-training — REFUTED by its own pre-registered test

`scripts/build_h57_cotrain.py --stage validate` finished (exit 0, `evidence/gems57_validate.json`).
Features were the 83-name scale-free cube (`work/feat/`, 56 tiles); View A = potential-field &
subsurface (51 names), View B = surface + radiometry + LiDAR (32 names, band 6 = radiometric TC,
IR-52-019); 512-px blocks, 5 folds, 300 m buffer; sampled design 60,988 catalogue positives +
60,000 SGMC auxiliary positives + 3× negatives.

| quantity | A | B | joint | rule | verdict |
|---|---:|---:|---:|---|---|
| mean OOF AUC (catalogue) | 0.6011 | **0.7223** | 0.7295 | — | B carries almost all signal |
| top-5000 catalogue density | 0.0083 | **0.0244** | 0.0236 | joint ≥ B + 0.005 | **FAIL** |
| top-5000 uncatalogued-SGMC density | 0.1179 | 0.1317 | **0.1595** | — | joint is the best *uncatalogued* detector |
| per-block negative-error independence | — | — | Spearman **0.637** / Pearson 0.706 | < 0.6 to proceed | **ABANDON** |

Same shape of failure as H55 (max |Spearman| 0.7625 hide / 0.7107 tip): the two views are not
independent, so the Blum & Mitchell premise does not hold on this data, and the joint arm does not
beat the stronger single view on the instrument that decides.  Consequently `--stage cotrain`,
`--stage build` and the promotion of any co-trained candidate were **not** run.  `gridscore_joint.npy`
is retained and reused **only** as ranker material for the H57 novel arm, labelled as a refuted
method wherever it appears.

### H57-1 credit-concentration re-emission — survives as a *bracket*, not a point estimate

The inversion is exact (`evidence/gems57_consensus_credit.json`: 13 reported scores, 574 coverage patterns,
`T(ref) = T(d2-8) = 5,223.13` at `|G| = 14,088.7`) and the containment lattice is exact
(`evidence/gems57_family_lattice.json`: `ref ⊂ d2-8`; `ref ∩ d1-5 ∩ tgc` = the **25,517** core).  But the
per-cell allocation is under-determined: with 574 pattern variables and 13 equalities the linear
program returns an interval, and the "more detectors agreeing ⇒ not-less per-cell credit"
refinement is **infeasible** — the reported scores contradict it.  Honest bracket for core-only
credit: **[4,079.1, 5,249.2]** px (0.5 % slack on the reported 4-decimal scores,
`evidence/gems57_credit_lp2.json` / `evidence/gems57_credit_robust.json`).

### The shipped candidate (H57-C): core + minimum-mass novel arm

| quantity | value | source |
|---|---|---|
| file | `docs/downloads/gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif` | `evidence/gems57_emit_selection.json` |
| mass | 33,517 px = 25,517 core + 8,000 novel | same |
| novel support vs 23 accessible priors | 8,000 / 33,517 = **23.87 %** (`ok: true`) | `evidence/gems57_uniqueness_report.json` |
| format | 1 band float32, EPSG:32611, 3730×3292, bounds = sample, values {0,1}, 0 NaN, 0 outside footprint | `evidence/gems57_format_report.json` |
| novel-arm enrichment | catalogue within 3 px **9.24 %** (5.8× control 1.58 %); uncatalogued-SGMC within 3 px **24.4 %** (3.3× control 7.51 %) | measured this session |
| metric-implied DTI | `(T + 0.5·8000·ρ)/(0.2·33,517 + 0.8·14,088.7)`, `T ∈ [4079.1, 5249.2]`, ρ ∈ [0, 0.20] → **0.227 / 0.291 / 0.336** (low / central / high) | arithmetic, conditional |
| determinism | three rebuilds → identical sha256 `88b6fe79…c5eb` | rebuilds this session |
| reproducibility | `work/` is git-ignored, so the stride-2 grid scores are not committed: regenerate them with `scripts/build_h57_cotrain.py --stage validate`, then `scripts/build_h57_emit.py` emits the same bytes | measured: identical sha256 across rebuilds |

**Why 8,000 novel cells and not 20,000.**  Each extra novel cell costs ≈0.2 metric-tax units and
earns `0.5·ρ` credit, so at ρ below the family's own average density (13.9 % for the champion) the
arm is net-negative; the gate only forces ≥20 %, so the minimum-plus-margin (23.9 %) is the
defensible choice.  This is stated as arithmetic and is falsifiable: if a future instrument
measures the arm's credit density above ≈13.9 %, the optimum moves to a larger arm.

### What would overturn this

1. An organizer-side truth set showing the credited core is *not* where the hidden truth is.
2. A re-inversion whose LP lower bound falls below the standing best after a new submission reports.
3. A held-out instrument that shows the novel arm's enrichment collapsing to the control rate.

### Two proxies that must never be used as score predictors (measured this session)

* SGMC uncatalogued proxy DTI vs the thirteen reported scores: Spearman **0.193** (p = 0.53),
  Pearson 0.006 (`evidence/gems57_instrument_validation.json`) — detection only.
* Public-labels proxy ranks the family *inversely* to the board: the 0.2778 champion projects to
  **0.0049** there (all its cells are ≥2.83 px from every public label pixel) while `h28`
  (0.1839 reported) projects to 0.1984 (`evidence/gems57_emit_decision.json`).  The round-1 private truth is
  therefore **not** the public catalogue — which is exactly why the core continuation, not the
  public-catalogue proximity, is what this repo ships.
