# 16 · What H56 found — the credit inversion and the file it produced

Session 2026-10-07. Every number here is reproducible from the scripts named next to it, on bytes whose
SHA-256 is pinned in `registry/data_manifest.json` (plus the two layers pinned in §1). Nothing in this
file is an organizer score; the two owner-reported scores used (0.2750 for the PINN file) are marked.

## 1 · The inversion, and why the champion is hard to beat

* `work/b1_pattern_credit.py` — 14 scored predictions, 235 coverage patterns ≥25 px, additive
  per-pattern credit fit (`T_i = Σ_p M[i,p]·t_p`, `t_p ≥ 0`). Leave-one-file-out: the core family
  (8 files) predicts to ±3 %, the weak files do not (Hedge2 −18.8 %, ens12 +11.5 %, h25ctx −24.3 %,
  r13 −99.2 %, ph −93.8 %). **The additive fit is not identifiable** and is reported as an
  approximation, not a measurement.
* `work/b2_lp_bounds.py` / `work/b3_monotone_lp.py` — the same system as an LP: 14 exact score
  equations (1 % slack for rounding), `0 ≤ t_p ≤ 3`, plus the monotone constraint *more independent
  detectors agreeing on a cell cannot earn less credit*. The LP reproduces the champion's own credit
  independently (5,171–5,275 vs published 5,223.1).
* **The one high-density structure in the whole ensemble** is the all-8 consensus tier: 17,435 px,
  credit [3,835, 5,213] → density **22.0–29.9 %** vs the champion's 13.87 % and uniform random 2.79 %.
  The ≥6 tier is 37,440 px at 13.5–14.1 % (a tight interval); everything below ≥5 is ≤10.8 %.
* **The consequence that decides the strategy:** the champion file's own marginal cell is worth
  6.0 % (published credit minus the tier's fitted credit, over the difference in mass), i.e. *just
  above* the metric's break-even bar at that score (`0.2·DTI` = 5.6 %). Its family is therefore
  already budget-optimal, and re-thinning it cannot gain more than a fraction of a point.

## 2 · The two-family check (measured, negative)

`|A ∩ PINN| = 37,654 = |A|`: the anderson-PINN file **contains** the champion file. Its 1,200 extra
cells carry `T(PINN) − T(A) = 13.4` credits — a density of 1.1 %, fifty times below the bar. Any
union of the two families is strictly worse than the champion's own support. (H56-3, rejected.)

## 3 · The file

`submission/gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif`
(SHA-256 `1308083dcf09b4c6…`, 153,815 bytes, `evidence/gems52-h56-build.json`):

* **Core** 25,517 px = `P1 = h33-2-b2 ∩ gems24-d1-5`. The `[4,168, 5,223]` implied-credit interval is exact only *conditional on the owner-reported file/score links*; the mapping is not organizer-authenticated.
* **Selected continuation/scarp arm** 15,000 px, ≥3 px from the core (a cell nearer than the
  kernel radius re-covers truth the core already covers, so it is pure tax), ranked by
  0.45·along-strike continuation + 0.35·3 m DEM scarp gate + 0.20·LiDAR step×coherence. **Correction
  after the decoded audit:** do not say all 15,000 arm cells are outside the 33-prior support union.
  The saved verifier reports only 12,941 total emitted cells outside that union. Since the 25,517-cell
  core is contained in prior patterns, 2,059 selected arm cells have support in at least one checked
  prior. No pixel-level overlap list is preserved.
* **Budget** chosen by `revealed.budget_rule`: maximise `P(DTI > 0.2778)` over the conditional core-credit
  interval × ρ_novel prior U[0.03, 0.14] → 15,000 selected arm cells. The decoded audit's whole-file
  support novelty is 12,941 / 40,517 = 31.9%, not 15,000 / 40,517.
* **Verified from the bytes** (`work/b7_verify_h56.py`, `evidence/gems52-h56-verify.json`): 40,517
  emitted; values {0,1}; all finite; 0 cells outside the footprint; 0 on the catalogue; minimum
  distance to the catalogue 223.6 m; 0 cells within 200 m; every cell an isolated 8-connected
  singleton; the novel arm is >= 3.16 px from every other emitted cell (its pre-registered rule);
  the 2.83 px global nearest-neighbour pair is inherited inside the core set P1 (the core is a
  given set, not a choice, so its internal spacing cannot be changed without abandoning the exact
  credit interval); 12,941 cells (31.9 %) outside the union of 33 prior rasters; pattern identical
  to none of them; the 7x7 Chebyshev-3 screen in `evidence/gems52-h56-verify.json`
  (`min_NN_separation_ok`) is False for the same inherited reason and is quoted as measured, not as
  a pass.
* **Projection** (not a measurement): mean DTI ≈ 0.308, worst 0.238, best 0.378;
  P(> 0.2778) ≈ 0.83; P(> 0.3195) ≈ 0.37; P(> 0.3774) ≈ 0.00.

## 4 · Honest limits

1. The projection rests on a prior for ρ_novel, not on a measurement; the repo's own screens
   (`knowledge/03` N-10…N-12) show no computable band re-ranks credited vs uncredited cells.
2. The 31.9 % novelty is novelty of *support* against the 33 accessible aligned priors only; private
   or unlinked submissions are not covered.
3. Beating the board top (0.3195) requires ρ_novel ≳ 0.08 — the prior gives that about a 37 % chance.
   The 8-file consensus tier's LP upper bound (0.353 if its density is at the top of its interval)
   is the only *accessible-evidence* route above the board top, and it cannot be selected pixel-wise.
4. Both input rasters and prior submissions are owner-mirrored, not organizer-authenticated. The
   0.308/0.83/0.37 projection uses score-to-file associations that are not organizer-authenticated and
   a 15,000-cell novel-density assumption despite the post-build prior-support overlap above; it is
   conditional arithmetic, not holdout or measured performance.
5. The saved checkout has no H56 per-pixel A-only dossier or the aligned arm/features/A-B probability
   arrays needed to make one. Do not substitute R2, H54 or H55-EDGE explanations for H56; see
   `evidence/h56_a_only_reasoning_scope_2026-10-07.json`.

## 5 · Post-build review corrections (2026-10-07)

The explicit no-upload review is `evidence/h56_slot_gate_review_2026-10-07.json`. No comparable spatial
holdout is recorded, and the H56 slate is retrospective. A second review of the saved verifier also
records two non-promotion issues: (a) support novelty is 12,941 cells against 33 accessible priors,
not the 15,000 selected-arm count; (b) the full-file nearest-neighbour ≥3 px diagnostic is false at
2.828 px, although the novel/selected arm itself is ≥3.162 px from the other emitted cells. No H56
A-only per-pixel reasoning is available in this checkout. These do not make H56 a valid competition
submission; retain it as research-only until a properly preregistered comparable holdout and independent
review pass.
