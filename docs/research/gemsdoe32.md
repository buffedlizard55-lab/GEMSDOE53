# GEMSDOE32 (the 0.2778 claim): why a dotted file can score high, and whether we can beat it

Labels used below. **MEASURED** = computed in this repo from files (`evidence/`, `registry/`).
**OWNER-CLAIM** = stated on the GEMSDOE32 owner repo or site, not verified by an organizer.
**USER-REPORTED** = a score given in the brief or a ledger, not verified by an organizer or from a dated official read.
**HOLDOUT-DTI** = our proxy. Nothing here is an organizer score.

## What is verified (and what is not)

- **USER-REPORTED:** `extradr19` at 0.2778 (#13). Nothing in the repositories links that row to a GEMSDOE32 file (IR-53-02).
  Our static fetch of the DrivenData leaderboard returned "Loading..." (client-side), so we read no leaderboard
  number ourselves. The owner's ledger (reads dated 2026-10-03) gives extradr19 at 0.2449 (rank 19) and rank 1 at
  0.3195. The brief gives rank 1 at 0.3774. These cannot both be right for the same snapshot (IR-53-26).
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
2. **Spacing turns the same dot budget into more distinct credit.** On our holdout (X2, 44,090 dots per fold, 5 folds):

   | arm (HOLDOUT-DTI) | pooled DTI | TP_w | FP_w | FN_w |
   |---|---:|---:|---:|---:|
   | HGB 19 bands, top-N | 0.0265 | 1,998.5 | 130,448.8 | 58,989.5 |
   | ridge centrelines, top-N, no spacing | 0.0223 | 2,071.8 | 218,124.3 | 58,916.2 |
   | ridge centrelines, Poisson 2.8 px (ours) | **0.0501** | **4,678.0** | 218,266.5 | 56,310.0 |

   (Pooled over 5 folds, so FP_w counts about 5 x 44k dots. TP_w + FN_w equals the 60,988 catalogue pixels in every
   arm, which is a structural check of the bookkeeping.) At the same false-positive cost, packing more than doubles the
   credit. Source: `evidence/x2_ridge_holdout.json`.
3. **So a file in the d2.8 family can score well for a reason the feature does not explain.** Thinning a thick
   emission into a spaced set of dots is what converts it into credit. This is the owner's own account (S22) and
   matches our measurement. It is not an organizer result.
4. **The 2-px catalogue prune** (the owner's step in H33-2-B2) removes dots that our holdout could not test. A dot
   adjacent to a mapped fault may earn credit on a new parallel fault, or may just be a false positive. It is untested
   here (L-17).

## Can we beat 0.2778?

- **Not established for the organizer's truth.** Our only evidence is HOLDOUT-DTI, which rewards recovery of mapped
  faults (L-02). The holdout favours larger dot budgets; user-reported board entries favour sparser ones (IR-53-28).
- **Our candidate (H2) beats the frozen holdout best** (0.0501 at 44,090 dots versus 0.0352 for the repo's best
  at 103k dots) and the same-budget HGB baseline. It is not a byte copy of any registry file, and its dot-level
  rank correlation is at most 0.09. Its uniqueness gate fails at the surface level against two team files (GEMSDOE46
  dfa-corroborated, lift 3.6; GEMSDOE40 eulerdepth-si0, lift 5.6; `evidence/overlap_baseline_v2.json`). The file is
  therefore DO-NOT-SUBMIT.
- **What would decide it:** an organizer receipt for a file with this structure, or an agreed chance-corrected
  overlap rule so that the lattice flag stops blocking dense dot files. Both need a decision from you.

## Action

- No submission slot is selected in this session.
- Keep every GEMSDOE32 number labelled USER-REPORTED or OWNER-CLAIM until a dated official read or receipt exists.
