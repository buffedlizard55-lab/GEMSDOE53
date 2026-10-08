# H53-1 … H53-4 — four hypotheses this repo had not tried, ranked, with cost and verdict

Each one names the layers, the physical signature, why the catalogue can plausibly miss the structure,
how it differs from everything already implemented here (naming the file that implements the prior
arm, so a reader can check rather than trust), and its **measured** status on the spatially-blocked
instruments.  Ranking is by expected DTI gain over implementation cost; the ranking is stated before the
numbers and the numbers are then reported against it, including where it was wrong.

**Where the ranking was wrong.** H53-1 (rank 1) passed and ships. H53-4 (rank 2, monoclinal asymmetry) was
never implemented, so its rank-2 position is an *estimate and is labelled as one*: the ranking below is the
pre-registration, and only H53-1 has numbers attached. H53-2 and H53-3 remain unimplemented and are marked
as such rather than dressed with borrowed evidence.

Prior arms this must differ from, by name: `A_only`, `B_only`, `union`, `cotrain` and the corridor
composite, all in `scripts/validate_holdout.py` / `scripts/composite_split.py`, all of which are
*single-dataset or pooled magnitude rankings with no orientation and no null model*.

---

## H53-1 — Cross-dataset orientation coincidence, permutation-calibrated  *(rank 1: implemented)*

**Layers, five physics families, sixteen channels** (`src/gems52/dicoincidence.py::CHANNELS`):

| family | channels | source |
|---|---|---|
| magnetics | `tmi_hg` (band 3), `tc` (band 6), `rtp` (band 2), `tmi_vg` (band 9) | official cube |
| magnetics, depth-filtered | `TMI_up150` | external `geodawn_extensions_u8.tif` band 4 |
| gravity | `iso_grav_anom_hg` (18), `iso_grav_anom_vg` (11), `iso_grav_anom_slope` (5) | official cube |
| conductivity | `cond_surf` (17) | official cube |
| radiometric | `ThK`, `UK` (external band 1, 2), `K`, `Th`, `TC` (external `geodawn_rad_u8.tif` 1, 2, 4) | GeoDAWN |
| surface (View B) | `det_elev_slope` (19), `det_elev` (12) | official cube |

**Physical signature.** Not "there is a line here" but **"independent physics agree that this is a
line, at this place, with this strike"**.  Each channel's azimuth field (structure tensor,
`src/gems52/structure.py`) is reduced to one weighted axial azimuth per 1.6 km tile, and every
family-disjoint channel pair is tested against a null built by **rolling one azimuth field across the
tile grid** — a null that preserves each dataset's own fabric and destroys only the same-place pairing
(`src/gems52/dicoincidence.py::coincidence_test`).

**Why the catalogue can miss it.** The USGS/INGENIOUS product is a manual compilation; its failure
mode is inconsistency between interpreters, between quadrangles and between datasets.  A place where
four independent physics agree on a strike, and no trace is mapped, is exactly where such a
compilation has a hole.  The organiser confirms the class is in scope: *"'new fault' means 'any fault
pixel not already captured by USGS/INGENIOUS' and can include newly mapped geometry of an existing
fault system"* (chrisk-dd, Sep 23, https://community.drivendata.org/t/where-do-you-draw-the-line/11536 ).

**Difference from prior arms.** All prior arms rank *magnitude* — the strength of a scarp, a gradient
or a blended rank.  None has an orientation field, none has a calibrated null, and none can express
"these two datasets disagree, and that is the information".  The 2025 Stanford-workshop mapper this
family's notes cite (Hermant et al., linked by the organiser's About page) fires on roads, canals and
canyon rims precisely *because* it is single-dataset; requiring cross-family strike coincidence is the
direct answer to that documented failure mode.

**Cost.** 3 minutes cached (tiles + statistics), ~10 minutes full (node evidence).  Implementation
2 new modules, 4 new test files, all green.

**Verdict — passed, and this is the arm that ships.** On the two blocked instruments, at the incumbent's
budget and with the incumbent's emitter protocol, the coincidence-gated surface arm emitted under a minimum
separation scores **0.0387 tip / 0.0661 hide** fold-mean against 0.0357 / 0.0565 for the same field without
the gate, 0.0289 / 0.0445 for surface-only, and 0.0192 / 0.0369 for the same arm with its places rolled to a
different tile — with the previous best in this repo at that budget being 0.0320 / 0.0518. Fold support 3/4
and 4/4; comparator ordering identical on both instruments; `verdict.promoted = true` in
`evidence/h53_holdout.json`. Three parts of the hypothesis were wrong on the way and are recorded as wrong in
`knowledge/09` §3: the global significance gate did not discriminate, the per-tile z gate could not fire at
all, and the gate without the separation emitter lost to the ungated union.

---

## H53-2 — Strike **anomaly** relative to the regional fabric  *(rank 4: cheap, high variance)*

**Layers.** The same azimuth fields as H53-1 (nothing new to compute).

**Physical signature.** A lineament whose strike *deviates* by ≥ 40° from the locally dominant fabric.
The GeoDAWN region's dominant fabric is N–S (Basin and Range); the Walker Lane and the geothermal
fields along it are NW–SE to WNW transcurrent structures.  A cross-cutting lineament inside an N–S
fabric is the one geometry a fabric-following interpreter is most likely to skip.

