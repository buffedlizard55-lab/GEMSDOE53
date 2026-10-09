# GEMSDOE32 H33-2-B2 and public row 0.2778 (score attribution unresolved)

Labels used below. **MEASURED** = computed in this repo from files (`evidence/`, `registry/`).
**OWNER-CLAIM** = stated on the GEMSDOE32 owner repo or site, not verified by an organizer.
**USER-REPORTED** = a score given in the brief or a ledger, not verified by an organizer or from a dated official read.
**HOLDOUT-DTI** = our proxy. Nothing here is an organizer score.

## What is verified (and what is not)

- **PUBLIC LEADERBOARD SNAPSHOT (S2, fetched 2026-10-08):** `extradr19` appears at 0.2778 (#13). This is a public board entry, not a submission-page receipt for H33-2-B2; nothing in the repositories links that row to a GEMSDOE32 file (IR-53-02). The owner's ledger (dated reads 2026-10-03) instead gives `extradr19` at 0.2449 (rank 19) and rank 1 at 0.3195, while the S2 snapshot lists rank 1 at 0.3774. The snapshots differ and the live page does not show its capture time (IR-53-01, IR-53-26).
- **OWNER-CLAIM:** the GEMSDOE32 README (read 2026-10-08) names `gemsdoe32-h32d-submodular-multipysics-46090` as its
  one-click file. An earlier landing-page read named `gemsdoe32-h33-h33-2-b2` as primary and UNSCORED, and
  that is the file behind the 0.2778 claim. The 0.2778 link to H33-2-B2 is not in the owner's ledger (IR-53-32).
- **OWNER-CLAIM (S20, S22):** the owner's analysis says the 0.2600 "d2.8" file is the model's own emission thinned
  by a 2.8 px distance rule to 44,090 dots, with none on the catalogue. It also says the score-to-file link is
  unresolved. It is not an organizer receipt.

## Why a sparse, dotted file can score well (MEASURED mechanism, on our proxy)

1. **Credit is the bottleneck, not dot count.** With alpha 0.2 and beta 0.8, a dot's false-positive cost is at most alpha
   (about 0.2 per dot at full cost). Credit comes from dots near truth. Two dots 1 px apart on the same truth share one
   credit: the metric takes the max over the kernel, not the sum.
2. **Spacing can turn the same dot budget into more distinct credit, but the available X2 measurement is not a valid holdout comparison.** X2 is labelled HOLDOUT-DTI (proxy; evaluator shared-template `src/metrics.py`, commit `dcbbb19`; 60,988 withheld catalogue positives in 3,199 segments; 5 folds; 95% t intervals, df 4). **Correction (IR-53-37):** `scripts/x2_ridge_holdout.py` defines negatives as `footprint & ~cat & ~buf`, where `buf` is made from withheld faults. These results therefore depend on hidden locations and are diagnostic only; they cannot establish that H2 beats the frozen baseline.

   | arm | pooled HOLDOUT-DTI (X2 design A; invalid for promotion) | 95% t CI, df 4 | TP_w | FP_w | FN_w |
   |---|---:|---:|---:|---:|---:|
   | HGB 19 bands, top-N | 0.026547 | [0.017965, 0.035025] | 1,998.5 | 130,448.8 | 58,989.5 |
   | ridge centrelines, top-N, no spacing | 0.022318 | [0.020251, 0.024437] | 2,071.8 | 218,124.3 | 58,916.2 |
   | ridge centrelines, Poisson 2.8 px | **0.050097** | **[0.042504, 0.057716]** | **4,678.0** | 218,266.5 | 56,310.0 |

   Values are pooled over five folds; FP_w accumulates across folds. TP_w + FN_w equals the 60,988 withheld catalogue pixels as a bookkeeping check. The pattern is consistent with metric-aware packing, but it is not a valid estimate of performance on the competition's unmapped targets and cannot satisfy the promotion gate. Source: `evidence/x2_ridge_holdout.json` and `scripts/x2_ridge_holdout.py`.
3. **So a file in the d2.8 family can score well for a reason the feature does not explain.** Thinning a thick
   emission into a spaced set of dots is what converts it into credit. This is the owner's own account (S22) and
   matches our measurement. It is not an organizer result.
4. **The 2-px catalogue prune** (the owner's step in H33-2-B2) removes dots that our holdout could not test. A dot
   adjacent to a mapped fault may earn credit on a new parallel fault, or may just be a false positive. It is untested
   here (L-17).

## Can we beat 0.2778?

- **Not established for the organizer's truth.** Our catalogue-proxy HOLDOUT-DTI rewards recovery of mapped faults only (L-02). The early design-A results appeared to favour larger dot budgets, but their withheld-buffer side channel makes that volume comparison invalid (IR-53-37, IR-53-28). User/owner board entries favour sparser outputs, but the score-to-file attribution is unresolved.
- **No valid claim that H2 beats the frozen holdout best.** X2's apparent 0.050097 versus the 0.035233 design-A comparator is invalid for promotion because both use the hidden-buffer negative pool (IR-53-37); H2 was not rerun under design B because the experiment budget was exhausted. Its X3 candidate is independently labelled DO-NOT-SUBMIT because the uniqueness gate failed. The H2 file's geometric structure is not evidence of an organizer score.
- **What would decide it:** an organizer receipt for a file with this structure, or an agreed chance-corrected
  overlap rule so that the lattice flag stops blocking dense dot files. Both need a decision from you.

## Action

- No submission slot is selected in this session.
- Keep the 0.2778 value labelled as a public leaderboard snapshot (S2), not a score attribution for H33-2-B2. Keep the 0.2708 value labelled OWNER-CLAIM. Only a submission-page receipt can link a file to an ORGANIZER-CONFIRMED score.
