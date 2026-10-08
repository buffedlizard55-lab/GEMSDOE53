> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# Hypotheses H52-1 … H52-5 — ranked, with the evidence that decided each one

Every hypothesis states the layers it uses, the physical signature it predicts, why that signature can
exist without being in the fault catalogue, how it differs from what this family has already tried,
and the measured (not projected) effect. Costs are wall-clock on this 2-core / 3 GB box.

Ranking is by **measured** effect on the appropriate blocked instrument, not by expected gain. Where a
hypothesis was refuted, it says so and keeps the number.

---

## H52-1 — Buried range-front translation: A confident, B withholds, cover deep

**Layers.** `A_grav_step`, `A_mag_step`, `A_strain_inv_reg`, `A_shear_rank` (the offset),
`A_depth_base_rank` (band 15, depth to basement = cover thickness), `B_scarp_p900`, `B_slope_rank`
(the contradiction).

**Physical signature.** A 100–300 m Bouguer or RTP-vertical-gradient linearity that continues for
≥ 500 m with **no** corresponding digital-elevation scarp, located where band 15 says the cover is
thick. A gravity step without a topographic step is a density contrast with no relief — which in a
extensional basin with basin-wide alluvium means the structure is *there and buried*, not absent.

**Why the catalogue cannot contain it.** The published fault map in this footprint is a
geomorphology/LiDAR-scarp product (staff discussion, thread 11527, where they were asked whether the
labels are LiDAR-scarp or geophysics-inferred — unanswered, so the claim is inference from the
competition's own framing). Where cover is thick enough to prevent scarp preservation, the mapping
method has no signal, so absence of a mapped fault there is *weak evidence of absence*.

**Difference from repo history.** GEMSDOE45 screened `depth_to_basement` as an inverse *feature*
(p@40k 0.0323) and GEMSDOE47 used `|grad2.5|_det_elev_slope` top-K. Nobody had used cover thickness as
a **gate on the disagreement class** — i.e. as the thing that converts "the views disagree" into
"and the disagreement is explained by burial".

**Measured.** In the 15 px off-trace corridor, mean cover-depth rank:
**A-only 455.0 vs concordant 251.2 vs B-only 296.7** (`evidence/strata_hide.json`). The mapped-fault
population sits in shallow cover (as it must, to have been mapped); the A-only candidate population
sits at 1.8× that depth, near the footprint background (499). Gravity step for A-only 6.06 vs
B-only 2.59 at comparable slope (7.93 vs 10.65): offset without relief, and its mirror image does not
occur. **H1 is supported as a description of the population.**

**But its yield as an emitter is small.** On hidden whole-segment folds, `A_only` mass scores **below**
uniform-random emission at the same budget (see `evidence/holdout_*.json`). Interpretation: A-only
pixels are the right *kind* of place, but the field view's ranking is too coarse (its useful precision
is 0.31 p@40k on-catalogue, and off-catalogue the base rate is 1.2 %). Cost: zero extra data, 20 min
compute. **Kept as corroboration and as a down-weighting input, not as the primary emitter.**

---

## H52-2 — Mapping truncation: rank the near-trace corridor instead of pruning it

**Layers.** `B_scarp_strike`, `A_mag_strike`, `A_grav_strike` (along-strike continuity of the same
gradient direction), plus distance-to-trace geometry — no new inputs.

**Physical signature.** A mapped trace ends. Its field offset and scarp azimuth continue past the end
for ≥ 1–3 px. Faults do not stop because a quadrangle boundary or a cover patch does.

**Why the catalogue cannot contain it.** Mapping is truncated by convention and by data extent as much
as by geology; and the organiser's own clarification is decisive here — new-fault truth *can* lie
within 300 m of a known trace, and those corrections are a stated goal of the competition
(thread 11516 post #4). The mask is **pixel-exact**, so everything 1–3 px off a trace is unmasked and
fully scorable.

**Difference from repo history.** This is the reverse of the inherited advice. GEMSDOE47 concluded
"prune the flank mass" (a blanket 2 px prune); that contradicts staff point #4, and it also throws
away the highest-precision mass available. Here the corridor is **ranked**, never deleted, and the
ranking is the strike-continuity evidence rather than raw proximity.

**Measured, and it is the largest single effect we found.** Restricting a field to the 6 px corridor
and re-ranking inside it lifts tip-instrument DTI from `union|37654 = 0.0240` to
`union_cor|37654 = 0.0320` (**+33 %** at identical budget, identical folds, identical masking) while
uniform-random emission on the same folds sits at 0.0253. Cost: zero. **This is the primary
emitter arm.**

**Instrument note, because it nearly produced the wrong conclusion.** A validation set built by
removing *whole catalogue components* cannot see this effect at all: measured on the real label file,
only **0.5 %** of a hidden component's pixels lie within 5 px of a still-visible trace (a trace's
neighbours belong to the same component). That instrument is structurally blind to near-trace mass and
would have refuted H52-2 for an arithmetic reason, not a geological one. The `tip` instrument — hold
out the along-strike ends of traces, leave the bodies visible, where **88.5 %** of held truth is within
5 px of a visible trace — is the one with the power to test it. Recorded in
`knowledge/05_instruments_and_what_each_can_see.md`.

