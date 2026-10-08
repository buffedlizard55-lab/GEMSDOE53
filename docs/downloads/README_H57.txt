gems52-h57-union-novel-core25517px-arm14804px.tif
short link: h57-candidate.tif (byte-identical alias)
sha256 5fadcaefd64db0cb553bf16dfd0ec9b54005e3674ed4afb1052d5c8e1e215f78
bytes 157541

VERDICT: SUPPORTED BUT BELOW THE REGISTERED LIFT THRESHOLD

submission name: gems52-h57-two-view-union-arm-core25517px-arm14804px-5fadcaef-zeros
identifying note (181 chars): H57: exactly-accounted core of two scored priors plus 14.8k px of two-view co-training union mass, all outside the 200m ring and all outside prior support. Not a verified fault map.

- R4 format gate (single band, float32, EPSG:32611, 3730x3292, transform, all finite, [0,1], no nodata): True
- R5 decoded pattern differs from every accessible aligned prior: True
- R5 support novelty gate: True
- R6 artefact is not the union of the two named priors: True
- R3 nothing emitted inside the <= 200 m catalogue ring: True
- R2 block-buffered OOF independence measured and non-degenerate: True
- R7 one written geological reasoning per emitted arm pixel: True
- R1 mean lift >= +0.005 on BOTH instruments: False
- R1 >= 3/4 folds positive on BOTH instruments: True

- The structure of this artifact is verified end to end -- format, uniqueness, novelty, the ring, the set relations and the per-candidate geological reasoning all pass their registered gates, and the ranking field is the best of eight on the only holdout that can measure anything. R1's absolute +0.005 lift threshold is not met (best +0.0048). Upload is therefore a judgement call, not a gate pass: P(this file scores below the owner's own 0.2778) = 0.83 under the registered prior, and P(above 0.3195) = 0.36.
