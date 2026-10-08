# GEMSDOE52

Target: a **unique, downloadable single-band GeoTIFF** for [DrivenData competition 306 — DOE GEMS
Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/), built to beat this group's
best of 0.2778, with the reasoning and the evidence published next to the file.

## The file — download it, submit it, nothing to configure

| | |
|---|---|
| **download** | [`docs/downloads/gems52-h53-coincidence-gated-singles-37654px-r1.tif`](docs/downloads/gems52-h53-coincidence-gated-singles-37654px-r1.tif) — click, save, upload |
| also as a zip | [`docs/downloads/gems52-h53-coincidence-gated-singles-37654px-r1.zip`](docs/downloads/gems52-h53-coincidence-gated-singles-37654px-r1.zip) (the same bytes, verified inside the archive) |
| in the repo too | [`submission/gems52-h53-coincidence-gated-singles-37654px-r1.tif`](submission/gems52-h53-coincidence-gated-singles-37654px-r1.tif) |
| bytes / shape | 147,575 · 3730 × 3292 · single band · `float32` · EPSG:32611 · 100 m cells · 256 × 256 tiles |
| values | {0, 1} only — **37,654 positive px, every one of them a separated single pixel** (3 px minimum separation), 0 outside the valid footprint, **no NaN** |
| sha256 | `9ffe11b2b56a2cb43e7da5ce3613a626b1a5503dc72e91cee694376d15f4420f` |
| **submission name** | `gems52-h53-coincidence-gated-singles-37654px-r1` |
| **notes-box text** (180 chars, ≤200 by assert) | *H53-1: surface lineaments kept only where an independent geophysical family agrees on strike in the same 1.6 km tile (permutation-calibrated, top 10%); 37,654 spaced single pixels.* |
| format gate | `ok: true` (`src/gems52/gates.py`, read off the written bytes: same grid, bounds, CRS, dtype, value range as `sample_submission.tif`, no NaN) |
| uniqueness gate | `ok: true` — 8 priors checked, **84.6 %** of the mass sits where no prior of this family put anything, and 655,900 prior pixels are deliberately **not** re-emitted |
| not merely the union | 31,932 of the 37,654 pixels are ones the ungated union would not have chosen at the same budget (Jaccard vs that union 0.082) |
| holdout verdict | **`promoted: true`** — fold-mean DTI on *both* blocked instruments above every comparator, and identical comparator ordering in both (tip 0.0387 vs 0.0320 previous best; hide 0.0661 vs 0.0518) |
| selection | `evidence/h53_holdout.json` + `evidence/dicoincidence.json` — the coincidence gate is `coincidence_table()` (100 family-disjoint pair tests, 400 circular-roll permutations each) and the gate is the pair-relative top-decile agreement per 1.6 km tile |
| exact steps | [`docs/executive-summary.html`](docs/executive-summary.html) |
| rebuild it | `PYTHONPATH=src python3 scripts/h53_detect.py --stage tiles && PYTHONPATH=src python3 scripts/h53_detect.py --stage stats && PYTHONPATH=src python3 scripts/build_h53_submission.py` |

**Why this file and not r1:** r1 cleared the control bar but failed the pre-registered
"+0.010 over the naive union" bar on the truncation instrument, so it shipped flagged `promoted: false,
forced: true`. H53-1 was built, gated and promoted *before* this file was written, and the builder refuses
to write a file when the holdout verdict is not promoted (`scripts/build_h53_submission.py`; `--force`
records itself in the audit). The weekly slot is therefore spent on an arm that beat the previous holdout
best on both instruments, which is the standing rule.

The site is the product: [docs/index.html](docs/index.html) renders every number from
`docs/data/*.json`, which `scripts/refresh_feed.py` regenerates and a committed GitHub Actions workflow
refreshes on a schedule, so **nothing on the page needs hand-checking**.

**Core values this repo is run by — _Maximize P(Win)_, _Own the Outcome_.** Maximize P(Win): every
decision is taken on the number the organiser scores, at the prevalence their published scores imply, and no
weekly slot goes to an idea that has not beaten the current holdout best. Own the Outcome: the file, its
hash, its gates, its provenance, its negative results and its irregularities are all in this repo — including
the bug our own writer shipped tonight and the gate caught (IR-52-007), and the mechanism from the brief that
failed its own test (§4).

