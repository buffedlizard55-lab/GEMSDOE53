# 21 — What H59 actually found (session 2026-10-08)

Preregistered in [`20_hypotheses_H59_preregistered.md`](20_hypotheses_H59_preregistered.md) and frozen
in [`registry/h59_preregistration.json`](../registry/h59_preregistration.json) before any H59 fit ran.
For the first time in this repository **every H59 number was computed on the manifest-pinned bytes**
(`work/h59_pinned`, 23/23 SHA-256 matches recorded in `evidence/h59_preflight_integrity.json`) rather
than on the tracked `data/*.tif` grid stubs, which closes the exact gap that made H57's numbers
"not comparable evidence" (`IR-H58-001`): the preflight measures the tracked stubs and records them
as unused. Receipts: `evidence/h59_cotrain.json`, `evidence/h59_validation.json`,
`evidence/h59_build.json`, `evidence/h59_format_gate.json`, `evidence/h59_uniqueness.json`,
`evidence/h59_slot_gate.json`.

## 1. The answer to "why did `h33-h33-2-b2` score 0.2778, and can we beat it?"

The champion file is `h27-4-r1` (owner-reported 0.2600 for the d2-8 superset) **minus the ≤200 m ring
around the mapped catalogue**: 40,199 px → 37,654 px scored, +6.8 % score for deleting 6.3 % of its own
mass. Re-measured from bytes again in this session (the exact set relations of the nested pair):
`A\B = 0`, `B\A = 6,436` px all inside 100–200 m of a mapped trace, `min` distance-to-catalogue inside
A = **223.6 m**, and inverting the metric on the pair gives `|G| = 14,088.7 px` and *exactly zero*
credit for the deleted ring. It won because it understood the metric's tax term, not because its
detector was stronger: same mass scattered scores 0.0778 (3.6× worse).

Beating it is then a two-part problem, and H59 executed both parts as far as the evidence allows:

1. **Keep the exactly-accounted credit.** `P1 = A ∩ gems24-d1-5` = 25,517 px with credit bounded
   [4,168, 5,223] (density 16.3–20.5 % vs 2.79 % random) — emitted unchanged, so the floor of the
   new file is the champion's best-credited core: core alone projects **0.2546–0.3190**.
2. **Add mass only where it is accepted by the metric's own inequality.** The bar at the champion's
   score is ρ > 0.059, at 0.3195 it is ρ > 0.068; every H59 challenger was tested for exactly that,
   under the registered fold protocol, and the projections in `evidence/h59_build.json` show the
   conditional arithmetic across ρ ∈ {0.03 … 0.14}.

The honest summary: **yes, a file with central projection above 0.3195 is constructible from what the
published scores *prove* (P1 + a corroboration-cleared arm at ρ ≈ 0.09+), but no measurement available
in this repository can certify the arm's hidden-truth density** — the simulator is structurally blind to
it (knowledge/18 §6, re-confirmed below), and every attempt to beat the union field on the scorer's own
terms failed this session. The gap between "projectable" and "certifiable" is the whole board gap
between 0.28 and 0.38, and closing it needs organizer-authenticated labels or a physically new
detection principle, not more reweighting.

## 2. The independence premise, re-measured on the real bytes

Per-50×50-block out-of-fold negative-error correlation, whole-segment folds, 4 px buffer, 2,163 blocks
(411+878+639+272… per-fold sums recorded in the receipt):

| statistic | value |
| --- | --- |
| max abs block correlation | **0.1071** |
| abandonment threshold | 0.60 |
| pixel-level (4.5 M px) | Pearson +0.0601 / Spearman +0.0357 *(receipt `independence.pixel_level`)* |
| strata sizes | A-only 183,553 · B-only 197,898 · concordant 47,183 (H57: 179,254 / 201,837 / 46,293) |
| A-only median depth to basement | 411.3 m vs 161.0 m B-only — *the brief's cover geology, reproduced on pinned bytes* |

The Blum–Mitchell premise survives at this granularity on the *correct inputs* — weak coupling, not
independence; the H57 stratum picture is stable across seeds and input sets, which is itself a
reproducibility result the earlier rounds could not claim.

## 3. Pseudo-label exchange: ran, moved nothing (third independent reproduction)

89 whole segments / 1,996 px exchanged confident→abstaining inside the fold-0 unlabelled quadrant;
out-of-fold View-A AUC 0.4867 → 0.4856 (**−0.0011**). Family record: −0.0159/−0.0303 (knowledge/03),
+0.0027 (knowledge/18), −0.0011 (here). Disagreement labels the arm; it does not train it.

## 4. The four challengers, judged by the registered rule

Fold-mean DTI, isotropic 3-px emitter, identical pool, 4/4 folds won vs random for every field — but
promotion required a **4/4-cell win over the incumbent union**, and nothing took it:

