# Hypotheses H54-1 … H54-5 — ranked by what was measured, not by what was hoped

The brief asks for 3–5 candidate geological hypotheses not yet tried, each naming its layers, its
physical signature, why it should catch a fault missing from the USGS/INGENIOUS catalogue, how it
differs from anything already in this repo, and its expected DTI gain against its implementation
cost. It also asks that they be ranked, and that the top one be validated on a spatially-blocked
holdout **before** a weekly submission slot is spent.

Two things changed the shape of that request, and they are measured in `knowledge/10`:

1. **The holdout this repo validates on does not predict the organiser's score.** Spearman
   ρ(reported, simulated) = −0.1045, p = 0.734, n = 13; the champion file ranks *last* of 13 on the
   instrument (lift 0.09× random) and *first* on the board. So "validate the top one on the
   spatially-blocked holdout" cannot be honoured as written — the instrument is broken, not the
   hypothesis. What replaces it is stated per hypothesis below.
2. **The published scores of this group's own files are a far better instrument than any simulator**,
   because five of those files stand in exact set relations. That yields `|G|` = 14,088.7 px, an
   exactly-zero-credit 200 m ring around the mapped catalogue, and an exact interval on the credit
   carried by the double-corroborated atom `A & C`.

Ranking below is by **measured** effect on the instrument that exists. Where a hypothesis was
refuted it says so and keeps the number.

---

## H54-1 · Revealed-preference budget reduction: emit the double-corroborated tier only — **RANK 1, adopted**

**Layers.** None. It uses no geophysical layer at all — only the restored bytes of five scored
submissions and their published scores.

**Physical signature.** Not a physical one, and that is the point. Two independent thinnings of the
same field (`d2-8` at 44,090 px and `d1-5` at 60,069 px) agree on 25,517 pixels. Agreement between
two samplings of one ranked field is a rank statement: those pixels sat higher in the field than the
ones either sampling dropped.

**Why it should catch what the catalogue misses.** It does not claim to. It claims something cheaper
and better-supported: that the mass this group already emits is *over-budget*, and that the metric
says so in closed form. `DTI = T/(0.2 S + 0.8|G|)` is maximised at `S* = 4b|G|/(1−b)` for a
precision-recall curve `T = a S^b`; the family's own curve gives `b = 0.2284`, so `S*` = 16,678 px
against the 37,654 px actually emitted. The atom algebra reaches the same place from the other
direction: `DTI(A & C alone)` = **0.2546 – 0.3190**, central **0.3139**, with the interval following
only from `t ≥ 0`.

**Difference from repo history.** GEMSDOE17/18 concluded that *more* mass helps and GEMSDOE23 found
the optimum by hill-climbing a threshold on one field. Nobody noticed that two of the group's own
files are nested inside a third, or that the nesting converts published scores into an exact linear
system. `knowledge/01` §4 reasons about the credit bar per pixel; this reasons about the credit of a
*set difference*.

**Measured.** Containment verified on the bytes: `A\B` = `A\E` = `B\E` = `C\E` = 0 px; the six atoms
sum to `|E|` = 121,131 exactly. The cross-check model `T = 471.6 S^0.2284` predicts eight published
scores to within 4 %, five within 1.5 %, including a file from a different family
(`anderson-geothermal-pinn-38854`, predicted 0.2767 against reported 0.2750). **Cost: zero data, ~2 s
of compute.**

**Limit, stated.** Adopting it as the *whole* submission would re-emit 25,517 pixels that two prior
submissions already contain, which the brief's uniqueness rule forbids. It is therefore adopted as
the **retained core** of a majority-novel artefact, sized by `revealed.budget_rule` (see H54-2).

---

## H54-2 · Along-strike continuation of credited structure — **RANK 2, adopted as the novel half**

**Layers.** The recovered local strike of the credited dot cloud (structure tensor of its smoothed
density, σ = 3 px), plus `depth_to_base_surf` (band 15), `iso_grav_anom` (13) and `rtp` (2) gradients
for the ranking, and the two view models of H54-3.

