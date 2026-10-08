> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# 04 · Free, official external data — what is actually obtainable, and what each source buys us

Standing rule from the brief: new data must be (a) free, (b) official, (c) licence-permitted for use *and*
for sharing the derived submission with the sponsor, and (d) **confirmed obtainable**. This file records
exactly how far each candidate got through those four filters, because "I think this exists" is not a
finding.

## 0. The verification limits of this environment — read before trusting any row below

The analysis sandbox has no outbound network path at all: `curl https://www.drivendata.org/` dies with
`SSL_ERROR_SYSCALL`, and `urllib` reports the TLS connection being closed. The only thing that can reach
the public web from inside this session is the agent's own page-fetching tool. So:

* **"live, fetched this session"** in the table below means a request went out and bytes came back through
  that tool, at 2026-10-06 ~21:40 UTC, and the quoted numbers are in that response.
* Bulk rasters cannot be *downloaded* here even when they are freely downloadable everywhere else. For
  those, "confirmed obtainable" is necessarily a claim about the *service and its licence*, not about a
  file we hold. Every such row says so.
* The site's leaderboard feed is therefore refreshed by `.github/workflows/feed.yml` on a GitHub-hosted
  runner (real egress), with `scripts/refresh_feed.py` falling back to
  `registry/leaderboard_snapshot_2026-10-06.json` — never to an invented board.

## 1. What we already have, and the licence that governs it

The 19 competition-provided bands (verified inventory in `knowledge/01`, §bands) are licensed to
participants by the organiser for this competition, including the right to submit derived products. We
add no term of our own to that, and we do **not** re-publish the raw grids anywhere in this repo: `data/`
is git-ignored and `scripts/prepare_data.py` checks sha256 pins for the 23 files instead. Consequence for
the uniqueness rule the brief imposes: a submission is our *emission*, not their data, so sharing it with
the sponsor raises no third-party licence question.

## 2. Candidates, ranked by what they could change

### D-1 · USGS ComCat (ANSS) relocated seismicity — **live, fetched, usable today**

* Query used, verbatim:
  `https://earthquake.usgs.gov/fdsnws/event/1/count?format=text&starttime=1974-01-01&endtime=2026-10-01&minmagnitude=1.5&latitude=37.0&longitude=-90.5&maxradius=1.5`
  → **7,519 events** (returned as plain text, no authentication, no account).
* Licence: a USGS/DOE-funded federal data product; event catalogues are public domain, and the FDSN web
  service's terms place no restriction on redistribution of a derived, reduced table. Free to use with the
  sponsor. ✅
* Obtainability: JSON/CSV/text over HTTPS with a documented bounding-box and time-magnitude filter; a
  whole-catalogue pull for our footprint is a few thousand rows, i.e. a handful of HTTP requests, not a
  bulk raster. ✅ (obtainable in principle; **not** obtained in this session because of §0)
* What it buys: bands 10 and 16 of the provided data already carry "distance to earthquake" and "quake
  density", but from the grid the organiser shipped. ComCat gives **magnitude, depth, origin time and
  event-level location**, which is what a fault-length/throw proxy needs: `Σ 10^(0.9 M)` within a corridor
  is a moment-rate-like measure of how much slip a structure has taken recently, and a 3 km-relocated
  cluster with no mapped trace is the single strongest "there is a fault the catalogue missed" signal
  available for free. Expected lever: the far-field regime (hide instrument), where `B_only` is the only
  incumbent that beats random — a genuinely independent second ranking to blend with it.
* Cost: one script, ~30 s of compute, no GPU. It does **not** change round 1's emission tonight, which is
  why it is queued rather than built: the current composite selection is what must clear the holdout first.

### D-2 · Missouri DNR / MGS sinkhole inventory — **service and licence verified live**

* Item record fetched live from ArcGIS Online:
  `https://www.arcgis.com/sharing/rest/content/items/912f2e3eaa2b4c7d881424ee2fc98fb7?f=json`
  → `"title":"Sinkholes"`, `"access":"public"`, `"licenseInfo":"State of Missouri, Department of Natural
  Resources"`, `"spatialReference":"26915"`, `"url":"https://gis.dnr.mo.gov/host/rest/services/geology/sinkholes/MapServer"`,
  item modified 1713976616000 ms (2024-04-24). The Hub page states "known and probable sinkhole locations".
* Free ✅ (public, no token on the item); official ✅ (state survey). Obtainability: a REST MapServer that
  supports `query?...&returnCountOnly=true` and `f=geojson` — **we could not probe the endpoint itself from
  here** (the fetch proxy refused that request), so this row is metadata-verified, not download-verified.
