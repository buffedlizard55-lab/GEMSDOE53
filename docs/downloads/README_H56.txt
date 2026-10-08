Historical H56 core-continuation artifact — superseded by the current H56 co-training synthetic demo.
gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif
short link: h56-candidate.tif (byte-identical alias for this historical artifact; not the current H56 TIFF)
Current H56: gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif (synthetic methodology demo; not approved for upload)
sha256 1308083dcf09b4c6fb656589ce79b3c392f5a0dd315e2ed31c8d36a47fc1d52d
bytes 153815

RESEARCH / AUDIT ONLY — NOT APPROVED FOR UPLOAD. DO NOT SPEND A WEEKLY SLOT.

- The local format gate passes: one float32 band, 3730x3292, EPSG:32611, finite {0,1} values.
- Decoded-pattern audit: no exact match among 33 accessible aligned prior rasters. This is bounded
  to those files, not proof against private or unlinked submissions.
- Only 12,941 of 40,517 emitted cells (31.9%) lie outside the 33-prior support union. The 25,517-cell
  core deliberately overlaps prior patterns. Although the selected continuation/scarp arm is 15,000
  cells, 2,059 arm cells have checked-prior support. A pixel-level overlap list is not preserved.
- The full-file >=3-pixel nearest-neighbour diagnostic FAILs: minimum is 2.828 px inside the fixed
  core. The selected arm is at least 3.162 px from other emitted cells. Do not summarize this as an
  all-file spacing pass.
- No comparable spatially blocked H56 holdout is recorded; the hypothesis slate is retrospective.
  Local format and decoded-pattern checks are not holdout validation. The slot decision is CLOSED.
- Score-to-filename associations are not organizer-authenticated. The 0.308 mean and 0.83/0.37
  probabilities are conditional arithmetic, not a measured score or forecast. The projection applies
  a density prior to all 15,000 selected arm cells despite the support overlap above.
- No H56 per-pixel A-only dossier is reproducible from this checkout; do not substitute another
  candidate's CSV. See the scope receipt below.

Audit receipts (from this repository):
- ../data/h56_slot_gate_review_2026-10-07.json
- ../data/gems52-h56-verify.json
- ../data/h56_a_only_reasoning_scope_2026-10-07.json

Submission name retained for possible later review: GEMSDOE52-H56-ConsensusCore-Continuation-40517px
Identifying note retained for possible later review (157 chars; do not paste in portal now):
H56 consensus core + continuation | 25,517 prior-overlap core px + 15,000 selected arm px |
decoded pattern differs from 33 accessible priors; research only.

The TIFF and ZIP aliases are byte-identical copies of the canonical H56 files; aliases do not
change the prediction or establish uniqueness. No portal upload or acceptance is claimed.
