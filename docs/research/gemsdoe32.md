# GEMSDOE32 (the 0.2778 candidate): why it may score high, and whether we can beat it

Labels used below. **MEASURED** = computed in this repo from files (`evidence/`, `registry/`). **OWNER-CLAIM** = stated on the GEMSDOE32 owner site or README, not verified. **LEADERBOARD** = public DrivenData page (snapshot time not stated). Nothing here is an organizer score.

## What is verified

- **LEADERBOARD:** `extradr19` is listed at 0.2778 (#13) on the public leaderboard. Nothing in the repositories links that row to the GEMSDOE32 file (IR-53-02).
- **OWNER-CLAIM:** the GEMSDOE32 site says the file is `H33-2-B2`, built from a 0.2708 base by removing dots within 2 px of the public catalogue, with 37,654 dots. It also says "NO ORGANISER SCORE EXISTS". Its 0.2747 figure is a model projection, not a score.
- **MEASURED:** the registry copy of that file (`gemsdoe32-h33-h33-2-b2-…-e5eb6e7e`) has **37,654** dots. That matches the owner's count, so the file content is consistent with the owner's description.
- **MEASURED:** our candidate has rank correlation 0.009 with that file and 21.8% of our dots within 3 px of its dots (`evidence/uniqueness_check.json`). Our file is not a copy of it.
- **MEASURED (updated 2026-10-08, 613-raster population, `evidence/uniqueness_check.json`):** the GEMSDOE32 family in the registry (25 single-band rasters) has rank correlations at most 0.378 with our candidate and dot overlaps at most 0.508. None exceeds the 0.90 or 0.70 flags. The earlier 24-raster figures (rho 0.044, overlap 0.45) came from the old 138-file population and are not comparable (IR-53-23).

## Mechanism that could make a sparse, catalogue-pruned file score well (hypothesis, corroborated on our own holdout by E6)

1. The rules score distance-weighted Tversky with alpha 0.2 (false positive) and beta 0.8 (false negative), using a 300 m triangular kernel (rules worked example, S1). A dot within 3 px of a true fault earns partial credit, so the metric rewards placing dots close to where the new faults are, and penalises false positives only lightly.
2. Our HOLDOUT-DTI proxy rises with the share of the footprint emitted: 0.0217 at 0.5%, 0.0251 at 0.73%, 0.0279 at 1%, 0.0352 at 2% (`evidence/exp2_holdout_arms.json`, bands arm, raw probabilities). In this regime more dots score more, so a file with a sensible dot count and placement near faults is competitive. This is a property of the proxy. It is not an organizer result.
3. If the scored truth is new faults only (S1, "Labels"), a dot sitting on a mapped fault is a false positive (weight 0.2). Removing dots within 2 px of mapped faults (the owner's step) therefore cuts false positives. It is the same idea as our zeroing of known-fault pixels. Whether this is what moved the score is untested.
4. **E6 (session 3) corroborates the value-scale half of the mechanism on our own holdout.** The metric's FN term is `sum over gt of (1 - max neighbourhood p*k)`, so it only collapses when emitted values approach 1. Keeping the model's raw probabilities (mean ≈ 0.5 on kept pixels) leaves most of the FN mass on the table. Re-emitting the SAME model's ranking as **binary value-1.0 dots** raises pooled HOLDOUT-DTI from 0.0352 (raw @ 2%) to **0.0484 (bin @ 5%, 95% CI [0.0421, 0.0548])**, and the sweep's optimum sits exactly where the credit per dot (0.00995) crosses the break-even bar 0.2·DTI (0.00855) — the same break-even the GEMSDOE32 owner reports measuring empirically (0.0548) and deriving from the published formula (0.2·0.26 = 0.0520). Two independent derivations of the same bar, and our sweep lands on it. The placement AUC is unchanged (0.742–0.781), so the gain is value scale and volume, not a better detector.

So the most likely reason a 37–46k-dot file ranks well is: **high-value (≈1.0) dots, a sensible emission volume, placed off the catalogue, with a light false-positive penalty**. We have not measured that the owner's file scores 0.2778. We also cannot tell whether the score comes from the pruning or from the model.

## Can we beat it?

- **Not established.** We have no organizer score for any file from this repository. Our only number is a catalogue-holdout proxy, which is not comparable with the leaderboard (IR-53-03).
- The bar on the public leaderboard is 0.3774 (#1, re-fetched 2026-10-08), with 0.3345 at #2 and 0.3195 at #7. A 0.2778 file is at #13, so beating it would need a ranking gain of at least 12 places.
- The session-3 published candidate (`gems53-hgb-bands-bin-q0p0073`) applies the corroborated mechanism (binary value-1.0 dots, 0.73% volume, catalogue pixels zeroed) and passes every release gate, including the operative uniqueness gate (IR-53-26). Its holdout proxy (0.0343 at q=0.0073; the score-optimum volume q=0.05 scores 0.0484 but is a mutual near-copy of an existing same-volume submission and is rejected by the gate) is not an organizer score and cannot rank it against the leaderboard.
- The untested routes with the highest expected value: H7 (radiometric K/eTh alteration index from the USGS GeoDAWN radiometric grids — verified obtainable, S15/S20, CC0 — but not in the 19-band stack; L-15), H6 (elevation curvature), H8 (strain–topography coherence), H9 (seismicity–structure interaction).

## Action

The unique submission is generated, validated, and offered for download (`docs/downloads/`). Promotion to a competition slot is a separate selector step within the weekly cap. Before any slot decision: re-check the leaderboard (S2), confirm the operative uniqueness gate with the protocol owner (IR-53-26), and draft the generative-AI disclosure the rules require (rules 3.2; IR-53-24).