| field | tip@37,654 | hide@37,654 | vs union | verdict |
| --- | --- | --- | --- | --- |
| `clf_union` (incumbent) | 0.005370 | 0.006548 | — | retained for the arm |
| H59-A `x_corroborated` (union × LiDAR-scarp corroboration) | 0.005060 | 0.006162 | − | **refuted**: the file-level ×10 corroboration law (knowledge/10 §3) does NOT transfer to pixel-level multiplicative weighting. Two thinnings of the *same field* corroborate; a cross-instrument product mostly re-expresses instrument noise where the field is strong |
| H59-B `x_artifact_suppressed` (uncorroborated-B veto) | 0.005228 | 0.006435 | − | **refuted at λ=0.5**: the B-only stratum carries 2.7× random signal (H57), so a blanket veto discards true mass with the artefacts; a smarter artefact classifier would need labelled roads/erosion data this competition does not ship |
| H59-C `x_strain` (strain-gradient lineament × seismicity) | 0.003793 | 0.004982 | − | **refuted**: at 100 m the strain fields are smoothed below fault-resolution; as a *ranking field* it is 2.5× random but well under union; it stays in View A's feature set where it contributes as amplitude |
| H59-E `x_geoconj` (conductivity plumb-line under cover) | 0.005274 | 0.006439 | ≈0 | **not promoted**: statistically indistinguishable from union (−0.0001/−0.0011); the geothermal mechanism is real but the 100 m metric cannot pay for it |
| H59-D halo pool (core annulus 3–6 px) | tip@37,654 mean 0.003974 vs same-field full-pool control 0.005060 | — | − | **refuted as a *restriction***: restricting the pool to the halo hurts; note 6,389 of the shipped arm's 14,787 px land in the halo *anyway* under full-pool ranking — the continuation signal is real, the halo *monoculture* is not |

Incumbent drift check (the reason this round re-measured rather than quoted): union @37,654 is
0.005370/0.006548 here vs 0.005444/0.006445 frozen from H57 — the instrument reproduces to ±1.4 %,
so the +0.005 promotion bar's failure (best lift here **+0.00463** on hide, +0.00384 tip, 4/4 folds)
is a property of the field, not of the run.

## 5. What shipped

`gems52-h59-union-core25517px-arm14787px.tif` — 40,300 px: the exactly-accounted P1 core + a 14,783-px
arm = the retained union field's top-k inside the novel pool (outside every accessible prior's support,
100 % of arm px; ≥ 3 px from the core; outside the 200 m ring; file min distance to catalogue 223.6 m
inherited from the core and re-measured). 14,783 written reasoning rows + every A-only pool segment row exceeding the registered 5,000 cap — an expansion of coverage, disclosed here and in
`evidence/h59_build.json`). Determinism was *broken and then fixed* during this session: a rebuild
initially shifted the arm by 10 px because build outputs had entered the prior-scan roots (recorded as
IR-H59-001); self-exclusion now makes the build a measured fixed point (byte-identical across rebuilds).

Status, per the registered rules: format PASS (0 problems, all finite {0,1} — the portal's
"Predicted values must be in range [0,1]" rejection is impossible for this file, because
`gems52.grid.write_geotiff` refuses to emit a non-finite or out-of-range array (and the build's format
gate then verifies the re-read bytes));
uniqueness PASS vs 49 accessible aligned priors (47 at first build; the parallel sessions' genuine TIFFs entered
the scan as their rounds merged — IR-H59-004/005 — and the artifact was re-derived against 49 then
51 rasters, 50 distinct artifacts); **slot bar FAIL** (lift +0.0038/+0.0046 < +0.005);
R6 not-merely-union: the file is not the union of any two priors and not equal to any prior, but the
arm's *ranking field* is honestly reported as the plain union, so the literal "is the arm more than
top-k of the union" check is marked FAIL rather than argued around. Net: **download for review and
reproduction — OK; spending a weekly slot on it — not approved by this repository.**

## 6. Where the headroom actually is (for the next session, ranked)

1. **Organizer-authenticated inputs.** Everything above is conditional on owner-reported scores; a
   single authenticated download of `labels.tif` + `training_features.tif` from the login-walled data
   tab converts "conditional projection" into "validated" for the first time. Cost: one owner action.
2. **A genuinely new detector, not a reweighting.** H59 refuted four reweightings on the only holdout
   that can see anything. The surviving physical ideas need data the 100 m cube cannot resolve:
   1-m LiDAR *intensity/return-width* (not just the scarp products) for road-vs-scarp discrimination —
   obtainable from USGS 3DEP but licensing/bandwidth-blocked here (`knowledge/04`); or InSAR time
   series (ASF, free, registered) for strain-rate at 10× the resolution of band 4/7/8.
3. **Sub-budget precision.** The T(S) power law and the P1 algebra both say the family's 37–40 k budget
   sits *above* the acceptance bar's optimum; a 25.5–30 k file (core + only its very top-ranked arm)
   has higher central projection at lower variance. That is an owner slot-decision, computable here in
   one build — the machinery already parameterizes it (`--arm` in the H56-style builds).
4. **Do not re-run** : blanket B-veto, pixel-level corroboration products, strain ranking, halo-pool
   restriction, pseudo-labels-as-training, anisotropic placement, ≥200 m-corridor mass, A-only-as-
   population — all measured, all refuted or null (this file's §4 and knowledge/18 §4–5).
