# Hypotheses — new candidates, 2026-10-09 (session H8)

Ranked by expected DTI improvement divided by implementation cost. **Nothing here is a score.**
Every holdout number is HOLDOUT-DTI (proxy) and comes from `evidence/`. These are the hypotheses
**not tried before in this repository** (H1, M1, H2-ridge, H3, H4, H5, H7 are the earlier list in
`docs/research/hypotheses.md`). Prior art in the *registry* (other GEMSDOE sites) is named so each
hypothesis states how it differs — the parallel-run protocol forbids drifting into another lane.

| Rank | ID | Hypothesis (one line) | Layers / signature | Expected gain | Cost | Status |
|---|---|---|---|---|---|---|
| 1 | **H8** | Hidden faults continue beyond mapped segment tips and inside relay/step-over zones between overlapping segments; emit metric-spaced dots in those corridors with magnetic-lineament concordance, pruned >2 px off the catalogue | `labels.tif` skeleton (tip extrapolation, relay geometry) + band 2 (RTP) Hessian/NMS ridges; curvature/extrapolation transform of the catalogue itself | high (directly targets where unmapped segments sit) | low (rules only, no new data) | **tested this session** (X4 canary clean; X5 holdout) |
| 2 | **H11** | Geothermal-vent point process: shallow temperature anomalies, hot springs and travertine mark present-day permeable fault zones — vents are direct observations of the *hidden* structure | External: INGENIOUS 2 m temperature probes, `paleo_geothermal_regional` deposits, wells/springs GDB (pinned GitHub mirror `jklinck/geothermal_research@56d78de7`); KDE/point-density transform | high (off-catalogue evidence; independent of the fault catalogue) | medium (georeference 3 point layers; licence check IR-53-44) | not tested (budget) |
| 3 | **H12** | Concealed basin-bounding faults appear as edges of the depth-to-basinement and conductivity surfaces under cover where no faults are mapped | Bands 15 (depth to basement), 17 (conductivity surface); Sobel/structure-tensor edge + lineament transform | moderate–high in covered valleys (the catalogue is weakest there) | low (label-free bands already on the grid) | not tested (budget) |
| 4 | **H10** | Hydrothermal alteration halo concordance: radiometric K/Th anomalies co-located with magnetic lows/edges mark altered, demagnetised fault cores | External GeoDAWN radiometrics (K, eTh, eU, Th/K) + band 2; edge detection + co-location | moderate | medium (fetch native grids from the template bridge; registry prior art GEMSDOE46 r11f/r12 must be distinguished) | not tested (budget) |
| 5 | **H7** | Regional trend prior: new faults run sub-parallel to the dominant visible strike (Walker Lane / Basin & Range expectation) | `labels.tif` orientation histogram; orientation-matched weighting | small–moderate | very low | not tested (budget) |

## H8 — tip/relay continuation corridors (this session's lane)

- **Layers:** `labels.tif` (8-connected segments, 60,988 px) and band 2 (reduced-to-pole magnetics).
- **Physical signature:** displacement-controlled fault growth. The mapped trace ends where
  displacement dies (tip), not where the structure ends; interacting segments link through relay
  ramps / step-overs whose damage zones localize both seismic gaps and geothermal permeability
  (Faulds & Hinz, Great Basin play-fairway literature; see `registry/sources.json` S46-S33).
- **Why it catches faults MISSING from the catalogue:** a continuation is by construction off the
  mapped trace; a relay corridor sits between mapped segments where mapping gaps are. Nothing in the
  feature equals a catalogue label (X4 separability max 0.79 vs the 0.90 gate; the leaky
  full-catalogue distance positive control measures exactly 1.000).
- **How it differs from the repo and the registry:** the repo had no tip/relay geometry; the registry
  has GEMSDOE33's `h33d-analog-tip-stepover-r30` (analog-based, r=30) and GEMSDOE32's model-emission
  thinning (d2.8). H8 is rule-based catalogue geometry + magnetic concordance at 2.8 px packing with
  a >2 px catalogue prune; the uniqueness gate measures the actual drift against every registry file.
- **Mimicking process (run card):** mafic dyke swarms and buried lithologic contacts produce magnetic
  lineaments without Quaternary faulting; alluvial-fan berm edges mimic scarps.

## H11 — geothermal-vent point process (first item for the next session)

- **Layers (external, pinned mirror `jklinck/geothermal_research@56d78de7`, S26):**
  `2m_temperature_probe_INGENIOUS_regional_data` (T2m/T1m/T15m probes), `paleo_geothermal_regional`
  (travertine/silica deposits), `wellspringdata.gdb` (wells and springs).
- **Physical signature:** active hydrothermal upflow requires permeable fault zones; shallow
  temperature anomalies and travertine mounds are surface expressions of the *flow path*, i.e. of the
  fault even where no scarp is mapped. Paleo-deposits record past discharge on now-inactive strands.
- **Off-catalogue rationale:** a vent is a measurement, not a trace digitized from the same maps that
  built the labels. A vent on an unmapped structure is direct evidence for that structure.
- **Difference from everything in the repo:** none of these layers is in the 19-band stack; the repo's
  arms never used a point-process layer.
- **Cost / risk:** georeference NAD83 UTM 11N points to the 100 m grid (~1 m datum shift, negligible);
  licence check (IR-53-44) before use; the sandbox can reach GitHub but not GDR directly.

## H12 — concealed basin-edge lineaments

- **Layers:** band 15 (depth to basement surface), band 17 (conductivity surface), with band 12
  (detrended elevation slope) as a secondary.
- **Signature:** sedimentary thickness and conductivity step across concealed normal faults; a
  structure-tensor edge on the basement surface under cover marks the fault where the catalogue is
  empty by definition (covered basin floors).
- **Off-catalogue rationale:** USGS/INGENIOUS mapping terminates at the range front; basin-floor
  faults are mapped from geophysics only.
- **Difference:** the stack's gradient bands were used raw as ML features; no edge/lineament
  extraction on the basement/conductivity surfaces exists in the repo.

## H10 — alteration-halo concordance (distinguish from GEMSDOE46)

- **Layers:** GeoDAWN radiometrics from the template bridge + band 2.
- **Signature:** hydrothermal clay (K enrichment, Th depletion) halo around a demagnetised core along
  a magnetic edge — the classic concealed-geothermal-fault signature.
- **Difference from the registry:** GEMSDOE46 `r11f-scarp-radiometric-fusion` (0.1589,
  user-reported) fuses scarps with radiometrics; H10 targets the *halo concordance* (co-location of
  K/Th anomaly and magnetic edge) with no scarp layer, and would be uniqueness-gated against r11f/r12.

## H7 — regional trend prior (cheap filler)

Orientation histogram of visible segments; weight candidates by alignment with the dominant strike.
Catalogue-derived but not proximity-derived (no self-label channel). Small expected gain.

## Rejected / blocked (unchanged)

- H3 fault-parallel strain: blocked, public strain data are scalars only (IR-53-40).
- H4 USGS Quaternary faults as extra labels: rejected, they are the catalogue's own source (S1).