* Licence caveat to resolve by hand before shipping anything derived from it: the item carries a state
  attribution string rather than a named open licence. State-survey GIS layers are routinely redistributable,
  but "routinely" is not a licence. Flag: check the DNR GIS terms of use page (link on the site) before
  including a derived raster in a submission; a *model input* does not have to be redistributed, which is
  the safe path — the emission is ours.
* Geology of it: the Ozark is karst. Sinkholes and sinkhole clusters are *near-surface fracture* evidence:
  water finds the joint and bedding-plane network, dissolves it, the cover drops. Under Pennsylvanian
  cover, where magnetics go quiet and our A-view goes blind, a line of aligned sinkholes is a mapped-on-the-ground
  expression of a buried structure. That is exactly the population the A-only stratum is describing
  statistically (96,586 px, median cover-depth rank 455/512). As a layer it should be tested as a *far-field*
  ranker, and as a *negative* filter it is interesting too: a "fault" that cuts no karst and no drainage is
  suspect.

### D-3 · Kansas Geological Survey, Ozark region type logs and stratigraphic units

* `https://www.kgs.ku.edu/PRS/Ozark/TYPE_LOG/Stratigraphic/index.html` — found by search this session, page
  lists the unit chart used for Kansas well tops in the Ozark region (Chester D/C zones, Maquoketa, Viola,
  Simpson, Platteville, St. Peter, Arbuckle: Eminence, Bonneterre, Lamotte, then Precambrian). Not fetched
  for content beyond the index page.
* Free ✅, official ✅ (state survey, University of Kansas). Its value is not the chart but the **well
  formation-tops** it keys to: a marker-bed depth surface built from public well records is an independent,
  point-supported estimate of *stratigraphic offset*. Two kilometres apart, if the Bonneterre Dolomite is at
  310 m and then at 380 m, something moved. That is the direct, falsifiable test of H52-1 (a range-front
  fault buried under cover) that no potential-field transform can give us, because the transform only says
  "the field changed".
* Obtainability: the KGS well and oil-gas databases are web-queryable and downloadable without an account;
  no licence prevents a derived depth-offset layer. **Bulk assembly is the cost here** (~1–2 days), so it
  belongs to round 2, not to tonight.

### D-4 · Public bedrock/Quaternary maps at 1:24k and 1:100k (USGS ScienceBase, state surveys)

Useful *only as a negative control*: if a proposed new trace runs straight through a mapped, field-checked
quadrangle that shows no fault, the burden of proof is on us. We did not obtain these; ScienceBase was not
probed from this session. Listed so the next run checks the licence line by line rather than assuming the
USGS "public domain" default applies to a cooperative state-survey product (it often does not).

### D-5 · Things we will not spend time on, with the reason

* 1 m LiDAR (3DEP / OpenTopography): public domain, but the fetch is tens of GB and dead here — see N-6.
* Radiometric grids — **corrected 22:35 UTC, we had this wrong.** The provided `training_features.tif` is
  19 float32 bands and contains **no** radiometric channel (verified with `rasterio`: count = 19; the
  inventory in `evidence/band_inventory.json` lists magnetic, gravity, geodetic strain, elevation,
  conductivity, depth-to-basement and seismicity only). But the brief's own clause is conditional — "plus
  *any* radiometric bands in `training_features.tif`" — and it resolves to none **in that file only**: the
  family's `data/external/` holds `geodawn_rad_u8.tif` (4 bands) and `geodawn_extensions_u8.tif` (4), i.e.
  USGS GeoDAWN radiometrics resampled to the competition grid, sha256-pinned in `registry/data_manifest.json`,
  plus `lidar_scarp_features_u8.tif` (12 bands). Those are **external, sibling-acquired, and unverified by
  us as to licence terms** — GeoDAWN is a USGS product (DOI 10.5066/P93LGLVQ) so public domain is likely, but
  the *rasters in this checkout* were produced by another session, so they fail our "confirmed obtainable by
  the route we state" test until someone re-derives them from the source. This repo's View B does not use
  them: a choice, not an oversight, and the cheapest measured follow-up for next round is exactly this —
  K/Th contrast separates clay-filled from carbonate-lined cover, which is a physical discriminator between
  a buried fault scarp and a road cut, and it belongs to the far-field ranking where `B_only` is currently
  unopposed.
* Commercial fault catalogues and proprietary well logs: fail the free test.
* QFaults / INGENIOUS / similar global fracture compilations: already tested — 1 and 0 pixels in the
  footprint. They are empty here, and they cannot be a prior for what is missing.

## 3. The two-line rule this file exists to enforce

Before any new external layer enters a submission: (1) name the licence *as read from the source*, not as
remembered; (2) show one live request that returned real bytes for the exact query the pipeline will use.
If either is missing, the layer may be built for offline study, but it may not decide an emission.
