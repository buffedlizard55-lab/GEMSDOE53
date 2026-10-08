# R2 three-pass scientific and engineering review

Current brief: `08_current_user_prompt.md`, reproduced in full in README. Read both at every session. Core values: **Maximize P(Win)** by refusing a failed slot gate; **Own the Outcome** by completing inference, byte checks, publication, tests and disclosure.

## Pass 1 — restore, preregister, implement, measure

- Restored all 23 pinned inputs autonomously. Core features 418,912,844 B, labels 425,830 B, sample 1,599,597 B. Input integrity is verified against owner pins, **not authenticated against organizer downloads**. Data page redirects to login.
- Ran preparation and initial suite: 25 passed, 1 skipped before R2 rewrites. CPU training is possible; the brief's GPU-only blocker was stale.
- Ranked four geological hypotheses **before implementation**; froze seed/folds/learner/budgets/exchange rules in `registry/r2_preregistration.json`. Registration SHA is recorded by validation. None needs unobtained external data.
- Built 57 label-free feature columns with normalized convolution and 36 px conservative support erosion. A=34 columns (17 raw + 17 transforms), B=18 (2 raw + 16 transforms), cross=5. There are no radiometric bands in the actual 19-band input.
- Trained four fixed HGB learners per fold; evaluated six arms with actual incremental triangular max-cover placement and matched density. Original 8-connected components are whole, no train/truth component sharing, 80 px (8 km) training buffer, held tails included, unsupported truth remains FN.
- Actual local means: raw fusion **0.144376**; A **0.107543**; B **0.194671**; naive max/union **0.189424**; registered structural contrast **0.193167**; disagreement router **0.162120**. Primary minus strongest baseline **−0.001504**, 2/4 positive. Required +0.005 and 3/4. **FAIL.** No post-hoc replacement of the primary.
- Measured 4,201,273 finite held-out proxy-negative predictions in 2,093 spatial blocks. Largest absolute Pearson/tie-aware Spearman **0.071094**; weak proxy correlation permits a separate trial, not a conditional-independence/sufficiency proof.
- One-round, training-only, buffered whole proposal-component exchange: 428 pixels to B and 777 to A across folds, zero evaluation pixels. B mean increased only ~0.000141; A degraded. These pseudo-labels are **not in the primary TIFF**.
- Final model re-fitted using available core labels and features, never a prior TIFF as base or feature. A research artifact is allowed after failed model validation, but not promoted or uploaded.

## Pass 2 — defects found and fixed, not hidden

1. **H33 explanation was wrong.** Raster comparison: base 40,199 dots, H33 37,654, exactly 2,545 deleted, none added. All deletions are off-catalogue and within 200 m. Staff say known pixels are masked and do not pay penalties. Pruning weak flank mass is consistent with the reported gain, not proof of its cause. Hidden truth and authenticated paired uploads are unavailable.
2. **Mathematical overclaims.** Restored the TP term in simplified DTI: `T/(0.2T+0.2F+0.8G)`. General marginal rule `c(1−0.2s)>0.2sf`; isolated uncovered-pixel special case `w>0.2s`. At s=.2778 the 283 m diagonal clears the bar, so a universal 224 m cutoff is false. Hidden prevalence and the old 0.464 ceiling are retracted. Uniform scaling alone does not prove a global optimum; a density-weighted coverage surrogate is not expected DTI.
3. **Emitter defects.** Fixed zero-padding/convolution boundary behavior, implemented genuine incremental lazy greedy max-cover gains, corrected the always-one FP discount and candidate-pool statistic. FP discount's independent-Bernoulli assumption is disclosed and unused in matched-budget runs.
4. **Old negative OOF report invalid.** It persisted only positive predictions, had zero-error blocks, undefined Pearson and tie-wrong Spearman. R2 persists actual finite negative predictions and fails closed for missing/constant/insufficient errors. Legacy correlation/title/abstention helpers corrected; no positive-only fallback.
5. **Input-array integrity.** Initial validation aborted on an index mapping mismatch: the first 496 index entries were zero, and some first-page raw-column values disagreed with inputs. Cause was not proven. No metrics from that attempt were accepted. Rebuilt with atomic, explicitly flushed array writes, numerical rereads, exact `flat_idx == flatnonzero(valid)` and per-column SHA checks. Avoid unverified memory-map assumptions.
6. **Uniqueness is not new geographic coverage against every historical raster union.** Original ≥20% union-support novelty test failed: 0% novel against a 5.36M-cell union in the initial 380-file audit, despite no canonical decoded match and max Jaccard only 0.04958. One historical `5GEMSDOE` density-probe has **5,106,385 positive cells**; GEMSDOE48 ignorance-mass diagnostics add 4.2M cells at ≥.5, but are not fault probabilities. This saturates almost the whole survey. The old criterion is retained as a **failed diagnostic**, not silently relabeled passed. Research publication now separately requires canonical-distinct values against every supplied aligned file and not a literal prior/view union. The registered primary/model/slot gate is unchanged and still FAIL. No prior mask is used to alter the new model to 'game novelty'.
7. **Incomplete source transport/inventory.** Failed TLS is not 404/not-public. Owner-source GitHub API blobs are immutable mirrors, not deployed HTTP evidence. Enumerate TIFFs in docs/prediction/submission locations, including nested experiment directories; collapse same-blob aliases. Inaccessible/misaligned records retain reasons. Byte/canonical comparison scope remains accessible inventory only, not private/unlinked global novelty.
8. **Incorrect source assumptions.** Organizer staff explicitly decline to reveal hidden-label source/types/coverage. No LiDAR-only label story. A-only is not verified burial; B-only is not automatically a road. Seismic density is 100 km context. Electrical conductivity is not well thermal conductivity. Regional stress orientation is not a hard prohibition on every oblique/legacy/transfer fault; sibling PINN claims are not inherited as facts.
9. **Feed safety/freshness.** Removed hardcoded old branch, incorrect footprint/label counts, unsupported prevalence bracket and bogus universal placement rule. DrivenData Terms prohibit automated access; a live scraping schedule was not legitimate absent permission. Local evidence refresh remains automatic; external observed date is never refreshed by a local regeneration. No portal automation/credentials.
10. **Prompt/site.** Full current task text preserved in README and knowledge. Removed outdated active-page claims and old forced-artifact promotion. Top-of-page research download, unique filename/name/note, exact conditional submission instructions, raw-range/mask disclaimer and every A-only reasoning row.

