# 09 · What H53-1 actually found

Everything below is a measurement made in this checkout, on the repo's two blocked instruments, with the
artefacts named next to every number. Where a result is negative it is written as the negative it is. The
artefacts: `evidence/h53_holdout.json` (all arms, all folds, both modes, plus the verdict),
`evidence/dicoincidence.json` (channels, pair tests, arm sizes), `evidence/submission_h53_audit.json`
(the written bytes and both gates). Code: `src/gems52/dicoincidence.py`, `src/gems52/structure.py`,
`src/gems52/azimuth.py`, `src/gems52/nodes.py`, driven by `scripts/h53_detect.py`,
`scripts/validate_h53.py`, `scripts/build_h53_submission.py`.

## 1. The headline number

At the incumbent's own budget (37,654 px), the same folds (`make_folds(seed=0, n_folds=4, buffer_px=4,
prevalence=0.002)`), the same `topk`-vs-separation emitter pairing, and the same metric code:

| arm (this session's naming) | tip fold-mean | hide fold-mean |
|---|---|---|
| **`B_corr` + minimum separation** | **0.0387** | **0.0661** |
| `union` + separation (no coincidence gate) | 0.0357 | 0.0565 |
| `B_only` + separation (surface only, no corroboration) | 0.0289 | 0.0445 |
| `B_corr` with its places rolled by a random tile offset | 0.0192 | 0.0369 |
| repo's previous best at this budget (`union_cor` tip / `B_only` hide) | 0.0320 | 0.0518 |

Fold support: `B_corr`+separation wins 3/4 folds on `tip` and 4/4 on `hide` against the ungated union, and
4/4 on both against surface-only and against the rolled control. The ordering of the four arms is *identical*
in `tip` and in `hide`, which is why the verdict in `evidence/h53_holdout.json` is `promoted: true` under a
rule that requires exactly that: strictly better fold-mean than every comparator on **both** instruments,
≥3/4 fold wins against the strongest comparator, and identical comparator ordering.

## 2. What the coincidence test is, precisely

Each of 16 channels — 5 physics families: magnetics (4 official bands + the external upward-continued
`TMI_up150`), gravity (3 official bands), conductivity (1), radiometric (external GeoDAWN K, Th, Th/K, U/K,
Th/K from `data/external/geodawn_rad_u8.tif` and `geodawn_extensions_u8.tif`), and surface (detrended
elevation, its slope) — is reduced to a structure-tensor azimuth field at 300 m scale, then to **one
weighted axial azimuth per 1.6 km tile** (234 × 206 tiles; ~20.5 k of 48,204 tiles carry a resolvable
azimuth for a given channel). All 100 family-disjoint channel pairs are tested against a null built by
rolling one azimuth field across the tile grid by a random offset, so each dataset's own fabric is preserved
and only the same-place pairing is destroyed. The gate a node must clear is
`agreement_percentile(cos2) ≥ 0.90` — the tile's agreement with its pair must be in that pair's own top
decile.

Top global coincidences by z (all of them positive, all cross-family, and two families of them): magnetics
vs radiometrics (mag_tc × rad_TC z = +37.2, × rad_K +14.7, × rad_Th +12.3) and magnetics vs the
upward-continued magnetic field (mag_hg × tmi_up150 z = +24.0, mag_rtp +24.0, mag_vg +16.7). 37 of the 100
pairs clear the Bonferroni z gate for *global* agreement — which is precisely why the global gate is not
used for the arms: it does not discriminate.

## 3. The three things that did not work

1. **Global significance as a node gate.** With 37/100 pairs significant globally (province-wide fabric),
   gating on it made 93 % of candidate nodes "corroborated" and 99.9 % "A-corr" — the arms stopped
   discriminating. The information is in the *relative* statement, not the absolute one.
2. **A per-tile z-score.** One tile contributes one scalar; the null s.d. across permutations is ≈ 0.3, so
   `|z| ≥ 3` requires cos2 ≈ 0.9 and fires on 0.0 % of tiles. Nothing was flagged, and nothing would ever
   have been. This is the exact failure mode of a gate that cannot fire — the same one `IR-52-018` records for
   the earlier independence test — and it is why the shipped gate is a rank, not a z.
3. **The gated arms before the separation emitter.** `B_corr` emitted by plain top-k scores 0.0286 / 0.0501
   against the ungated union's 0.0253 / 0.0413 — the gate alone is worth about +0.005 hide, and it is the
   gate *plus the spacing* that produces the +0.0096 hide margin over the union.

## 4. Why spacing is the third ingredient

The incumbent family's own files are a one-parameter ladder in spacing, not in content: 60,069 px at
2.24 px median spacing (0.2477), 44,090 px at 3.0 px (0.2600), 37,654 px at 3.0 px with every pixel isolated
(0.2778). Two pixels closer than the 300 m kernel cover the same truth pixel, so the second pays the
`0.2·(1−q)` false-positive tax for no new credit; pixels much further apart leave truth between them
half-covered. `src/gems52/nodes.py::spacing_select` is greedy top-`k` under a minimum separation with a
bucket grid, and this file is 37,654 isolated pixels with median spacing 3.0 px — the same geometry, filled
with ranked evidence rather than a lattice.

## 5. What this file claims and what it does not

It claims: on the two instruments this repo has, with the same folds and metric as every other arm, a
surface-lineament detector gated by independent-physics agreement at the same place and emitted under a
minimum separation beats everything measured before it here, and the mechanism's ordering is stable across
both instruments. It claims the geometry matches the metric's own demonstrated optimum.

It does **not** claim the hidden leaderboard will move by a particular amount: the instruments measure
against a *proxy* truth (the catalogue) while the real test set is expert-mapped new faults, and the whole
reasoning behind the 0.2778 file is that the real set rewards pixels that are *off* the catalogue. The
honest statement of the bet is in `knowledge/01` §5 and on `docs/validation.html`: a placement arm that wins
on the proxy and emits the metric-optimal geometry is the best available use of one weekly slot, not a
guarantee.

## 6. Two API lessons worth keeping

* `tile_index()` hands the nodes a **flat** tile id. A 2-D per-tile map indexed with it either raises or
  silently reads the wrong tile; both happened in this session. The maps are now reshaped at the point they
  are stored (`z_by_pair`, `pct_by_pair`).
* A per-tile statistic must say what its own null is. `coincidence_test` returns the summary, the z-map *and*
  the raw cosine map, because the raw map is what a distribution-free gate needs and the z-map is only
  useful as a diagnostic.