**Why the catalogue can miss it.** Interpretation follows the dominant trend; the low-contrast
cross-cutting structure is the residual.  The competition's own About page cites the Stanza/Stanford
work that had to be *told* to look beyond the first-order trend.

**Difference from prior arms.** Nothing in this repo uses a fabric-relative angle.  The prior arms are
isotropic in strike (a scarp is a scarp at any azimuth).

**Cost.** ~30 minutes of analysis; no new data.

**Why rank 4.** It is a rare-class bet: a NW-trending fault is rarer than a N–S one in this footprint,
so even a perfect detector emits few pixels and the DTI gain is bounded by that pixel count.  Cheapest
to add *after* H53-1's fields exist, which is exactly why it is ranked by (gain / cost) rather than by
gain alone.

---

## H53-3 — Depth-filtered magnetic lineaments with the cover disagreement  *(rank 3: cheap, expected gain low)*

**Layers.** External `TMI_up150` (upward-continued 150 m magnetic field), official `depth_to_base_surf`
(band 15), `cond_surf` (band 17).

**Physical signature.** Upward continuation is a depth filter: sources shallower than ~150 m are
attenuated and deeper ones survive.  A linear gradient that exists in the continued field but has no
counterpart in the 1-px topography is a *buried* structure — the same reasoning as the H52-1 A-only
class, but with the shallow sources removed first instead of being averaged into the signal.

**Why the catalogue can miss it.** A geomorphic map cannot see it by construction.

**Difference from prior arms.** `depth_to_base_surf` was screened as an inverse feature
(`evidence/layer_screen.json`); the *continued* grid has never been used by any arm in this repo
(`grep -rn up150 src/` returns nothing before this session) and the external bundle's own README-style
band names are the only documentation of what it is.

**Cost.** ~20 minutes; no new data.

**Why rank 3.** This family's instruments have consistently found the magnetic-only arms weaker than
the surface arms (`A_only` below matched random on `hide`), so a magnetic-only detector inherits that
weakness even with the depth filter.

---

## H53-4 — Monoclinal asymmetry: two independent scarp products, one direction  *(rank 2: cheap, physically specific)*

**Layers.** External `lidar_scarp_features_u8.tif`: `step_max` (1 m LiDAR scarp step), `downface_max`,
`upface_max`, `ex_max`/`ex_mean`, plus the repo's own `B_scarp_p900` and `det_elev`.

**Physical signature.** A fault scarp is a **monoclinal** step: a steep free face on one side and a
long, gently sloping backslope on the other.  A road cut, canal levee or erosion line is *symmetric*
about its crest.  So the asymmetry ratio `downface_max / upface_max` (with a sign for *which* side
faces down) is a physical discriminator that is not a restatement of "there is a step here" — and it
must persist along-strike for ≥ 2 km in **two independent** scarp products (the 1 m LiDAR derivative
and the competition DEM derivative) to survive.

**Why the catalogue can miss it.** It targets the same class the brief's "B confident" arm targets,
but with a filter that removes the artefact class *by physics* rather than by down-weighting: the
measured artefact population in this footprint is dominated by symmetric features (roads, canals,
erosion lines), which is why the `B_only` arm's precision is limited.

**Difference from prior arms.** `B_scarp_fine`/`B_scarp_p300` use the repo's own two-sided step on the
DEM.  Nothing here has used the external 1 m LiDAR-derived products at all, and nothing uses
**asymmetry** — every prior surface arm is invariant to which side of the lineament is steeper.

**Cost.** ~40 minutes; no new data (the derived external raster is already hash-pinned in
`registry/data_manifest.json`).

**Why rank 2.** It is specific, cheap, and aims at the arm that actually wins on the instruments
(`B_only` is the only single-view arm that beats matched random on *both*), which is a better bet than
H53-2/H53-3 on expected gain even though its ceiling — like every surface arm — is set by how much
new truth lies on surfaces the catalogue already partly covers.

---

## If a candidate needed new external data: what and where

None of H53-1…H53-4 needs new data; all four use rasters already pinned in
`registry/data_manifest.json`.  For completeness, the two ideas that *would* need new data, with the
free official source and its obtainability checked this session:

| idea | source (free, official) | obtainable from this sandbox? | evidence |
|---|---|---|---|
| InSAR line-of-sight strain rate as an independent view | ARIA Sentinel-1 GUNW products, NASA/Caltech, https://aria.jpl.nasa.gov/ ; or COMET-LiCS, https://comet.nerc.ac.uk/COMET-LiCS-portal/ | **no** — TLS egress is blocked here (`curl` to sciencebase/OpenTopography/Overpass returns 000, measured) | `knowledge/06`, this session's connectivity probe |
| hydrologic spring alignment (H52-5) | USGS GDR/NREL spring records, https://gdr.openei.org/ | **no** from here; **yes** from the GitHub runner (the scheduled workflow fetched the live leaderboard successfully this session) | run 37541502292 succeeded; `data/external/gdr_*.csv` remain derived-not-authenticated |

So: any proposal that needs those sources is *viable through the workflow*, not from this box, and must
say so rather than quietly using an unverified copy.