## Pass 3 — acceptance matrix and final verification

| Requirement | Outcome / evidence |
|---|---|
| Genuinely new TIFF, no copied prior as inference base | New HGB inference from core rasters only; decoded pixel hash in submission receipt; all accessible comparisons and source inventory published. |
| [0,1], single-band float32, exact template geometry | Re-opened actual TIFF, raw min/max/finite and band/shape/CRS/transform checks; internal validity mask matches sample, no .msk sidecar. Local policy, **not proven portal acceptance**. |
| Not simply A/B union | Independently placed A/B masks compared; equality false and actual union pixels dropped; independently re-emitted same-budget max-view union also differs at 32,553 output pixels. Full numbers in `not_union_r2.json`. |
| Full prompt in README and read each session | Full current message included and exact embedded-file presence tested; AGENTS provides startup order. Older prompt/readme is explicitly archival. |
| 3–5 hypotheses before implementation | Four, exact layers/physical signature/missing-catalogue mechanism/cost/expected-lift judgment; frozen config precedes code. |
| Real negative OOF / abandon strong correlation | Actual predictions on held-out proxy negatives, tie-aware correlations; fail-closed missing/constant rules and regressions. Low observed correlation is not proof. |
| Whole-segment buffered pseudo-labels | Whole proposal components, one block, rejected boundaries/forbidden samples, train-only receipts, zero evaluation overlap; one trial, not in primary. |
| Single-view comparison and slot discipline | Strong B control beats primary. Scientific gate FAIL; no forced promotion, **0 slots**. |
| Every A-only candidate reasoning | Coordinate/score/raw signature/alternatives/status CSV for **each emitted A-only pixel**, exact row-count receipt. No verified geology or vents. |
| Official trusted sources + irregularities | 17 bounded claim records with primary/manual links; owner score attribution and source/deployment/auth/license limitations separated. |
| Easy clean Pages UI, executive guide, feed | Direct TIFF/ZIP at beginning and guide, audit/CSV links, real north-up output map, responsive tables, source policy and dated local feed. Static distribution, not browser training. |
| Three substantive passes | Implementation/results, mathematical/data/emitter/feed fixes, then full acceptance/tests/site checks/PR/deployment verification; final execution receipt updated at publication. |
| PR merged to main | Recorded in final execution receipt after real `gh` create/check/merge. No promise of merge before it happens. |
| Actual score above .2778/.3195/.3774 | **NOT established.** No organizer submission; current registered hypothesis failed the best comparable local control. Do not upload. |

Final unit/site/browser/download/PR checks and the full accessible inventory counts are in `evidence/review_execution_r2.json`. Older test counts above are dated stage results, not the final suite. Range/novelty tests must not be confused with scientific promotion. The ≥20% support diagnostic remains failed.

## Next session — ordered, actionable

1. Read README/full prompt/this review. Preserve failed results, zero slot use and the frozen surface control. Do not spend a slot on this file.
2. Freeze untouched confirmation regions before implementing paired-shoulder R2-H2. Audit correlated component/block geography and stronger-negative uncertainty; add raw-B vs transformed-B and signed-cross-feature ablations to isolate the real source of any gain. Related profile methods now exist in GEMSDOE47; do not claim global novelty.
3. Refit the historical incumbent's actual generator on the SAME folds. Recompute every catalogue-derived mask from visible training labels only. Do not score a fully labelled shipped historical TIFF on held catalogue truth and call it clean validation.
4. Registered 25k/50k secondary budget sensitivity should be explicitly reported without changing the locked primary. Additional seeds/held regions are confirmation, not new opportunities to cherry-pick.
5. Authenticate mirrored core files against allowed organizer downloads. Obtain actual official licensed 1 m/radiometric resource bytes and coverage receipts before external experiments. Metadata availability alone is not a verified data download. No unresolved mirrored derivatives or geothermal point labels as surrogate fault truth.
6. Geological verification must distinguish density/lithology/processing contacts from displaced faults, and faults from permeable, hot geothermal systems. Review A-only coordinates/alternatives independently.
7. Obtain sanctioned source access/permission if a live DrivenData feed is essential. Until then retain dated observations. Never ask for passwords/tokens or automate account slots.
8. Only reconsider an upload after a predeclared candidate clears best comparable baseline, frozen incumbent confirmation, format, canonical pattern novelty, literal non-union, and geological review. Record actual submission ID/hash/score/timestamp without reconstructing hidden truth.

## Concurrent main integration

H53 (PR #8) was merged while this branch worked. Its complete code/rasters/evidence/registry/tests and global incumbent pointer are preserved. Original pages/README archived, dedicated `docs/h53.html` summary linked. R2 has a separate marker and never claims protocol-comparable superiority. Combined suite: 86 passed; inherited H53 structure-tensor overflow warnings flagged, not presented as scientific validation.