---

## 1. The standing brief

The instruction set this repo is built against is recorded in
[`knowledge/00_brief_as_received.md`](knowledge/00_brief_as_received.md) — every directive, in order,
each one traceable to code or evidence here. Its integrity note matters: the *verbatim* wording of the
original message is not recoverable from this workspace (single commit `744df63`, no brief file
anywhere on disk), so the brief is restated faithfully rather than quoted, and that is flagged on the
site's [irregularities page](docs/irregularities.html) instead of being papered over with invented
quotation marks.

In one paragraph: treat the task as **co-training** across two views — View A the geophysical
potential fields, View B the surface/geomorphic layers — and take the discovery signal from their
**disagreement**, not their agreement, grounding it in [Blum & Mitchell, *Combining labeled and
unlabeled data with co-training*, COLT '98, doi:10.1145/279943.279962](https://doi.org/10.1145/279943.279962);
**test the theorem's premise** (conditional independence of the views' errors given the label)
empirically on spatially-blocked out-of-fold errors, and drop the arm if the test fails; pseudo-label
only where one view is confident and the other withholds; hold out **whole segments with a buffer**;
read **A-only as a fault buried under cover** and write that reasoning out for **every candidate**,
and **B-only as suspect** (roads, erosion, levees); compare against a **single-view baseline on
hide-and-recover**; normalise to [0, 1], write a GeoTIFF, place mass so that it is **aware of the
metric's own kernel**, pass a **uniqueness gate**, and be **more than the union** of previous
submissions.

### 1.0 The brief, verbatim

