# GEMSDOE53 review and preregistered hypotheses

## Leakage diagnosis

Under Kaufman et al.'s learn–predict separation, a feature is inadmissible when its value at prediction time depends on information obtainable only after the target is known. “Distance to the existing-fault catalogue” fails this test when the competition target is defined relative to that catalogue: removing held segments from labels while computing distance from the full catalogue leaks held-target geometry. The repair is fold-local recomputation from visible segments only, with buffered whole-segment withholding. This audit applies to every catalogue-derived feature, not only distance. Each standalone feature also receives an AUC canary; AUC > 0.90 is quarantined pending proof.

Source: Kaufman, Rosset, Perlich & Stitelman, *Leakage in Data Mining* (KDD 2011), DOI 10.1145/2020408.2020496.

## Ranked candidates (before execution)

1. **RTP × conductivity cross-gradient** — bands 2 and 17; targets intersecting, nonparallel potential-field/conductivity boundaries. A concealed fault can juxtapose magnetization and fluid/alteration domains without appearing in the mapped catalogue. Unlike prior single-field log-edge and consensus work, this uses the vector cross-product of two gradients. Expected improvement: medium; cost: low.
2. **Multiscale elevation curvature** — band 12; combines absolute Laplacians at 200 and 500 m with slope. It targets persistent breaks in surface curvature rather than a catalogue halo. It differs from the repo's single-scale Hessian/scarp responses by requiring cross-scale persistence. Expected improvement: low–medium; cost: low.
3. **Total-count edge × curvature** — band 6; targets radiometric domain boundaries potentially produced by alteration or lithologic juxtaposition. It can identify unmapped contacts but is confounded by soil/moisture and lithology. It differs by multiplying first- and second-derivative evidence. Expected improvement: low; cost: low.
4. **InSAR line-of-sight velocity discontinuity × thermal anomaly** — Sentinel-1 plus Landsat/ECOSTRESS; targets active permeability boundaries. It requires new official external products and was not executed because they are absent from the cache and the sandbox cannot access their hosts. Expected improvement: uncertain; cost: high.

Named mimics are, respectively: lithologic contacts; roads/anthropogenic cuts; soil-moisture/lithology boundaries; and groundwater withdrawal/land subsidence.

## Result and irregularity

All 19 cached feature bands have exactly zero range. Consequently every candidate is tied, AUC is 0.500, and the identical holdout result is not scientific evidence. The generated raster is unique and format-valid but has a **negative** promotion verdict. Restore authentic competition features before rerunning. No competition slot was used.

The supplied 0.2778 is treated only as an organizer score reported by the user; no receipt is present here. Its causal mechanism cannot be identified from a public filename and score. Sparse placement aligned to DTI's 300 m kernel is a plausible explanation, not a verified causal claim.
