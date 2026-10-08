# Generative-AI use disclosure for the H55 research release

Date: 2026-10-07 UTC. This disclosure is intended for the competition submission narrative if this research candidate is ever promoted. The current H55 artifact is unscored, was not uploaded, and failed its preregistered local promotion gate; this note does not imply competition acceptance.

## Extent and manner

Generative AI was used as a research and software-development assistant to inspect the repository, summarize source material, rank and preregister hypotheses, draft/modify Python code and tests, review the validation protocol, and prepare documentation. The exact H55 hypothesis, equations, parameter values, holdout gate, interpretation caveats, source URLs, and release note are recorded in `knowledge/14_h55_edge_hypotheses_preregistered.md` and `registry/h55_edge_preregistration.json` before feature implementation.

The software then executed all listed data restoration checks, feature calculations, model fits, blocked-fold predictions, negative-error correlations, pseudo-label diagnostics, distance-weighted Tversky calculations, placement, and GeoTIFF read-back checks. Those numerical outputs are reproducible receipts under `evidence/h55_edge_holdout.json`, `evidence/h55_edge_independence.json`, `evidence/h55_edge_pseudo_exchange.json`, and `evidence/h55_edge_submission.json`. The scripts did not use hidden labels, portal scores as training targets, or prior-submission pixel values as model features or targets. Prior rasters were used only in the separate decoded-output uniqueness audit.

No generative model supplied geological labels, field observations, or confirmed fault locations. The written geological explanations are hypotheses generated from measured input channels and relative model scores; they are not expert certification or proof of faults, geothermal systems, or vents. A human/domain expert should independently review any pixel before geological interpretation or deployment.

## Known data and validation limits

- The 23 core input files were restored from an owner-side mirror and match its pinned hashes. The organizer's original bytes were not independently authenticated in this sandbox.
- The competition's mapped-fault labels can be incomplete or inaccurate; catalogue-zero cells are therefore proxy negatives, not proven absence.
- Four spatial folds test recovery of withheld known-catalogue components, not the hidden/new-fault leaderboard labels. No official score or win probability is claimed.
- One-run weak negative-error correlation is not proof that the two views satisfy co-training's conditional-independence assumptions.
- No new external GDR derivative was obtained or used; the candidate's full eligible feature stack contains no radiometric band.
- The current H55 edge hypothesis did not beat the frozen strongest baseline by the required +0.005 mean DTI and at least 3/4 folds; no competition slot was used.