Recovered intact: `README.md` §8 of commit `503f18e6` on `main` (the PR #2 session) records the original
task prompt as a fenced block, and that block is reproduced here unaltered — including the URLs, the
character counts and the sentence about radiometric bands, which is *conditional* ("any radiometric bands in
`training_features.tif`") and resolves to none, as `knowledge/04` and `docs/irregularities.html` explain.
This supersedes the reconstruction that stood here until 22:20 UTC tonight; the sibling session's copy is
not the Arena message itself, but it is a byte-for-byte record of it, so the wording is quoted rather than
paraphrased, and the provenance is stated rather than assumed.

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

### 1.1 The directives, itemised (the standing starting point, restated in the brief's own order)

The brief as received by this session is [`knowledge/07_brief_2026-10-06_session2.md`](knowledge/07_brief_2026-10-06_session2.md);
it carries **eleven** operative directives, and this list is that list — same order, same scope — so a
reviewer can diff prose against prose. (Earlier revisions of this README itemised ten, having folded the
re-read-the-prompt rule and the why-0.2778 rule into others; that folding is what let a session start from a
summary instead of from the brief, so it is undone.)

1. **Ship a unique, downloadable `.tif`** — not a copy of any prior submission; a unique name and a short
   note for the submission form; the download obvious at the very top of the site.
2. **Re-read the whole prompt before working** — the brief lives in this repository, and this file is where a
   session starts.
3. **Co-train two views of the same unlabelled pixels** — View A the potential fields and subsurface
   (gravity, magnetics, strain, seismicity), View B the surface (slope, curvature, scarp; radiometry where it
   exists *outside* the official cube, per `IR-52-001`/`IR-52-011a`) — and treat **disagreement, not
   agreement, as the discovery signal** (Blum & Mitchell, COLT '98, doi:10.1145/279943.279962): A-only ⇒
   buried beneath cover, B-only ⇒ suspect (roads, erosion, levees).
4. **Test the independence premise instead of assuming it** — correlate each view's spatially-blocked
   out-of-fold errors on labelled negatives, and abandon the mechanism if it is strongly correlated.
5. **Pseudo-label only across the confident/abstaining boundary**, in whole-segment blocks with a buffer, and
   **write the geological reasoning** for every A-only candidate.
6. **Benchmark against a single-view baseline on hide-and-recover**, because co-training can amplify bias.
7. **Normalise to [0, 1]**, write the GeoTIFF on the competition grid, and place mass **metric-aware** (the
   300 m kernel, the pixel-exact mask, the acceptance bar), not by percentile.
8. **Pass the uniqueness gate and be more than the union of the views** — never re-emit a prior answer as the
   product; priors are for learning.
9. **Propose 3–5 new geological hypotheses** — layers, physical signature, why they catch
   catalogue-missing faults, diff against repo history — ranked by expected DTI gain over cost; **validate the
   top one on the spatially-blocked holdout before spending a weekly slot**; any idea that needs new external
   data must name a free, official source and confirm it is obtainable.
10. **The site** — clean GitHub Pages, one-click `.tif` at the very top, an executive-summary subpage with the
    exact submission steps, the `[0, 1]` validator error explained and made impossible, official links for
    manual review, a live feed so nothing needs hand-checking, irregularities flagged.
11. **Three passes** (implement → review/fix → re-check against the request), then a **pull request merged
    into `main`**, plus the list of what remains.

**Why 0.2778 scored what it did, and what the bar is** — the reasoning the brief asks for in the same breath
as the build: [`knowledge/01_why_02778_and_the_bar.md`](knowledge/01_why_02778_and_the_bar.md). Note the
disagreement it records: the brief quotes 0.3195 as the leader, the fetched board says 0.3774
(`IR-52-020`, `registry/leaderboard_snapshot_2026-10-06.json`).

## 2. Layout

```
src/gems52/     metric.py      literal official DTI, kernel, credit bar, max_cover  (tested)
                grid.py        pinned 3730x3292 / EPSG:32611 grid, GeoTIFF writer+re-read receipt
                transform.py   resample-any-grid-to-the-grid helper
                features.py    the 27 derived layers (19 View A, 8 View B)
                cotrain.py     uint8 rank stack, per-view logistic learners, co-training round,
                               the independence test, the disagreement strata
                emit.py        accept_bar + lazy-greedy metric-aware emission (gain > bar*(1-wmax))
                holdout.py     three validation instruments: hide / block / tip, catalogue-masked
                gates.py       format legality + uniqueness / not-merely-the-union audit
scripts/        prepare_data.py restore_data.py screen_layers.py run_pipeline.py
                validate_holdout.py build_submission.py refresh_feed.py research.sh
tests/          test_metric.py  (8 tests, including the marginal acceptance rule pixel-by-pixel)
knowledge/      00_brief 01_why_02778 02_hypotheses 03_negative_results 04_free_data_and_licenses
                05_instruments 06_provenance_and_irregularities  (written for the next session)
evidence/       grid, band inventory, layer screen, folds, independence, strata, holdout tables,
                per-submission gate reports
registry/       data_manifest.json (23 pinned inputs + sha256), preregistration.json (decision rules,
                written before any fold was scored)
docs/           the GitHub Pages site; docs/data/*.json is its only source of numbers
submission/     built rasters + LATEST.txt
```

## 3. Reproduce it

```bash
python3 scripts/restore_data.py                 # 23 pinned inputs -> data/, sha256-checked
python3 scripts/prepare_data.py                 # bands + labels + elevation -> work/derived/
python3 -m pytest -q                            # metric parity + lattice weights + emission rule
PYTHONPATH=src python3 scripts/run_pipeline.py --stage fit --rounds 1 --mode tip
PYTHONPATH=src python3 scripts/validate_holdout.py --mode tip --emit topk
PYTHONPATH=src python3 scripts/build_submission.py --mode tip --arm <winner> --emit greedy
PYTHONPATH=src python3 scripts/refresh_feed.py   # regenerate the site's data/*.json
```

`--mode` picks the instrument: `hide` (whole catalogue components removed), `block` (quadrant-blocked
as well), `tip` (only the along-strike ends of traces removed). Each writes its own
`evidence/*_<mode>.json`, so the two instruments' numbers cannot be confused with each other.
`bash scripts/research.sh tip hide` runs fit+validate for several modes in sequence.

## 4. What was actually found, before any of this was shipped

**H53-1 (this session): the discovery signal pays, but only after two of its own gates were repaired.**
Full write-up in [`knowledge/09_what_h53_found.md`](knowledge/09_what_h53_found.md); the numbers are in
`evidence/h53_holdout.json` and `evidence/dicoincidence.json`.

* **The brief's mechanism, implemented literally, produced a gate that could not fire.** The first version
  gated on a tile's *z-score* against the rolled null: one tile contributes one scalar, whose null s.d. is
  ≈ 0.3, so `|z| ≥ 3` demands a cosine of ≈ 0.9 and passes 0.0 % of tiles (measured). A gate that silently
  passes nothing looks exactly like a gate that passes nothing for physical reasons. Replaced with a
  **pair-relative percentile** (`agreement_percentile`, distribution-free), which is also the honest framing:
  the informative statement in a province with one dominant fabric is *"this tile agrees better than this
  pair's own tiles do"*, not *"these two datasets agree"* — that is the default here, and an earlier
  version of the arms that used the global gate counted 93 % of all candidate nodes as corroborated.
* **The gate, once it can fire, is what wins.** Fold-mean DTI at the same budget, same folds, same emitter:
  `B_corr + separation` **0.0387 tip / 0.0661 hide**, ungated union + separation 0.0357 / 0.0565, surface-only
  + separation 0.0289 / 0.0445, the same arm with its places rolled to another tile 0.0192 / 0.0369. Against
  the repo's previous best at this budget — tip `union_cor` 0.0320, hide `B_only` 0.0518 — that is
  **+21 % / +28 %**, with 3/4 and 4/4 fold support and the same comparator ordering on both instruments.
* **Separation, not density, is what the metric pays for.** The incumbent's own sweep is a ladder in
  spacing (2.24 px → 3.0 px → 3.0 px at 60,069 → 44,090 → 37,654 px) and its best file is 37,654 *single*
  pixels. So the emitter here is greedy top-`budget` under a **minimum separation**
  (`src/gems52/nodes.py::emit_nodes`): 37,654 pixels, all isolated, median nearest-neighbour distance 3.0 px
  — the same geometry the top of the ladder uses, filled with ranked evidence instead of a lattice.
* **What did not work, and is published rather than buried:** gating on *global* coincidence
  (37/100 pairs clear a Bonferroni z gate, so the gate stops discriminating); a per-tile z (above); and the
  gated arms without separation, which lose to the ungated union on both instruments. The eight-row arm table
  with all four controls is in `evidence/h53_holdout.json`.

* **The co-training mechanism failed its own gate.** One Blum–Mitchell round *lowered* View A's
  blocked AUC (mean Δ = −0.0159, fold support 1/4 on `hide`; 0.797 → 0.761 pooled earlier in the run), and its
  arm is the worst measured on both instruments — 0.0084 tip / 0.0078 hide against 0.0253 / 0.0396 for
  matched-budget `random` — so the pseudo-label round is **not** in the shipped field, and the failure is
  published (`evidence/holdout_*.json`, `docs/validation.html`). The premise is a subtler story, and we
  corrected our own earlier sentence about it: the pre-registered block-level test **could not fire** at this
  grid size (degenerate per-block false-alarm variance ⇒ correlation undefined, `spearman` 1.0 on all ties),
  the pixel-level logit correlation is weak (+0.1748 tip, +0.1316 hide against a 0.60 abandonment threshold),
  and the block-level *miss-rate* correlation on `hide` is **+0.8307** — the views miss the same
  neighbourhoods. So conditional independence here is **neither established nor refuted: it is unmeasured at
  the granularity the pre-registration specified**, and the r = 0.4298 / −0.1406 numbers this README carried
  at 22:20 UTC are **retracted**; `knowledge/03` §N-1 has the full table and the rule it taught us. The disagreement **strata** — the
  physical asymmetry between "field says fault, surface says nothing" and its converse — are, because
  they were measured separately and survived: A-only pixels sit in materially deeper cover than
  concordant pixels (mean depth-to-basement rank 455 vs 251) and carry a gravity step (6.06 vs the
  artefact class's 2.59), which is the signature a buried range-front fault has and a road cut
  does not.
* **The instrument had to be rebuilt to see the thing we were claiming.** Removing whole catalogue
  components makes a fold that is *structurally blind* to near-trace mass: only 0.5 % of a hidden
  component's pixels lie within 5 px of a still-visible trace, because a trace's neighbours belong to
  the same component. Yet the organiser's own clarification is that new-fault truth can lie within
  300 m of a known trace, and that mapping-truncation corrections are part of what the competition is
  for. So the `tip` instrument was added, where 88.5 % of the held-out truth *is* reachable from a
  visible trace. Numbers from the two instruments are never pooled.
* **Ranking a smooth field by global percentile loses to random emission.** At 37,654 px the top of
  an uncentred field is one big anomaly high, not the next fault. The fix is to apply every ranking
  *inside a permitted region* — footprint minus catalogue, and for corridor mass inside the 1–6 px
  corridor — which is what the arm table does; the naive global-percentile arms are reported alongside it
  so the comparison is auditable rather than asserted. The instruments, and the selection rule that follows
  from them, are written up in `knowledge/05_instruments_and_what_each_can_see.md`.
* **0.2778 is a placement result, not a discovery result.** Removing 2,545 pixels of self-overlap with
  the mask (6.3 % of the mass) raised that submission's DTI by 2.6 %. See
  [`knowledge/01_why_02778_and_the_bar.md`](knowledge/01_why_02778_and_the_bar.md) for the algebra, the
  perfect-precision counterfactual (0.464 at the same budget), and the acceptance-bar table that shows
  the marginal rule across the entire live leaderboard is the same sentence: *emit a pixel iff it is
  within 224 m of a fault pixel the catalogue does not already have*.

### 1.2 Prior submissions of this family that this file must not be

`GEMSDOE52-CoTrain-Disagree-H52-1` (PR #2, 41,200 px, `c7e980f4…`), the r1 composite this session's
predecessor built (`gems52-h52-cotrain-disagreement-emission-composite-37654px-r1.tif`, 89,751 B,
`063fb724…`, `promoted: false`, `forced: true`), and the rasters in `data/scored/` (gems19, gems24) are
this group's own priors. The uniqueness gate compares against every one of them: this file puts **84.6 %**
of its 37,654 pixels where no prior ever reached, drops 655,900 prior pixels rather than re-emitting them,
and its 31,932-pixel difference from the ungated union at the same budget is the measured statement that it
is not a union either. r1 stays published — its evidence, its hash, its retraction of the co-training round
— because the point of the register is that the failures are as legible as the file.

## 5. Irregularities, stated plainly

The live public leaderboard's #1 is **0.3774**, not the 0.3195 stated in the session's opening
context (`IR-52-002` / `IR-52-020` — the same disagreement under the brief's own item number, now entered in
`knowledge/06` and on the register page rather than only referenced); the group's own 0.2778 currently sits at **#13 of 24 visible rows** (read twice this session, 21:2x
and 21:33 UTC, identical both times). Every file→score
mapping in this family (including the 0.2778 one) is **owner-reported**, not organiser-authenticated —
the board exposes no filename, hash or upload receipt, and GEMSDOE47 formally retracted its alleged
mapping. Full list: [`docs/irregularities.html`](docs/irregularities.html) and
[`knowledge/06_provenance_and_irregularities.md`](knowledge/06_provenance_and_irregularities.md).

Licences: all pinned inputs are the competition's own bundles or USGS/GDR open data; the sibling-derived
external CSVs in `data/external/` are **derived, not organiser-authenticated** and are used only as
optional corroboration, never as positive labels. See
[`knowledge/04_free_data_and_licenses.md`](knowledge/04_free_data_and_licenses.md).

## 6. No manual steps

`docs/data/*.json` is regenerated from `evidence/` by `scripts/refresh_feed.py`;
`.github/workflows/feed.yml` runs it nightly and on push, and the site renders only from those files.
If a number on the site is wrong, the fix is the evidence file, never the HTML.