**Physical signature.** `TPw = Σ_g max_x p(x) k(d(x,g))` credits each truth pixel **once, at its best
covering weight**. A dot 250 m from a trace earns that truth pixel 0.167; a dot on the trace earns up
to 3.0 truth-pixel-credits, because ∫(1 − |u|/3)du over the covered ribbon is 3. So the cheapest
score in this metric is not new structure — it is mass placed *along* structure already known to be
credited. Faults in this footprint are straight over kilometres, so a 100–400 m step along a
recovered strike stays on the structure while covering truth pixels the original dot's kernel cannot
reach. Across-strike steps are the opposite: they re-cover the same truth pixels (δ ≈ 0) and pay the
full false-positive tax.

**Why the catalogue cannot contain it.** The credited structure is by construction ≥ 200 m from any
mapped trace (H54-1's exactly-dead ring). Its continuation is further still.

**Difference from repo history.** GEMSDOE45's "tip" arm ranked the corridor *around the mapped
catalogue*; this ranks the corridor around the **credited emissions**, which is a different and
much smaller set, and it walks a *recovered strike* rather than dilating. Nothing in the repo
recovers an orientation field from its own prior emissions.

**Measured.** The credited cloud is anisotropic: mean coherence **0.4197** against **0.2676** for a
matched uniform-random cloud at the same smoothing (1.57×), and at σ = 6 px the fraction of dots above
coherence 0.8 is **16.8 %** against **2.2 %** (7.6×). The two independent thinnings agree on the
recovered orientation histogram to cosine **0.9952**; the random control is flat. The dominant
recovered strike is **100–110° in array convention** (+x east, +y south) = azimuth ≈ **010–020°**,
i.e. NNE–SSW — the Basin-and-Range normal-fault strike of a footprint spanning 37.3–40.7 N,
116.2–120.0 W. A detector that recovered the wrong fabric would be fitting noise; this one recovers
the right one. **Cost: zero data, ~40 s.**

**Limit, stated.** Recovering the fabric is not the same as recovering the trace to within 100 m. The
credit density of this component is the `ρ_novel` of `revealed.budget_rule` and it is a *prior*
(U[0.03, 0.14]), not a measurement — see `knowledge/10` §6 for the screens that say no feature I can
compute re-ranks inside the champion file.

---

## H54-3 · Two-view co-training on a revealed-preference label — **RANK 3, adopted as the ranker and as the artifact-suppression rule**

**Layers.** View A (potential field / subsurface): bands 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15,
16, 17, 18 with horizontal gradients, Laplacians, 5×5 ranges and structure-tensor coherence on the
five most physical of them — 49 features. View B (surface): bands 12, 19 with the same four operators,
all **12 LiDAR scarp bands**, all 4 radiometric bands and all 4 ratio bands, plus the up/down-face
asymmetry of H54-5 — 32 features.

**Physical signature.** A fault buried under basin fill shows in the potential field and not in the
surface; a road, a canal levee, a quarry face or an erosion line shows in the surface and not in the
potential field. The disagreement is the signal, exactly as the brief specifies, and the two
directions of disagreement mean opposite things.

**Why the catalogue cannot contain it.** The mapped catalogue in this footprint is a geomorphic scarp
product (inference, recorded in `knowledge/02` H52-1 — the staff were asked and did not answer,
thread 11527). Where cover prevents scarp preservation the mapping method has no signal, so absence
from it is weak evidence of absence.

**Difference from repo history.** `knowledge/03` N-1 refuted co-training **pseudo-labels as a label
source** (0.0084 tip / 0.0078 hide against random 0.0253 / 0.0396) and that verdict is accepted here,
not re-litigated. What is new is the **label**: not a pseudo-label but the revealed-preference tier
`A & C`, whose credit density the organiser's own scores bound below at 16.3 % against 2.8 % for
uniform random. Using prior submissions as a label is the "learning and education" use the brief
permits; the artefact emitted is not those pixels. The independence test is also reported at pixel
level as well as block level, because N-1 records that block-level variance was degenerate and the
abandonment test therefore could not fire.

**Measured, and one part of it is a negative result.** Out-of-fold AUC over 4×4 spatial blocks,
label = credited-core membership: **View A 0.7126** (block mean over the 11 blocks with n ≥ 500:
0.7004), **View B 0.9277** (block mean 0.9183), blend 0.9139. Independence: pixel Pearson
**r = 0.2744**, block mean **r = 0.2784**, block variance 0.00267 (not degenerate) — below the
pre-registered 0.60 abandonment threshold, so the arm proceeds. **But the brief's own single-view
baseline says co-training does not win: View B alone (0.9183) beats the blend (0.9139).** That is
reported rather than buried.

**The caveat that matters more than the AUC.** `knowledge/10` §6 measures that *habitat is not
credit*: the credited tier `P1` and the tier `P5` carrying 4–10× less credit have nearly the same
habitat AUCs against random (0.666 / 0.680 for `ddetelev_range5`). So a 0.93 AUC on this label means
"View B can find where this family emitted", **not** "View B can find which emissions were right".
This is precisely why `ρ_novel` enters the budget rule as a prior. **Cost: zero data, ~4 min.**

---

## H54-4 · Radiometric depletion and alteration ratios as an independent vote — **RANK 4, partly adopted (inside View B), main claim refuted as a standalone**

**Layers.** `geodawn_rad_u8.tif` K, Th, U, TC and `geodawn_extensions_u8.tif` Th/K, U/K, U/Th —
8 external bands that no GEMSDOE round in this repo's history used, plus band 6 `tc`.

**Physical signature.** Hydrothermal fluid moving up a fault alters the rock it passes: potassic
alteration raises K, argillic alteration destroys K-feldspar and raises U/Th, silicification drops
total count. The *ratio* is the diagnostic, not the magnitude, because magnitude is dominated by
lithology and by whether the pixel is bare rock or alluvium.

**Why the catalogue cannot contain it.** An alteration halo survives burial; a scarp does not. A
fault whose only surface expression is a 5 km-wide K-depletion anomaly is invisible to any
geomorphic mapping product and is exactly the population a geothermal prize wants found.

**Difference from repo history.** The repo used radiometric *magnitudes* through band 6 and never
used the external ratio raster at all (`data/external/geodawn_extensions_u8.tif` is restored and
hash-pinned but appears in no prior pipeline).

**Measured, and it is mostly a refutation.** Blocked AUC against the credited tier:
`rad_K` **0.3612**, `rad_TC` **0.3787**, `rad_Th` **0.4171**, `rad_U` **0.4279** — all strongly
*below* 0.5, i.e. the credited dots sit on radiometrically **depleted** ground, uniformly, with no
ratio structure: `ext_ThK` 0.5182, `ext_UK` 0.4739, `ext_UTh` 0.4675, all within 0.05 of chance.
Depletion in all three channels together is **bare rock and thin soil**, a lithologic and geomorphic
artifact of the same high-relief habitat that `ddetelev_range5` already captures at AUC 0.6664 — not
an alteration signature, which would move the *ratios* and leave the total count alone. **The
alteration-halo claim is refuted on this footprint; the depletion is real but is not what the
hypothesis said it was.** Kept as View B features, dropped as a standalone emitter. **Cost: zero.**

---

## H54-5 · Scarp up/down-face asymmetry as the surface-artifact discriminator — **RANK 5, adopted only as the suppression term**

**Layers.** `lidar_scarp_features_u8.tif` bands 6 `downface_max`, 7 `upface_max`, 8 `cross_max`,
3 `step_max`, combined as `(up − down)/(up + down)` and that ratio times `step_max`.

**Physical signature.** A normal-fault scarp in this footprint has a systematic asymmetry: a steep
down-facing side on the basin side and a gentler up-facing side on the range side, and the asymmetry
flips sign with dip direction. A road cut, a canal levee, a quarry face or an erosion line has no
consistent sign relative to a regional strike — it follows contours or follows a survey line. So the
*sign of the asymmetry relative to the recovered strike* separates real scarps from the artifacts the
brief asks to suppress.

**Why it matters here.** The brief's B-confident/A-abstains class is defined as suspect. Without a
discriminator, "suspect" is just a low View A score, and suppressing it is arbitrary.

**Difference from repo history.** Every prior round used scarp *magnitudes* (`B_scarp_p900`,
`B_scarp_strike`). Nobody formed the asymmetry ratio, and nobody compared its sign to an orientation
recovered from a different dataset.

**Measured, and it is weaker than hoped.** Against the credited tier the raw scarp bands are the
strongest single features in the whole screen — `sc_upface` **0.6522**, `sc_lappos` 0.6396,
`sc_downface` 0.6361, `sc_lapneg` 0.6326, `sc_ex_max` 0.6297, `sc_cross` 0.6296, `sc_step_max`
0.6216 — but the *asymmetry* adds nothing they do not already carry, and `sc_coh100` is 0.4895, i.e.
chance. The scarp response is high on the credited dots because they are on steep bedrock ground, the
same habitat as H54-4's depletion. Adopted only as the `B_only` suppression term in the ranking
(−0.35 on the B-minus-A disagreement plus −0.25 on the whole `B_only` stratum), not as a detector.
**Cost: zero.**

---

## Not tried, and what it would take

* **USGS ComCat event-level seismicity** (`knowledge/04` D-1: service and licence verified live,
  7,519 events for a comparable query, no authentication). Would give magnitude, depth and origin
  time, hence a moment-rate-like `Σ 10^(0.9 M)` along a corridor — a genuinely independent vote that
  the provided bands 10 and 16 do not carry, because they are already-smoothed distance and density
  fields. **Blocked here: `earthquake.usgs.gov` is unreachable from this sandbox** (only `pypi.org`
  and `api.github.com` respond; `raw.githubusercontent.com` and `drivendata.org` both die at HTTP
  000). Obtainable on any machine with real egress.
* **QFaults trace geometry.** `data/external/gdr_qfaults_traces.csv` holds 1,126 traces with
  `slip_rate`, `recency`, `slip_sense`, `map_scale` and 18,182 km of length, but **centroids only** —
  there is no polyline in the file, so a trace cannot be rasterised from it. 376 centroids fall in
  the footprint, 77 of them on the mapped catalogue, mean distance to it 595 m: the layer is largely
  independent of the labels, which is what makes it worth having. Needs the GDR's WFS/GeoJSON
  endpoint, unreachable from here.
* **A within-champion re-ranking.** `knowledge/10` §6 is a screen of 171 features that says it cannot
  be done from the provided grids. If the family still holds the `h19-5` *field* (not just its
  thresholded emission), the top 16,678 px of it is worth ≈0.2975 by the same algebra, and that is
  the single highest-value artefact this group could produce next.

## Ranking summary

| rank | hypothesis | expected DTI | cost | status |
| --- | --- | --- | --- | --- |
| 1 | H54-1 revealed-preference budget reduction | 0.2546 – 0.3190 (exact interval, central 0.3139) | 0 data, 2 s | adopted as the retained core |
| 2 | H54-2 along-strike continuation | ρ_novel prior U[0.03, 0.14] → P(win) 0.82 at 25,000 px | 0 data, 40 s | adopted as the novel half |
| 3 | H54-3 two-view co-training on the revealed label | ranks the novel half; blend 0.9139 vs View B alone 0.9183 | 0 data, 4 min | adopted as ranker + suppression |
| 4 | H54-4 radiometric alteration ratios | — | 0 | **refuted as standalone** (depletion is lithologic); kept as View B features |
| 5 | H54-5 scarp up/down-face asymmetry | — | 0 | adopted only as the `B_only` suppression term |
