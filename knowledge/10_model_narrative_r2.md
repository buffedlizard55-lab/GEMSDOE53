# R2 model / AI-use narrative — research, not a prize submission certification

## Target, evidence and result

Predict faults on the provided GeoDAWN-aligned raster. The output is a model proposal map, **not confirmed faults, vents, geothermal fluid paths or commercially viable reservoirs**. Registered structural contrast mean local catalogue-holdout DTI 0.193167 versus surface-only 0.194671, −0.001504, 2/4 positive folds: promotion FAIL. No organizer score or actual upload/acceptance exists. No weekly slot was used.

## Data and algorithm

Only core competition feature raster, known-fault label raster and sample geometry/footprint. Restored from owner mirrors with SHA-pinned receipts; organizer authentication of those bytes remains unverified. No new external derivatives, geothermal well/spring labels, previous submission values or prior masks in model fitting/features/placement. Prior TIFFs are read **only after inference for learning/audit comparisons**.

57 label-free raw/physical features, Gaussian 1/3/8 px normalized-convolution transforms, signed gravity–cover normals and persistence, surface curvature/residuals, conservative 36 px support erosion. CPU histogram gradient boosting, 120 rounds, 15 leaves, min leaf 80, LR .08, L2=2, fixed seed, balanced training weights, no early stopping. Model probabilities are not field-calibrated fault posteriors. Actual incremental triangular max-cover lazy greedy under the registered 37,654-pixel budget; this is a restricted-pool coverage surrogate, not expected DTI/global optimum.

Four component-preserving quadrant hide-and-recover folds and 80 px train buffer. Negatives are catalogue-zero proxies outside the 300 m positive collar, not proven geological absence. A/B OOF proxy errors measured on actual finite held-out negative predictions. Low correlation permitted a separate single-round buffered whole-component co-training trial; its negligible B gain/A loss did not promote it and pseudo-labels are not in this primary file. Every emitted A-only pixel has a conditional reasoning/alternatives CSV row; heuristic signature thresholds are not a validated geological classifier.

## Output and limitations

One float32 data band on the pinned sample's shape/CRS/affine grid. Binary finite [0,1] raw cells, zero outside supported inference footprint and on known catalogue pixels, internal validity mask matches the sample footprint. No negative nodata sentinel or .msk sidecar. Public format permits NaN outside the footprint; all-finite raw values are a precaution for the reported range error, not proof of undocumented portal behavior. All output bytes are re-opened and hashed.

Canonical pattern differences are audited against accessible aligned prior files; invalid/sentinel prior cells normalize to zero at float32 comparison precision. Private/unlinked rasters are not covered. A saturated historical density-probe/ignorance-raster union makes the original ≥20% absolute support-novelty diagnostic fail; that failure is retained. Unique newly inferred patterns and literal non-union are separate questions, and research release is not slot approval.

Catalogue targets may favor visible mapped structures. No hidden-label data/type/coverage disclosure exists. Four folds, one seed and weak proxy-negative correlation cannot prove sufficient independent views or public/private performance. External resource/provenance/license claims require actual official downloads and are not inferred from a mirror or metadata page.

## Generative AI disclosure

An Arena.ai coding agent assisted with repository inspection, literature/source reading, hypothesis design, code, tests, numerical analysis, documentation, website construction and review. The agent's text was not treated as ground truth. Model predictions and reported metrics were computed by executable scientific software on restored raster data; no reported organizer score, fault label or geothermal observation was generated or invented. The website's map is rendered from actual output bytes, not AI imagery.

The competitor remains responsible for eligibility, authorship, permitted data use, the accuracy of the narrative and final submission representations. This document does **not** certify eligibility, organizer input authentication, field verification or prize acceptance. See the official [GEMS rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf), process overview/AI disclosure/solution verification, and [problem specification](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).

## Resources and reproducibility

CPU only, two OpenMP threads and one BLAS thread, Python 3.11; exact scientific versions in `requirements-r2.txt`. Core feature raster ~419 MB, cached eligible-domain feature arrays ~1.05 GB, full-grid predictions/models under ignored `work/`. Several GB of working disk/RAM and public GitHub egress for mirror restoration/audit are required. `scripts/run_structural_pipeline.py --stage all` restores no credentials and does not interact with the portal. README has full restoration → prepare → validation → inference → static-site commands. A GPU is not required for this HGB implementation.
