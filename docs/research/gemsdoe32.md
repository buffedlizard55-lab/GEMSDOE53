# GEMSDOE32 (the 0.2778 candidate): why it may score high, and whether we can beat it

Labels used below. **MEASURED** = computed in this repo from files (`evidence/`, `registry/`). **OWNER-CLAIM** = stated on the GEMSDOE32 owner site or README, not verified. **LEADERBOARD** = public DrivenData page (snapshot time not stated). Nothing here is an organizer score.

## What is verified

- **LEADERBOARD:** `extradr19` is listed at 0.2778 (#13) on the public leaderboard. Nothing in the repositories links that row to the GEMSDOE32 file (IR-53-02).
- **OWNER-CLAIM:** the GEMSDOE32 site says the file is `H33-2-B2`, built from a 0.2708 base by removing dots within 2 px of the public catalogue, with 37,654 dots. It also says "NO ORGANISER SCORE EXISTS". Its 0.2747 figure is a model projection, not a score.
- **MEASURED:** the registry copy of that file (`gemsdoe32-h33-h33-2-b2-…-e5eb6e7e`) has **37,654** dots. That matches the owner's count, so the file content is consistent with the owner's description.
- **MEASURED:** our candidate has rank correlation 0.009 with that file and 21.8% of our dots within 3 px of its dots (`evidence/uniqueness_check.json`). Our file is not a copy of it.
- **MEASURED:** the GEMSDOE32 family in the registry (24 rasters) has rank correlations at or below 0.044 with our candidate. The highest dot overlaps are 0.45 (`h32d-submodular`), 0.43 and 0.42, and none exceed the 70% flag.

## Mechanism that could make a sparse, catalogue-pruned file score well (hypothesis, not tested)

1. The rules score distance-weighted Tversky with alpha 0.2 (false positive) and beta 0.8 (false negative), using a 300 m triangular kernel (rules worked example, S1). A dot within 3 px of a true fault earns partial credit, so the metric rewards placing dots close to where the new faults are, and penalises false positives only lightly.
2. Our HOLDOUT-DTI proxy rises with the share of the footprint emitted: 0.0217 at 0.5%, 0.0251 at 0.73%, 0.0279 at 1%, 0.0352 at 2% (`evidence/exp2_holdout_arms.json`, bands arm). In this regime more dots score more, so a file with a sensible dot count and placement near faults is competitive. This is a property of the proxy. It is not an organizer result.
3. If the scored truth is new faults only (S1, "Labels"), a dot sitting on a mapped fault is a false positive (weight 0.2). Removing dots within 2 px of mapped faults (the owner's step) therefore cuts false positives. It is the same idea as our zeroing of known-fault pixels. Whether this is what moved the score is untested.

So the most likely reason a 37–46k-dot file ranks well is: sensible emission volume, placed off the catalogue, with a light false-positive penalty. We have not measured that the owner's file scores 0.2778. We also cannot tell whether the score comes from the pruning or from the model.

## Can we beat it?

- **Not established.** We have no organizer score for any file from this repository. Our only number is a catalogue-holdout proxy, which is not comparable with the leaderboard (IR-53-03).
- The bar on the public leaderboard is 0.3774 (#1), with 0.3195 at #7. A 0.2778 file is at #13, so beating it would need a ranking gain of at least 12 places, which our blocked candidate cannot give.
- The main untested route is H1 (segment-exact learn-predict separation, `docs/research/hypotheses.md`). It was not run within the budget.

## Action

Do not use a submission slot on a GEMSDOE32-style file. The only candidate built here is blocked by the protocol overlap flag (`evidence/overlap_baseline.json`, lift up to 4.2× over random placement). Any new candidate needs a fresh uniqueness check and an explicit decision to spend the budget.
