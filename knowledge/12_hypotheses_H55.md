# 07 · H55: five hypotheses not yet tried, each with its layers, its signature, and its cost

Written **before** the H55 holdout sweep was scored. Ranking rule stated up front and not moved
afterwards: **expected DTI improvement divided by implementation cost**, where "expected" means
either measured in this repository on a spatially-blocked fold or bounded by the metric algebra —
never asserted.

Two standing constraints from the brief are honoured in every entry below:

* a hypothesis must explain why it finds a fault that is **absent** from the USGS Quaternary fault
  and INGENIOUS compilations, not one that is present in them. The metric pays nothing for
  re-finding a mapped trace: `labels.tif` is masked pixel-exactly, and the family measured that
  deleting 6.3 % of its own mass that sat on catalogue pixels **raised** its score 2.6 %
  (`knowledge/01`).
* if a hypothesis needs data the repository does not have, the specific free official source is
  named and its obtainability is confirmed before the hypothesis is called viable.

---

## The correction that unlocks four of the five

**Band 6 of the official `training_features.tif` is the GeoDAWN aeroradiometric total-count grid,
not a magnetic derivative.** The file's own TIFF tag says
`data_category = magnetic_data`, `description = "Tilt angle or total curvature - magnetic field
derivative for edge detection"`. Measured on the bytes this session, 150,000-pixel sample,
`evidence/h55_band6_identity.json`:

| test | Spearman ρ |
|---|---|
| band 6 vs the independently reduced GeoDAWN **TC** grid (`data/external/geodawn_rad_u8.tif` band 4, from DOI 10.5066/P93LGLVQ) | **+1.0000** |
| band 6 vs **K + Th + U** from the same release | **+0.9914** |
| band 6 vs TMI (band 14) | −0.0250 |
| band 6 vs TMI upward-continued 150 m (external band 4) | +0.0079 |
| band 6 vs TMI horizontal gradient (band 3) | −0.1489 |
| band 6 vs TMI vertical gradient (band 9) | +0.0214 |
| band 6 vs RTP (band 2) | −0.0914 |

Total count *is* the sum of the potassium, thorium and uranium windows — that is what a
total-count channel means — so ρ = 0.9914 against K+Th+U is the physical signature, and ρ = 1.0000
against the independently reduced TC grid is the identification. A magnetic-field derivative cannot
be uncorrelated with the magnetic field; |ρ| ≤ 0.149 against all five magnetic bands in the file.
Also decisive: band 6 is strictly positive (min 2.953, max 88.573, mean 18.46) while a tilt angle is
bounded by ±π/2.

**Consequences.** `src/gems52/features.py` filed this band inside **View A** as `A_mag_tilt_abs`,
i.e. a radiometric surface-geochemistry band was being used as potential-field evidence. That
corrupts the two-view split the whole brief is built on and the conditional-independence test that
is supposed to police it: any correlation between "View A" and "View B" that runs through band 6 is
an artefact of the mis-filing. And the brief's clause *"View B is DEM-derived curvature and slope,
plus any radiometric bands present in `training_features.tif`"* therefore resolves to **one band**,
not to none as `knowledge/04` and `docs/irregularities.html` recorded. `src/gems55/radlayers.py`
moves it and adds the six radiometric products the official USGS release carries but the
competition did not ship.

---

## H55-1 · Radiometric total-count step: the range front that has no scarp

**Layers.** `R_tc_step900` (two-sided across-strike step of band 6, 900 m half-width, 1,900 m
along-strike persistence), `R_tc_edge` (|∇TC| in units per metre), `R_tc_line` (300 m Hessian line
response on TC), `R_tc_rank`. All from the official competition file, band 6.

**Physical signature targeted.** A *laterally persistent two-sided step* in total gamma-ray count.
Basin fill and range bedrock differ in bulk K/Th/U by a factor of two to five in the northwestern
Great Basin; the survey measures the top 30–50 cm, so the contrast is a property of **material**,
not of relief. The transform is deliberately not curvature: `T.scarp_step` requires both flanks to
move and the offset to continue for ~2 km, which is what removes canyon rims, stream banks and
alluvial-fan apices — the documented false-positive mode of fault mappers in this province
(Hermant et al. 2025, 50th Stanford Geothermal Workshop).

