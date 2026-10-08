> Provenance and integrity note. This file reproduces, as a fenced block, the instruction set this
> session was given, in the order and wording it arrived. It is a record of the task, not evidence
> about the competition: every factual claim it contains about the competition is re-derived from an
> organiser source elsewhere in this repo (`knowledge/01`, `knowledge/04`, `knowledge/06`,
> `docs/irregularities.html`), and where this brief and the organiser's own pages disagree, the
> organiser's pages win and the disagreement is listed as an irregularity.

# The brief as received, 2026-10-06 (session 2, this checkout)

```text
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Co-training between a geophysical view and a surface view, with disagreement as the discovery signal. Blum and Mitchell (COLT '98, pp. 92-100, doi:10.1145/279943.279962) show that when each example has two views, each sufficient and approximately conditionally independent given the class, two learners trained on separate views can use each other's confident predictions on unlabeled data. View A is potential-field and subsurface (gravity, magnetics, strain, seismicity). View B is surface (DEM-derived curvature and slope, plus any radiometric bands present in training_features.tif). Test the independence assumption empirically: correlate each view's spatial-block out-of-fold errors on labeled negatives, and abandon the method if they are strongly correlated. Pseudo-label only where one view is confident and the other abstains, using whole-segment spatial blocks and a buffer so no leakage reaches the evaluation. The discovery signal is disagreement. Where A is confident and B is not, the fault may be buried beneath cover. Where B is confident and A is not, suspect surface artifacts such as roads or erosion lines. Because Phase 2 reviewers verify faults, write the geological reasoning for every A-only candidate. Co-training can also amplify bias, so compare against a single-view baseline on hide-and-recover segments. Normalize to [0,1], write the GeoTIFF, apply the repo's metric-aware placement, run the uniqueness gate, and confirm the output isn't merely the union of the two views.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.
[... the session's list of forty-odd GEMSDOE sibling sites with their owner-reported scores, the
leaderboard snapshot, the data/links block, and the standing rules about verification, official
sources, three passes and a final PR + merge into main -- all reproduced in the session log. The
operative requirements are itemised below because that is what the repository is accountable to. ...]

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:
https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html  h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778
Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Before implementing, generate 3-5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot - do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

0.3195 is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and have an up to date current feed.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form: "Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.

The single remaining blocker to training is data placement: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` - after that the full train->inference->validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

Run this task through multiple passes.
Pass 1: Implement the task completely and verify the result.
Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.
Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.
Do not stop after the first pass. Each pass must build on the previous pass. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.
```

## Why the block above is abridged in the middle, on purpose

The session's message also carried forty-odd sibling-site lines, a leaderboard snapshot, a Dropbox
link list and three repetitions of the standing verification rules.  They are omitted here rather than
retyped, because retyping them from memory is exactly the failure this repository's register exists to
catch; the requirements they express are enumerated below, and the *data* they point at is recorded
with pins in `registry/data_manifest.json`.

## The directives of this brief, itemised (the standing starting point)

1. **Ship a unique, downloadable `.tif`** — not a copy of any prior submission, named uniquely, with a
   short note for the submission form; the download must be at the very top of the site.
2. **Re-read the whole prompt before working**; the brief lives in the README so the next session
   starts from it.
3. **Blum & Mitchell co-training**, two views, disagreement as the discovery signal
   (doi:10.1145/279943.279962); A-only ⇒ buried beneath cover; B-only ⇒ suspect (roads, erosion).
4. **Test the independence premise** on spatially-blocked out-of-fold errors, and abandon the
   mechanism if it fails.
5. **Pseudo-label only across the confident/abstaining boundary, in whole-segment blocks with a
   buffer**, and write the geological reasoning for every A-only candidate.
6. **Compare against a single-view baseline on hide-and-recover**, because co-training can amplify bias.
7. **Normalise to [0, 1]**, apply the metric-aware placement, pass the uniqueness gate, and show the
   output is not merely the union of the two views.
8. **Explain why 0.2778 scored what it did**, and design something that can beat it — including the
   current board leader (the message says 0.3195; the board read this session says 0.3774, and that
   disagreement is logged as `IR-52-020`).
9. **Propose 3–5 new geological hypotheses**, each with layers, physical signature, why it finds
   catalogue-missing faults, and how it differs from what this repo already did; rank by expected DTI
   gain over implementation cost; validate the top one on the blocked holdout **before** spending a
   submission slot; for any idea needing new external data, name the free official source and confirm
   it is obtainable.
10. **The site**: clean, user-friendly, one obvious download, an executive-summary subpage with the
    exact submission steps, the `[0, 1]` error explained, official links for manual review, a live
    feed so nothing needs manual checking, and irregularities flagged.
11. **Three passes**, then a **pull request merged into `main`**, plus a list of what remains.
