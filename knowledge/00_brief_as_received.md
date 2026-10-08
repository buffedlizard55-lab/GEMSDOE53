# The brief, as received (standing starting point for this repo)

> **Provenance, updated 22:35 UTC.** The brief's **verbatim wording was recovered tonight** from
`README.md` §8 ("Original Task Prompt (Verbatim)") of commit `503f18e`'s parent chain on `main` — the PR #2
session recorded the full prompt as a fenced block. It is reproduced below and in the repo README. Two caveats
kept honest: (a) that copy is a *sibling session's transcription* of the Arena message, not the message
itself, and we cannot diff it against the original because this workspace holds no copy of it; (b) everything
written here before 22:20 UTC was a reconstruction from the session record, and where the reconstruction and
the recovered text disagree, **the recovered text wins** — the one substantive difference found was the
radiometric clause, which is conditional in the original ("plus any radiometric bands in
`training_features.tif`") and absolute in our earlier note; see `knowledge/04` and `IR-52-001` on the
register. Until 22:20 UTC this file stated the verbatim wording was unrecoverable; that statement was
correct about *this checkout* and wrong about the repository, because `main` had moved ahead of our base
commit and a fetch was the difference. Lesson recorded in `knowledge/03` §N-8: enumerate the remote refs
before declaring anything unrecoverable.

Version 2, recorded 2026-10-06 (UTC). Nothing here expires; every later instruction in this session
is additive.

## 1. The method

1. Treat the competition as a **co-training** problem: View A = the geophysical / potential-field
   layers, View B = the surface / geomorphic layers. Fit a separate model per view over the same
   unlabelled pixels.
2. The signal is **disagreement**, not agreement: a pixel where one view is confident and the other
   withholds is a candidate for something the catalogue does not contain. Agreement is where the
   catalogue already agrees with itself.
3. Ground this in the learning theory, and cite it: Blum & Mitchell, *Combining labeled and
   unlabeled data with co-training*, **COLT '98, doi:10.1145/279943.279962**. The theorem needs the
   two views' errors to be **conditionally independent given the label**.
4. Therefore **test the premise instead of assuming it**: measure the empirical correlation of the
   two views' out-of-fold errors on **spatial blocks**, and state the reading. If the errors are not
   independent enough, the arm is void and must be dropped — no submission slot on a refuted premise.
5. Pseudo-label **only** where one view is confident and the other abstains. Never pseudo-label from
   the catalogue itself.
6. Hold out **whole segments**, with a **buffer** between blocks, so that a fold never contains half a
   fault that the other half gives away.
7. Reason about each stratum geologically, not just numerically:
   - **A-only** (field confident, surface withholds) → a fault **buried under cover**. Write that
     reasoning out **for every candidate**, not once for the population.
   - **B-only** (surface confident, field withholds) → **suspect**: roads, canal levees, quarry
     faces, erosion. Down-weight, and say why.
8. Also report a **single-view baseline on hide-and-recover**: the honest yardstick is whether the
   two-view method beats each view alone at equal mass, on hidden segments.

## 2. The submission

9. Normalise predictions to **[0, 1]** and write a **single-band GeoTIFF** on the official grid
   (EPSG:32611, 100 m, same bounds as `sample_submission.tif`).
10. Placement must be **metric-aware**: use the DTI kernel/credit structure to decide which pixels to
    emit, rather than emitting a thresholded score field.
11. **Uniqueness gate**: every artefact must be new relative to everything this group has already
    submitted, and "the union of the previous ones" explicitly does not count as new.
12. Aim above the group's current best of **0.2778**, and explain first *why* that score is what it is.

## 3. Hypotheses

13. Propose **3–5 new geological hypotheses**. Each one must state: the layers it uses, its physical
    signature, why it can find catalogue-missing faults, how it differs from what is already in this
    repo's history, and its expected DTI gain and cost. Rank them.
14. Validate the top one on a **spatially-blocked holdout** *before* spending a submission slot.

## 4. Data and knowledge

15. Any new external data must be **free, official, and confirmed obtainable**, with a licence that
    permits use and sharing with the sponsor.
16. Store the knowledge gathered here so the next session does not re-derive it.

## 5. The site

17. A clean **GitHub Pages** site for this repo, with the `.tif` **one-click download obvious at the
    very top**. The site must be able to produce the file the submission needs; "as easy as download
    the file and submit it", and that requirement belongs in the executive summary / the top of the
    page.
18. An **executive-summary subpage** carrying the exact submission instructions.
19. Fix the portal's **"Predicted values must be in range [0, 1]"** error for good.
20. A **unique submission name** plus a short note explaining what it is.
21. A **live, up-to-date data feed** so that nothing on the page has to be checked by hand.
22. Core Values: **Maximize P(Win)** and **Own the Outcome**.
23. Work in **three verification passes**, flag every irregularity found, give official links for
    manual review, and finish with a **pull request, then merge to main**. Zero manual input from the
    user; no hallucinated facts.

---

## Appendix · the recovered verbatim text

```text
Always keep in mind Arena Core Values:
1. Maximize P(Win): Spend cycles where they change the expected score. Don't polish infrastructure when the model is the bottleneck; don't tune hyperparameters when the features are missing the signal.
2. Own the Outcome: Verify end-to-end. A script that "should work" hasn't worked; a submission file that wasn't checked on disk isn't ready; a claim without a number in `evidence/` is a guess.

Work autonomously with zero manual input from the user. Verify everything line by line from official trusted sources with links. Flag any irregularities for review. Do not hallucinate and make stuff up. Put the prompt into the README.md.

For the DOE GEMS challenge (https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/ & https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ & https://www.drivendata.org/competitions/306/competition-doe-gems/ & https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ & https://www.drivendata.org/competitions/306/competition-doe-gems/data/ & https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0 & https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0 & https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0):

Use the Blum & Mitchell (COLT '98, doi:10.1145/279943.279962) co-training setup:
- Split features into two views:
  * View A — potential-field and subsurface (gravity, magnetics, strain, seismicity)
  * View B — surface (DEM-derived curvature and slope, plus any radiometric bands in `training_features.tif`)
- Test conditional independence empirically by correlating each view's errors on labeled negatives — if strongly correlated, abandon co-training.
- Pseudo-label only where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches evaluation.
- Use **disagreement as the discovery signal**:
  * A confident, B not → buried fault candidate beneath cover (flag for Phase 2 geological reasoning)
  * B confident, A not → surface artifact (roads, erosion lines) to suppress
- Compare against a single-view baseline on hide-and-recover segments to verify co-training isn't amplifying bias.
- Normalize to [0, 1], apply metric-aware placement, run the uniqueness gate, and confirm the output is not merely the union of the two views.
- For Phase 2 readiness, write a short geological reasoning note for every A-only candidate so reviewers can evaluate the buried-fault calls.

Study, analyze and explain why the following had the highest score out of the listed GEMSDOE websites and how to beat the 0.2778 score and get the top score of 0.3195 on the leaderboard:
- https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html - h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778
- https://buffedlizard55-lab.github.io/GEMSDOE36/docs/ - gemsdoe36-anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros.tif: 0.2750
- https://buffedlizard55-lab.github.io/GEMSDOE44/docs/
- https://buffedlizard55-lab.github.io/GEMSDOE46/

We're at ~0.2778 vs 0.3195 top on GEMS. The remaining ~0.04 gap is almost certainly geological domain knowledge, not post-processing. Generate 3–5 candidate geological hypotheses we haven't tried yet. For each:
1. What data layers it combines (name the bands in `training_features.tif` or external sources)
2. What physical signature it looks for
3. Why it should catch faults missing from the USGS/INGENIOUS catalogue
4. How it differs from our previous implementations
Rank them by expected DTI improvement vs implementation cost, and we'll validate the top one on spatially-blocked holdout before touching a submission slot. Do not spend a weekly submission slot on an idea that hasn't beaten our current holdout best on spatially-blocked validation.

Once the competition rasters are placed in `data/` (`bash scripts/download_competition_data.sh` if you have URLs, or manual drop from DrivenData) and `python scripts/prepare_data.py` is run, the full model pipeline can be executed and verified. Do all of this autonomously with zero manual input from the user.

Fix the "Predicted values must be in range [0, 1]" error. Must generate a UNIQUE .tif submission for the competition. Never copy a previous submission as the final output. Make sure the Github pages is clean and user-friendly. Have the one-click TIF/ZIP file download at the very top so the user does not have to scroll down and search for it. Provide a unique submission name and <=200-char submission note. Provide an Executive Summary subpage on the Github pages website as well.

Do your work in 3 passes:
Pass 1 — Implement and verify: Complete the task end-to-end. Run tests, linters, type-checks, or build steps that exist in the repo, and verify your changes actually work rather than assuming they do.
Pass 2 — Review and fix: Re-read every file you touched or created. Look for bugs, unhandled edge cases, broken imports, type errors, regressions, leftover debug code, or unintended changes. Fix anything you find and re-verify.
Pass 3 — Re-check against the user's original request: Re-read the user's prompt from the top and confirm every requirement, constraint, and detail they asked for is addressed. If anything is missing or only partially done, complete it now.

Please remember to create a PR once you are done.
```