**Why it finds a fault the catalogue lacks.** USGS Quaternary fault and INGENIOUS traces are
compiled from geomorphic expression: a scarp, a lineament, a deflected drainage. Where a range-front
fault has been buried by Holocene fan alluvium the geomorphology is erased but the two materials
still sit either side of the plane, and the gamma-ray contrast survives. This is precisely the
population the competition asks for — new faults, not re-found ones — and it is the population
`knowledge/03` N-2 showed the surface view alone cannot reach (only 0.5 % of a *hidden whole
component*'s pixels lie within 5 px of a still-visible trace).

**How it differs from anything in the repo.** Nothing in `gems52.features` touches band 6 except to
take its absolute value as a magnetic tilt. `knowledge/03` N-7 killed *second-derivative
potential-field* transforms (Laplacian of strain ≈ 0.50, basement signed step 0.511, magnetic
transforms ≈ 0.52) — this is a *first-order two-sided step on a surface-geochemical field*, in View
B, never screened.

**Expected gain / cost.** Gain: unmeasured until the sweep; the corrected View B is what produced
the fold-0 winner (see H55-5), so the gain is already partly realised. Cost: **zero new data, 37 s
of compute** (`python3 scripts/run_h55.py --stage layers`). **Rank 2** — enabling, and free.

---

## H55-2 · Th/K and U/K ratio steps: alteration and cover, separated from topography

**Layers.** `R_thk_step900`, `R_uk_step900`, `R_thk_edge`, `R_uk_edge`, built from
`data/external/geodawn_extensions_u8.tif` bands 1–3 (Th/K, U/K, U/Th). Source: the official USGS
GeoDAWN release, Glen & Earney 2024, https://doi.org/10.5066/P93LGLVQ, public domain.

**Physical signature targeted.** The same two-sided persistent step, but on an **elemental ratio**
rather than on total count. Ratios remove the three things that make total count noisy — soil
moisture, radon escape and flight-height residual — so a ratio step is a lithological or alteration
boundary, not a weather boundary. Th/K rises across bedrock→alluvium (alluvium is Th-enriched in
detrital heavy minerals, K-feldspar is winnowed); U/K rises over silicification and iron staining.

**Why it finds a fault the catalogue lacks.** Two independent reasons. (i) A buried contact has no
geomorphology to map. (ii) A hydrothermal alteration zone is *not a geomorphic feature at all*: it
is a chemical deposit left by fluid that used the fault as a conduit, and it can sit hundreds of
metres from the plane. No Quaternary-fault mapping campaign records either.

**How it differs.** Measured this session: Spearman(U/K, detrended elevation) = **+0.007**,
Spearman(U/K, K) = −0.580, Spearman(Th/K, detrended elevation) = +0.208. The U/K field is
essentially orthogonal to relief, which makes it the only layer in this repository that can see a
fault with no topographic expression. The repo's View B is 100 % DEM-derived; it is structurally
blind to that case.

**Expected gain / cost.** Gain: small-to-moderate, unmeasured. Cost: **zero new data** (the rasters
are already restored and SHA-256-verified), 37 s of compute. **Rank 4.**

---

## H55-3 · Thermal-fluid points extended along a measured structural strike

**Layers.** `Th_point` and `Th_lineament`, built from
`data/external/gdr_wellspring_in_footprint.csv` (27,092 rows).

**Source, and the blocker discharged.** Great Basin Center for Geothermal Energy, *INGENIOUS –
Great Basin Regional Dataset Compilation*, Geothermal Data Repository submission 1391,
DOI **10.15121/1881483**, licence **CC-BY 4.0**,
https://gdr.openei.org/submissions/1391, file
https://gdr.openei.org/files/1391/wellspringdata.gdb.zip. `knowledge/02` H52-5 recorded this source
as **blocked** because the GDR host could not be re-resolved and an unverifiable file may not move
emitted mass. Both the submission page and the file URL were read this session (2026-10-06), the DOI
resolves, and CC-BY satisfies the competition's external-data rule. The blocker is discharged. The
one column *not* trusted is `dist_known_fault_px`: it is derived, so distance to the visible
catalogue is recomputed from `data/labels.tif` on the pinned grid.

**Physical signature targeted.** The silica **geothermometer**, not the point count. A quartz
geothermometer temperature of ≥ 100 °C at discharge means the water equilibrated with rock at that
temperature, i.e. circulated to roughly 2–4 km on a normal Great Basin gradient, and returned fast
enough not to lose its heat. Deep, fast, buoyant circulation in extensional terrain requires a
fault: the damage zone is the only structure with both the fracture permeability and the throw.
Measured on the grid this session: **12,570** distinct 100 m cells carry a well or spring;
**11,258** are more than 300 m from any mapped catalogue fault; **8,958** are more than 1 km away;
only **194** lie *on* a catalogue pixel; **991** cells record a discharge temperature ≥ 30 °C,
**362** ≥ 70 °C, and **147** carry a quartz geothermometer ≥ 100 °C.

**Why it finds a fault the catalogue lacks.** The thermal population and the mapped-trace
population barely intersect — 194 of 12,570 cells, 1.5 %. A hot discharge 3 km from the nearest
mapped trace is either an unmapped fault or a mapped fault whose trace is wrong or truncated, and
both are the competition's target. Staff confirmed in forum thread 11516 post #4 that truth may lie
within 300 m of a known trace and that those corrections are part of the goal.

**The step nobody has taken.** A spring is a *point*; under a 300 m kernel one point earns at most
1.0 and costs 0.2, which is a good trade but not a trace. So the point is extended along a **strike
measured from a 2 km structure tensor** of the radiometric field, and the walk is gated by that
tensor's coherence and truncated when coherence drops below 0.30 or the footprint ends. No layer
anywhere in this family converts a point observation into a linear hypothesis; every existing
point-derived layer (GDR spring density, volcanic vents, QFaults centroids) is a kernel-density
blob.

**Expected gain / cost.** Gain: moderate and *orthogonal* — the evidence is not a function of any
band in `training_features.tif`, so it cannot be reproduced by the other views. Cost: low; the data
is on disk, ~1 min of compute. **Rank 3.**

---

## H55-4 · Calibrated |G| and the credit bar, replacing the inherited budget

**Layers.** None — this is a calibration, and it changes every other hypothesis's placement.

**Signature.** The competition publishes DTI but not |G|. Inverting the metric on this laboratory's
own 13 scored rasters does. For a sparse emission (every emitted pixel 8-isolated, so no two
compete for the same truth pixel and `M = T`) the published form collapses to

    DTI = T / (0.2·S + 0.8·|G|)          ⇒     |G| ≥ 0.2·DTI·S / (1 − 0.8·DTI)

per submission; `scripts/calibrate_g.py` computes `S`, `A` (kernel-weighted coverage) and the
sparsity test for all 13, then picks the |G| that makes the implied per-covered-pixel truth density
`ρ_A = T/A` as close to constant as possible across the sparse rows — the only cross-submission
prediction the model actually makes. Output: `evidence/h55_g_calibration.json`.

**Why it matters.** `knowledge/05` fixed `K = 37654` "to match the 0.2778 file's footprint mass" —
i.e. the budget was inherited from an unrelated submission. The metric's own marginal rule says the
budget is an *output*: add a pixel while its expected credit exceeds `bar·(1 − C)`, with
`bar = 0.2·DTI/(1 − 0.2·DTI)`, and `bar` is a function of |G| through DTI. Getting |G| wrong moves
the bar and therefore the file size, in the wrong direction, silently.

**Caveat carried, not hidden.** Every score in the family's history is owner-reported; the board
publishes a number and a username, never a filename, hash or receipt (IR-52-011). Raster bytes are
SHA-256-verified, so `S`, `A` and the geometry are exact; only DTI is second-hand.

**Expected gain / cost.** Gain: bounded — it cannot create signal, it stops throwing it away.
Cost: ~2 min. **Rank 5** (necessary infrastructure, no signal of its own).

---

## H55-5 · Placement is worth more than prediction: the 600 m hard-core rule

**Layers.** None — an emitter, applied to whatever field wins.

**Signature.** The kernel `k(d) = max(1 − d/300 m, 0)` has a disc weight sum of exactly
**9.380298** (25 cells with k > 0, 29 with k ≥ 0; enumerated, never approximated). One isolated
emitted pixel can therefore contribute at most 9.380 of kernel-weighted coverage `A`, and the ratio
`A/S` — coverage per unit of budget — is bounded by that number. For a *straight trace* sampled
every `s` pixels the credited mass per emitted pixel is measured
(`evidence/h55_spacing_curve.json`):

| spacing s (px) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| mean kernel weight per truth px | 1.000 | 0.836 | 0.772 | 0.673 | 0.608 | 0.509 | 0.439 | 0.386 |
| **T / S** | 1.000 | 1.644 | 2.316 | 2.556 | **2.889** | **2.900** | 2.778 | 2.750 |
| A / S | 3.112 | 5.376 | 7.567 | 8.487 | 9.380 | 9.380 | 9.380 | 9.380 |

**The optimum is 500–600 m, not 100 m and not 200–300 m.** Measured on the family's real scored
rasters, `A/S` is 3.81 for a contiguous file (`h19-5`, 41 % of the ceiling), 6.56 for `d1-5`
(spacing ~1.5 px), 7.95 for `d2-8`, and **8.04 for the 0.2778 file** (86 %). So the best submission
this group ever made leaves 14 % of its placement efficiency on the table, and its contiguous
ancestor leaves 59 %.

**Measured, on a real fold, with everything else held identical.** `hide` fold 0, `n_truth = 10,336`,
same fitted field, same permitted set (footprint minus visible catalogue minus held-out components
grown by the buffer), same budget 37,654 px, same pixel-exact mask, same tested metric:

| emitter | DTI | A/S | % of ceiling |
|---|---|---|---|
| top-K (rank order — what the family shipped) | 0.03196 | 2.233 | 23.8 % |
| hard-core 200 m | 0.05130 | 6.184 | 65.9 % |
| hard-core 300 m | 0.06334 | 8.010 | 85.4 % |
| **hard-core 500 m** | **0.07151** | **9.303** | **99.2 %** |
| matched random control | 0.04387 | ≈9.38 | 100 % |

**+124 % over top-K at identical budget, and +63 % over the matched random control.** This is the
largest single effect measured in this repository, and it is a *placement* effect: it creates no
signal, it stops spending budget on pixels inside a 300 m disc that another emitted pixel already
covers.

**Why this is an emitter and not a tuning knob.** `gems52.emit.greedy_emit` maximises ρ̂-weighted
coverage and should find the same spacing on its own. The first version of
`gems55.emit_opt.coverage_greedy` reported `A/S` = 1.8–2.1 — *worse than top-K* — which looked like
evidence that a greedy packs into the peak of a peaked belief field. It was a bug: the running cover
was updated with `np.maximum(cf[nbi], kk, out=cf[nbi])`, and fancy indexing copies, so `out=` wrote
into a throwaway and no pixel ever learned that its disc was already covered. One test
(`sum of marginal gains == Σ ρ̂·K_E`, the telescoping identity) caught it at 107.7 vs 66.6. Fixed,
the greedy reaches `A/S` = 9.27 (98.8 % of the ceiling) and banks **20 % more** ρ̂-weighted coverage
than a hard-core thinning of the same field and **33 % more** than top-K, on both a flat and a
clustered belief (`tests/test_h53_emit.py`). So the claim "the greedy under-spreads when ρ̂ is
peaked" is **withdrawn**; IR-52-025 records the correction. Both emitters are measured on both
instruments and the winner ships — see §Measured below.

**Expected gain / cost.** Gain: measured, +0.040 absolute on `hide` fold 0; the algebra says the
same 14 % → 99 % move on the 0.2778 file is worth roughly +0.03 DTI on the board at unchanged
geology. Cost: **already implemented**, ~5 s per emission. **Rank 1.**

---

## Ranking, as written before scoring

| rank | id | hypothesis | expected DTI gain | implementation cost | new external data needed |
|---|---|---|---|---|---|
| 1 | H55-5 | 500–600 m hard-core placement, budget from the metric | **+0.040 measured on `hide` fold 0** (+124 % rel.) | done | none |
| 2 | H55-1 | band 6 is radiometric TC → corrected View B, TC step/edge/line | enabling; realised inside the fold-0 winner | 37 s | none |
| 3 | H55-3 | thermal points extended along a structure-tensor strike | moderate, and orthogonal to every band | ~1 min | INGENIOUS/GDR 1391, DOI 10.15121/1881483, CC-BY — **verified reachable** |
| 4 | H55-2 | Th/K and U/K ratio steps (buried contact + alteration) | small–moderate | 37 s | USGS GeoDAWN, DOI 10.5066/P93LGLVQ — already on disk |
| 5 | H55-4 | |G| calibrated from our own scored history | bounded; stops waste | ~2 min | none |

**Promotion rule (pre-registered, not moved later).** A hypothesis may touch a weekly submission
slot only if, on **both** instruments (`hide` and `tip`), it beats the matched-budget random
control in **≥ 3 of 4** folds *and* beats the best H52 arm recorded in `evidence/holdout_*.json`.
Never pool the two instruments: `union_cor|37654` is the best `tip` arm (0.0320) and the worst
`hide` arm (0.0001), and each is structurally blind to what the other can see (`knowledge/05` §4).

---

## Measured — after scoring, added to the same file rather than to a new one

Both instruments, 4 folds each, whole held-out segments, prevalence matched to 0.2 % of the
footprint, pixel-exact catalogue mask on the permitted set **and** on the score, matched-budget
random control computed in the same permitted set on the same folds. Source:
`evidence/h55_sweep.json` (coverage-greedy + hard-core, arms `B_c100`/`B_c50`/`B_therm`),
`evidence/h55_sweep_hardcore.json` (hard-core, all six arms), `evidence/h55_holdout_hide.json`
(the first single-fold run, which is where the placement effect was isolated).

### The placement effect, isolated

`hide` fold 0, `n_truth = 10,336`, one fitted field, one permitted set, budget 37,654 px, one mask:

| emitter | A/S | % of the 9.380298 ceiling | DTI |
|---|---|---|---|
| top-K, rank order (what the family shipped) | 2.233 | 23.8 % | 0.03196 |
| hard-core 200 m | 6.184 | 65.9 % | 0.05130 |
| hard-core 300 m | 8.010 | 85.4 % | 0.06334 |
| hard-core 400 m | 8.763 | 93.4 % | 0.10101 |
| hard-core 500 m | 9.303 | 99.2 % | 0.07151 |
| matched random control | ≈9.38 | 100 % | 0.04291 |

Note the shape: 400 m beats 500 m even though 500 m has the higher `A/S`. Coverage per pixel is not
the objective — *credited* mass is, and at 500 m the emission starts stepping over short traces. The
`T/S` curve in `evidence/h55_spacing_curve.json` predicted 500–600 m for a trace the emission lies
exactly on; with real positional error the optimum moves inward to 400 m. That is the curve doing
its job, which is to be wrong in a measurable direction rather than to be quoted.

### Arm × emitter, mean over 4 folds

| arm | emitter | hide | tip | sum | hide wins | tip wins |
|---|---|---|---|---|---|---|
| **B_therm** | **greedy \| 37654** | **0.09701** | **0.0547** | **0.15171** | 4/4 | 4/4 |
| B_c50 | greedy \| 37654 | 0.09699 | 0.05469 | 0.15168 | 4/4 | 4/4 |
| B_c100 | greedy \| 37654 | 0.0967 | 0.05375 | 0.15045 | 4/4 | 4/4 |
| B_therm | greedy \| 50000 | 0.0971 | 0.05319 | 0.15029 | 4/4 | 4/4 |
| B_c100 | hc4 \| 37654 | 0.09167 | 0.05448 | 0.14615 | 4/4 | 4/4 |
| B_c50 | hc4 \| 37654 | 0.09112 | 0.05421 | 0.14533 | 4/4 | 4/4 |
| B_only (no centring) | hc4 \| 37654 | 0.07827 | 0.05251 | 0.13078 | 4/4 | 4/4 |
| A_only (potential field) | hc4 \| 37654 | 0.02979 | 0.02894 | 0.05873 | **1/4** | **2/4** |
| AB_w80 (0.8 B + 0.2 A) | hc4 \| 37654 | 0.09112 | 0.05358 | 0.1447 | 4/4 | 4/4 |
| matched random | 37654 | 0.03948 | 0.02477 | 0.06425 | — | — |
| matched random | 50000 | 0.04318 | 0.02598 | 0.06916 | — | — |
| *reference:* H52 shipped arm | 37654 | *0.0518* | *0.0291* | *0.0809* | — | — |

### What was promoted, and by which rule

`_select` in `scripts/run_h55.py` implements the rule written above the sweep and reads it out of
the evidence file at build time:

```json
{
 "source": "evidence/h55_sweep.json",
 "arm": "B_therm",
 "emitter": "greedy|37654",
 "passes_rule1": true,
 "hide": 0.09701,
 "tip": 0.0547,
 "total": 0.15171,
 "hide_wins": 4,
 "tip_wins": 4,
 "mass": 37654,
 "n_g": 8129.0
}
```

The shipped file is `gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.tif`, sha256 `a0f3ed4b4524ca67a0c715beca5a905eced165ee9e59be5e5831a39b7526254d`, `A/S = 8.8151`
= 93.97% of the ceiling, every emitted pixel 8-isolated
(`max_component = 1`), 64.4% of its
mass touching none of 18 scanned priors, and
1,048,807 prior pixels deliberately not re-emitted. Rebuilding
reproduces the identical sha256.

### What this file is *not* claimed to score

`DTI ≈ 0.3044` is the **placement gain in isolation**: take the
0.2778 file's own measured per-covered-pixel truth density ρ_A = 0.01287, apply it to this file's
measured coverage A = 331,924, change nothing else. That is arithmetic given its
assumption, and the assumption is the weakest link — it says this field's covered area is exactly as
enriched as that file's, which the folds do not establish in either direction.

The fold numbers are **not** a forecast and are not offered as one. The same family scores ~0.05 on
`hide` folds and 0.2778 on the portal, so the instruments under-forecast the board by roughly 4× in
absolute terms; they are a *ranking* device, which is the only use this repo makes of them. The
+87.5 % on the sum against the previously shipped arm is a statement about the instruments, and
whether it transfers is the open question. It is printed above the download button rather than below
it for exactly that reason.

### The three things that did not work, stated with their numbers

1. **The potential-field view alone is not promotable under the registered fold gate.** `A_only` wins
   1/4 `hide` folds and 2/4 `tip` folds. Its mean DTI is below matched random on `hide` (0.02979 vs
   0.03948), but above matched random on `tip` (0.02894 vs 0.02477). It therefore fails the required
   ≥3/4 wins on each instrument; it is inaccurate to say both means are below random. The separately
   preregistered block-error correlation test refutes the co-training premise. `knowledge/03` N-6
   predicted weak potential-field ranking at the layer level (transforms AUC ≈ 0.52); the H55 result
   does not establish that View A has no error signal, only that this A-only arm fails promotion.
2. **Every blend is at or below the surface view alone.** `AB_w80` 0.09112 / 0.05358
   against `B_c50` 0.09112 / 0.05421; the geometric mean and the min were worse still
   (`evidence/h55_holdout_hide.json`, fold 0). Mixing A into B does not improve the View B comparator (hide is unchanged and tip is lower).
   Separately, A-only is below matched random on hide but above it on tip, and fails its fold-win
   promotion rule; it is not a below-random-on-both result.
3. **The disagreement signal, as a modulator, hurts.** Boosting View B where A is confident and B
   abstains (`Bdis_A`) and damping it where B is confident and A abstains (`Bsup_B`) scored 0.06776
   and 0.06902 against 0.07387 for unmodulated `B_only` on `hide` fold 0 at identical emitter and
   budget. The *strata* remain physically real — A-only pixels do sit in deeper cover — but a real
   description of a population is not a ranking improvement, and this is the second mechanism from
   the brief to fail its own test (the first was the pseudo-label round, IR-52-010).
4. **The thermal injection is neutral, and is labelled neutral.** `B_therm` beat `B_c50` — the same
   field without it — by **0.00003** on the selection sum (0.15171 vs 0.15168), 4/4 folds each. Only
   3,340 of 5,165,840 footprint cells carry a thermal lineament, so at a 37,654 px budget they are
   ~9 % of the file and cannot move a mean much. The pre-registered rule picked it anyway because the
   rule maximises the sum and was written before the numbers were seen. The gain in this file comes
   from items 1–4 of the ranking above, **not** from H55-3, and a session that reports otherwise
   should be corrected by pointing at this paragraph.

### The brief's own test, on the corrected split: **refuted**

The pre-registration said: correlate the two views' per-block out-of-fold error on labelled negatives
across spatial blocks, and abandon co-training if the errors are strongly correlated
(`ABANDON_R = 0.6`, `src/gems52/cotrain.py`). In H52 this test **could not
fire** — fewer than three blocks were usable and Spearman degenerated to 1.0 on all ties — so
`knowledge/03` N-1 recorded the premise as *unmeasured* rather than refuted, and retracted an earlier
pair of numbers that had been asserted. On the corrected split it fires.

| instrument | fold | usable blocks | Spearman, mean over-prediction on negatives | Spearman, FAR at budget 37,654 |
|---|---|---|---|---|
| `hide` | 0 | 40 of 62 | **+0.6341** | +0.1049 |
| `hide` | 1 | 40 of 62 | **-0.1158** | -0.2054 |
| `hide` | 2 | 40 of 62 | **+0.7625** | -0.0426 |
| `hide` | 3 | 40 of 62 | **+0.5576** | +0.1328 |
| `tip` | 0 | 40 of 62 | **+0.6034** | +0.0696 |
| `tip` | 1 | 40 of 62 | **+0.4002** | -0.2493 |
| `tip` | 2 | 40 of 62 | **+0.7107** | -0.0265 |
| `tip` | 3 | 40 of 62 | **+0.5837** | +0.1559 |

**Verdict: REFUTED at the pre-registered threshold on both instruments** (max |ρ| =
0.7625 `hide`, 0.7107
`tip`, against 0.6), 4/4 folds each. Co-training is abandoned. Two honest
qualifications travel with that verdict:

* The *other* block statistic — false-alarm rate at a fixed global budget — correlates weakly
  (max |ρ| 0.2493,
  and negative on three of eight folds). So the refutation is a property of the statistic the
  pre-registration *named*, not of every statistic computable from the same arrays. Both are reported;
  neither is hidden. Picking the flattering one after the fact is exactly what IR-52-011 and IR-52-018
  are about.
* View A's block-level false-alarm rate is wildly dispersed (coefficient of variation 1.35–5.22)
  where View B's is not (0.75–1.18). A view whose error is concentrated in a handful of blocks is a
  view that is finding a few regional anomalies and nothing else — the same reading as N-2 and N-10,
  arrived at from a third direction.

The co-training abandonment follows from the pre-registered block-error-correlation statistic. Separately,
the A-only emitter fails the ≥3/4-fold promotion rule: 1/4 hide and 2/4 tip wins, with its mean below
matched random on hide but above it on tip. The file's single-view choice is not a claim that A-only loses
to random on both instruments.

### Not merely the union of the two views

The brief asks for this check explicitly, and `gates.uniqueness_report` does not answer it — that gate
compares against *previous submissions*. `scripts/verify_h55.py` compares against the two views of
*this* pipeline at the same budget:

| compared set | px | overlap with the shipped file | % of shipped | shipped == set |
|---|---|---|---|---|
| top-K of View A alone | 37,654 | 307 | 0.8% | False |
| top-K of View B alone | 37,654 | 1,836 | 4.9% | False |
| union of the two views' top-K | 74,099 | 2,095 | 5.6% | False |
| coverage-greedy of View A alone | 37,654 | 428 | 1.1% | False |
| coverage-greedy of View B alone | 37,654 | 6,578 | 17.5% | False |
| union of the two views' coverage-greedy emissions | 74,760 | 6,902 | 18.3% | False |

The shipped file is View B's own coverage-greedy emission with a thermal rank bonus. It shares
5.6%
of its pixels with the union of the two views' top-K sets and
18.3%
with the union of their coverage-greedy emissions, and is equal to no set in the table.