---

## H52-3 — Seismogenic blind section: elevated micro-earthquake density with no scarp

**Layers.** `A_eqdens_rank`, `A_eqdist_negrank` (official bands 10 and 16: distance to earthquake,
earthquake density) intersected with the A-only stratum and with deep cover.

**Physical signature.** A linear or clustered micro-earthquake swarm along a trend with no surface
expression and a weak gravity response — a locked or creeping segment whose slip is not accumulating
as relief. In an actively extending basin, seismicity is the only dataset that samples the *currently*
active part of the section, including the parts that pre-date the map.

**Why the catalogue cannot contain it.** A geomorphic map is a map of *Quaternary surface expression*.
Blind segments are its documented failure mode, and the earthquake catalogue is the standard
independent evidence for them.

**Difference from repo history.** The seismicity bands were previously thrown into a single pooled
feature list, where their regional smoothness makes them a "is this near a swarm" predictor, which is
a location prior, not a fault detector. Here they are only ever consulted *inside* an already
field-confident, surface-abstaining class — as corroboration with a sign, not as a ranker.

**Measured.** Not yet separable on the folds (seismicity clusters at wavelengths ≫ 300 m, so it cannot
move a pixel-level ranking), and no fold DTI is claimed for it. Cost: zero. **Status: retained as a
tie-breaker inside the A-only corridor mass; explicitly not promoted.**

---

## H52-4 — Conductivity-defined fluid lineament in cover

**Layers.** `A_cond_rank` (band 17, EM conductivity at surface) against `A_depth_base_rank` and
`B_scarp_p900`.

**Physical signature.** A narrow, persistent conductivity contrast tracing a buried zone of
differential moisture — fault-rock damage zones and contrast in permeability across the plane express
as a linear moisture/groundwater boundary at the surface even with no relief.

**Why the catalogue cannot contain it.** The lineament is hydrologic, not morphologic; LiDAR-derived
mapping never sees it.

**Difference from repo history.** Conductivity was in the stack but never used as an independent
corroborator of the buried class; the family's magnetic/geodetic transforms at 300 m were refuted
(AUC ≈ 0.52) and this is a different physical agent at a different scale.

**Measured / expected.** 100 m conductivity resolves *soil moisture*, which follows drainage and
lithology as strongly as structure, so the prior for a spurious hit is high. We did not find a fold
signal for it. Cost: zero, but honest expected gain ≈ 0. **Not used as an emitter; documented so the
next session does not re-derive it.**

---

## H52-5 — External hydrologic evidence: spring-line density as a burial indicator

**Data.** USGS GDR spring occurrence (Wellspring/NSDI spring records) and GDR QFaults-v2 traces,
both free and public-domain, fetched through the public GDR API by a sibling session
(`data/external/gdr_*.csv`, 27,092 spring rows in footprint).

**Physical signature.** Springs preferentially line the base of range-front scarps *and* the toe of
buried scarps where a fault plane intercepts the water table — so a linear spring alignment in deep
cover, off the mapped trace, is positive evidence for a buried plane.

**Why the catalogue cannot contain it.** Springs are hydrologic evidence and the catalogue is
geomorphic; the alignment survives burial that destroys the scarp.

**Difference from repo history.** QFaults-v2 and INGENIOUS were already tried **as positive fault
priors** in this family and yielded ~0 off-catalogue hits (dead end, `knowledge/03`). Springs were
never tried, and they are a different claim: not "this line is a fault" but "this *unmapped* location
has the hydrologic consequence of a fault".

**Status, and the reason it is not in the shipped file.** The CSVs on disk are **derived, not
organiser-authenticated**: the GDR host is unreachable from this sandbox, so the fetch could not be
re-verified this session and the row counts cannot be tied back to an official download receipt. Per
the standing instruction (external data must be *confirmed obtainable*, licence permitting sharing with
the sponsor), an unverifiable file is not allowed to move mass. **Blocked pending a re-fetch with a
hash and a licence note; flagged on the site's irregularities page.** Cost if unblocked: ~30 min +
20 min compute.

---

## Ranking actually used

| rank | hypothesis | measured on validated folds | verdict |
|---|---|---|---|
| 1 | H52-2 corridor ranking | +33 % DTI at equal budget, 4/4 folds improve | **shipped** |
| 2 | H52-1 buried A-only class | population is real (cover 1.8×, gravity step 2.3×) but its ranking loses to random | corroboration + down-weighting only |
| 3 | H52-3 seismicity corroboration | no separable fold effect | tie-breaker only |
| 4 | H52-5 spring lines | not measurable with verified data | blocked on provenance |
| 5 | H52-4 conductivity lineament | no separable fold effect, high false-positive prior | not used |

The meta-finding, stated once and applied to every decision below: **the mechanism the brief named
(co-training via pseudo-labels) was refuted by its own gate, while the geology it pointed at
(disagreement = burial) survived.** The submitted field therefore keeps the strata and drops the
pseudo-label round, and the weights that combine the views were re-derived from the folds instead of
declared — see `knowledge/03_negative_results_and_what_they_killed.md`.
