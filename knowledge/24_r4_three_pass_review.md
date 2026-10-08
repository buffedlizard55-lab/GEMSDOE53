# Round 4 — three-pass review

Pass 1 implemented and ran the pipeline. Pass 2 reviewed it against the receipts. Pass 3
re-checked the results against the original request. This file is the defect list, because
next session will not remember and most of these fail silently.

Fourteen defects, grouped by how they fail. **Eight were caught by tests before they
reached a receipt; six were caught by reading the receipts against the code.**

---

## Wrong numbers reported as findings (the dangerous class)

**1. `blocked_auc` ranked globally, not within blocks.**
The Mann-Whitney U statistic is defined on ranks 1..n of the block being scored. Using
global ranks inflated a perfectly separated 4-pixel block to **2.5** instead of 1.0, a
reversed block to 0.5 instead of 0.0, and an all-tied block to 1.5 instead of 0.5 — a
constant offset of +1.5 that would have made every AUC look better than it is. The
docstring asserted the substitution was harmless. *Fixed and tested.*

**2. `budget_confound` reported `r = 0.0, p = 1.0` for a degenerate regression.**
When the board is strictly monotone in budget over the sample, regressing the board on
budget leaves an *exactly zero* residual. The implementation reported that as a null
correlation. It is the opposite: the relationship is perfect and inseparable from budget.
A fabricated null is worse than no assay. Now returns `r = None, degenerate = True`.
*Fixed and tested.*

**3. `random_control` was generated at one fixed budget.**
The arms stage built the uniform-random control at 37,654 px and then scored it at
20,000 / 37,654 / 70,000. At 70,000 it only had 37,654 pixels to draw from, so it
understated what random achieves — a blind control. Now one field of iid uniform scores
over every allowed pixel, whose top-k is a uniform subset of size k for every k at once.
*Fixed.*

**4. The emitter wrote 37,655 pixels when 37,654 were requested.**
`_threshold_for_topk` used a quantile, so every pixel tied at the boundary value was
included. Submissions are compared like-for-like at a fixed budget, so the count has to
be exact. Replaced with `topk_mask`, which uses `argpartition` and returns exactly k.
*Fixed and tested, including the all-tied case.*

---

## Silent no-ops and contract violations

**5. `whole_segment_folds` conflated the training-exclusion mask with the emission mask.**
The held-out segment and its buffer were removed from *both*, so the emitter was scored
on its ability to place pixels where it was forbidden to place them. Measured truth
survival was **0.000**. Now the two masks are separate objects, survival is **1.0000** on
all four folds, and the stage raises below 0.9 rather than reporting a number nobody
reads. *Fixed and tested.*

**6. `block_error_table` ranked over `allowed` instead of `pos | allowed`.**
Ranking inside the emission mask excludes the catalogue pixels themselves, so the "how
many known faults did we miss" count was taken against a set containing no known faults
and the miss rate came back **all-NaN**. *Fixed and tested.*

---

## Crashes

**7. `gather` with `np.ix_` is a cross product.** Three index arrays asked numpy for
**5.90 TiB**. `stack[:, rows, cols]` broadcasts the two adjacent advanced indices
element-wise instead; the result is `(L, n)`, transposed to `(n, L)`. *Fixed and tested.*

**8. `_deferral` returned a 2-D array into a boolean assignment.** NumPy rejects boolean
indexing with a 2-D input. *Fixed by the arm test.*

**9. `random_control` built 2,450 values for 137 picks** — ranked over `idx.size` and
permuted, then indexed with a 137-element selection. *Fixed by the budget test.*

**10. `log()` in the driver did not accept `flush=`** but `full_fit_predict` passes it.
*Fixed.*

**11. `fit_view` received an all-zero fold array to mean "no cross-validation"**, which
produced an empty training set and then `b.max()` on a zero-size array. Added an explicit
`cv=False` parameter. *Fixed.*

**12. The champion reference path was wrong** — `data/ref_h33_2_b2.tif` instead of the
restored `data/reference/h33-2-b2-zeros.tif`. *Fixed.*

---

## Environment and registry

**13. `IR-52-034` was cited but not registered.** It had been added by the pre-reset
session, never committed, and destroyed. The repo's own
`test_every_irregularity_id_cited_in_the_repo_exists_in_the_register` caught it.
Re-registered with an explicit `provenance_warning`: the measured half is reproducible
from committed code, the documentary half rests on a contractor read-me that was
destroyed and must be re-verified against a re-fetched copy.

**14. `tests/test_h59.py` opened `work/h59_pinned/labels.tif`**, which the reset wiped.
It is a `restore_data.py` target, so `--only labels` restored it. This failure was a
symptom of the reset, not a code defect.

---

## What pass 3 concluded against the original request

The request was to build a two-view co-training round and produce a unique, submittable
TIF. Delivered: 74-layer plan, both views fitted, 18 arms compared under matched-budget
hide-and-recover, one raster emitted at exactly 37,654 px with all gates passing and a
maximum Jaccard of 0.043 against all 16 prior submissions.

What pass 3 would not let stand:

- **The instrument cannot promote.** Uniform random beats the champion. Any candidate
  ranking that rests on it is measuring budget. Filed as
  [issue #31](https://github.com/buffedlizard55-lab/GEMSDOE52/issues/31).
- **The views are not independent** (max \|ρ\| = 0.705 against a 0.60 threshold), so
  calling the exchange "co-training" overstates what it is.
- **Two pre-reset findings did not reproduce** — the consensus-arms-worse-than-random
  result, and the independence verdict. Both old and new numbers are recorded in
  `knowledge/23`; neither is presented as a re-measurement of the other.
- **The emitted raster is labelled `research`** because nothing available can compare it
  to the incumbent. It beats random 12.4× and A_only 5.2×, and that is the whole of the
  evidence behind it.

## Remaining work

1. Re-fetch `data/external/audit_sources/GeoDAWN_ReadMe.pdf` and re-verify IR-52-034's
   documentary half.
2. Re-derive the board column for the historical rasters so the budget-confound partial
   correlation can be estimated on real leaderboard scores rather than placeholders.
3. Fix the view split, or stop calling the exchange co-training.
4. Re-measure the halo defect (pre-reset: our top-37,654 at median 412 m from the
   catalogue, the champion's at 1,965 m) — not re-run this session.
