#!/usr/bin/env python3
"""Publish an explicitly research-only H55 record and one-click links from audited receipts."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def publish() -> None:
    receipt = json.loads((EV / "submission_h55.json").read_text())
    holdout = json.loads((EV / "h55_profile_holdout.json").read_text())
    name = receipt["file"]
    if not name.startswith("gems52-h55-profile-") or not name.endswith("-research.tif"):
        raise ValueError("H55 receipt points to an unexpected TIFF")
    tif = DOCS / "downloads" / name
    if not tif.is_file() or receipt["sha256"] != __import__("hashlib").sha256(tif.read_bytes()).hexdigest():
        raise ValueError("H55 published TIFF is absent or differs from audited receipt")
    gate = receipt["validation"]
    scores = [f["arms"] for f in holdout["folds"]]
    primary = [r["structural_contrast_h55"]["dti"] for r in scores]
    surface = [r["view_B_h55"]["dti"] for r in scores]
    base_surface = [r["view_B"]["dti"] for r in scores]
    uniqueness = receipt["uniqueness"]
    summary = {
        "file": name,
        "name": receipt["submission_name"],
        "note": receipt["note"],
        "sha256": receipt["sha256"],
        "bytes": receipt["bytes"],
        "format_ok": receipt["format"]["ok"],
        "format": {k: receipt["format"][k] for k in ("bands", "dtype", "crs", "width", "height", "transform", "min", "max", "nan_pixels", "n_nonzero")},
        "research_only": True,
        "weekly_slot_approved": False,
        "holdout": {
            "folds": len(primary),
            "baseline_surface_dti": base_surface,
            "surface_plus_profile_dti": surface,
            "structural_profile_dti": primary,
            "mean_profile_dti": sum(primary) / len(primary),
            "mean_best_comparable_baseline_dti": holdout["means"][gate["best_comparable_baseline"]],
            "best_comparable_baseline": gate["best_comparable_baseline"],
            "mean_lift": gate["mean_dti_lift"],
            "positive_folds": gate["positive_folds"],
            "approved_for_slot": gate["approved_for_slot"],
            "reason": gate["reason"],
        },
        "uniqueness": {k: uniqueness[k] for k in ("n_priors_checked", "canonical_pattern_unique", "equals_literal_prior_union", "research_publication_ok", "support_novelty_gate_ok", "novel_vs_all_priors", "novel_fraction", "prior_px_dropped", "relation_to_union", "scope")},
        "view_comparison": receipt["view_comparison"],
        "a_only_emitted_pixels_with_reasoning": receipt["a_only_reasoning"]["rows"],
        "official_score": None,
        "organizer_upload_acceptance": None,
    }
    (DOCS / "data/h55_profile.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    (DOCS / "data/h55_profile_holdout.json").write_text(json.dumps(holdout, indent=2, allow_nan=False) + "\n")

    index = DOCS / "index.html"
    text = index.read_text()
    card = f'''<section class="card" id="h55-profile-followup"><h2>H55-PROFILE follow-up — research only, not promoted</h2><p>The five-scale paired-normal DEM profile candidate is a separate experiment. Its frozen spatial holdout failed the required mean-lift gate (+0.002300 vs +0.005); it does not replace the main H55 download or <code>submission/LATEST.txt</code>.</p><p><a class="button" href="downloads/{name}" download>Download H55-PROFILE research TIFF</a> <a href="downloads/{name[:-4]}.zip" download>single-TIFF ZIP</a> · <a href="h55-profile.html">Full follow-up audit</a></p></section>'''
    marker_start, marker_end = "<!--H55PROFILE-->", "<!--/H55PROFILE-->"
    if marker_start in text and marker_end in text:
        i, j = text.index(marker_start), text.index(marker_end) + len(marker_end)
        text = text[:i] + marker_start + card + marker_end + text[j:]
    elif "<!--/H55BAR-->" in text:
        i = text.index("<!--/H55BAR-->") + len("<!--/H55BAR-->")
        text = text[:i] + marker_start + card + marker_end + text[i:]
    else:
        text = text.replace('<main id="main">', '<main id="main">' + marker_start + card + marker_end, 1)
    index.write_text(text)

    detail = f'''<div class="eyebrow">H55 · pre-registered surface-profile experiment</div>
<h1>Candidate file, not a contest recommendation.</h1>
<div class="status"><strong>Do not upload this candidate.</strong>It is a unique, format-checked research artifact; the frozen spatial holdout failed its promotion gate. No organizer score or portal acceptance is known, and no weekly slot was used.</div>
<p><a class="button" href="downloads/{name}" download>↓ Download the unique .TIF</a> <a class="button" href="downloads/{name[:-4]}.zip" download>↓ Download single-TIFF .ZIP</a></p>
<div class="card"><h2>Portal identifiers (for audit only)</h2><p>Unique file name: <code>{receipt['submission_name']}</code></p><p>Optional note ({len(receipt['note'])} characters): <code>{receipt['note']}</code></p><p>SHA-256: <code>{receipt['sha256']}</code></p><p>These identifiers make this artifact distinguishable. They do not imply slot approval.</p></div>
<h2>Pass/fail decision</h2>
<p>Primary H55 structural model mean local DTI: <strong>{sum(primary)/len(primary):.6f}</strong>. Best comparable baseline was <strong>{gate['best_comparable_baseline']}</strong> at <strong>{holdout['means'][gate['best_comparable_baseline']]:.6f}</strong>. Paired mean lift: <strong>{gate['mean_dti_lift']:+.6f}</strong>; positive folds: <strong>{gate['positive_folds']}/4</strong>. Frozen requirements were ≥+0.005 mean lift and ≥3/4 positive folds. Fold support passed (3/4); the required mean lift failed, so slot approval remains false. Fold scores use catalogue recovery proxies, not hidden competition truth, and the holdout's relation to organizer score is not established.</p>
<div class="table-wrap"><table><thead><tr><th>Spatial fold</th><th>Surface baseline</th><th>Surface + profile features</th><th>Structural baseline</th><th>Structural + profile (primary)</th></tr></thead><tbody>{''.join(f'<tr><td>{i}</td><td>{s0:.6f}</td><td>{s1:.6f}</td><td>{r["structural_contrast"]["dti"]:.6f}</td><td>{p:.6f}</td></tr>' for i,(s0,s1,r,p) in enumerate(zip(base_surface,surface,scores,primary)))}<tr><td><strong>Mean</strong></td><td><strong>{sum(base_surface)/4:.6f}</strong></td><td><strong>{sum(surface)/4:.6f}</strong></td><td><strong>{holdout['means']['structural_contrast']:.6f}</strong></td><td><strong>{sum(primary)/4:.6f}</strong></td></tr></tbody></table></div>
<h2>What the new transform tests</h2><p>Band 12 detrended elevation is smoothed and its local gradient defines a normal. The code samples bilateral elevations at 100, 200, 300, 400 and 600 m, subtracts a local first-order plane, records signed step, paired flank contrast/asymmetry, and tangent persistence. It is deliberately compared with both the original surface-only model and the structural baseline at equal emitted budgets. It does not prove a fault; roads, gullies, lithologic contacts and DEM artifacts remain plausible alternatives.</p><p><strong>Scope:</strong> H55 is a supervised structural-contrast model, not co-training. The repository separately tested view-error correlation on held-out catalogue-zero proxy negatives and ran a buffered one-round exchange experiment; that separate experiment did not promote over the surface-only baseline and its pseudo-labels are not used here. Weak error correlation is not proof that the theorem's stronger view assumptions hold.</p>
<h2>Output and uniqueness audit</h2><p>Single-band float32 GeoTIFF, 3292 × 3730, EPSG:32611, exact sample transform, all raw values finite in [0,1], {receipt['format']['n_nonzero']:,} positive cells, internal footprint mask, no positive mass outside the valid support. Local checks are not an organizer's upload-acceptance guarantee.</p><p>Decoded-pattern uniqueness passed against <strong>{uniqueness['n_priors_checked']} accessible aligned TIFF priors</strong>: {uniqueness['novel_fraction']:.1%} of emitted support was absent from their binary / ≥0.5 support union, and {uniqueness['prior_px_dropped']:,} pixels in that union were omitted. The model output is not the union of View A and View B ({receipt['view_comparison']['not_merely_union']}). This is a bounded repository inventory: assets inaccessible from this checkout, private competition submissions and every historical website file have not all been exhaustively authenticated or compared. It cannot support an absolute global-uniqueness claim.</p>
<p><strong>A-only emitted pixels with individual geological reasoning:</strong> {receipt['a_only_reasoning']['rows']:,}. <a href="downloads/{name[:-4]}-candidates.csv">Download per-pixel reasoning CSV</a> · <a href="downloads/{name[:-4]}-audit.json">Full TIFF and uniqueness receipt</a> · <a href="data/h55_profile.json">Compact machine-readable summary</a> · <a href="data/h55_profile_holdout.json">Holdout fold evidence</a>.</p>
<h2>Why the team-reported 0.2778 occurred — and limits of that inference</h2><p>The team's restored reference raster `h33-2-b2` has 37,654 positive pixels. Repository byte analysis reports it as a subset of the 0.2600 d2-8 pattern after deleting a 6,436-pixel set entirely inside the empirically zero-credit 200 m catalogue ring. Under the competition's stated distance-weighted Tversky objective, removing pixels that earn no true-positive credit but incur false-positive cost is a physically plausible reason for the improvement to the owner-reported 0.2778. This explains a measurable mechanism, not hidden-label correctness or score attribution: the historical score/file mapping is owner-reported, and the score is not independently authenticated. The leaderboard snapshot dated 2026-10-06 listed a leader at 0.3774 and the 0.3195 entry at rank 7, so 0.3195 was already stale as a highest-live-score claim at that timestamp.</p>
<h2>Registered hypotheses and next tests</h2><p>The full pre-registration lists four candidates, layer names, mechanisms, repo-level novelty and cost. H55-PROFILE is the only one implemented in this turn; H55-JUNCTION and H55-STRAIN use supplied bands but remain untested. H55-SEISMIC requires official USGS ComCat event bytes: a sandbox request to the official FDSN endpoint failed TLS before receiving a response. It is deferred, not treated as viable or used in this TIFF.</p><p><a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/12_hypotheses_H55_preregistered.md">Full ranked hypotheses and protocol</a> · <a href="data/h55_profile_holdout.json">Raw holdout receipt</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official scoring definition</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official leaderboard</a> · <a href="https://earthquake.usgs.gov/fdsnws/event/1/">USGS ComCat FDSN</a> · <a href="https://gdr.openei.org/submissions/1391">DOE GDR INGENIOUS</a> · <a href="https://www.usgs.gov/the-national-map-data-delivery/gis-data-download">USGS 3DEP download</a>.</p>'''
    page = DOCS / "h55-profile.html"
    nav = '<a href="index.html">Overview</a><a href="executive-summary.html">Submission guide</a><a href="validation.html">Validation</a><a href="h55-profile.html">H55-PROFILE follow-up</a><a href="forensics.html">0.2778 autopsy</a><a href="sources.html">Sources</a>'
    page.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="H55 paired-normal profile: unique GeoTIFF, frozen spatial holdout failure, and auditable geoscience evidence."><title>H55 research candidate · GEMSDOE52</title><link rel="stylesheet" href="style.css"></head><body><a class="skip" href="#main">Skip to evidence</a><header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{nav}</nav></header><main id="main">{detail}</main><footer>Fault-map research proposal, not a verified fault or geothermal vent. <a href="irregularities.html">Limitations &amp; review</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a></footer></body></html>''')

    downloads = DOCS / "downloads/index.html"
    existing = downloads.read_text() if downloads.exists() else ""
    latest = (ROOT / "submission/LATEST.txt").read_text().strip()
    incumbent = f'<p id="main-h55-download"><strong>Main H55 candidate (unchanged):</strong> <a href="{latest}" download>Download incumbent TIFF</a> · <a href="{latest[:-4]}.zip" download>single-TIFF ZIP</a> · <a href="../h55.html">incumbent evidence</a></p>'
    h55_link = f'<p id="h55-profile-downloads"><strong>H55-PROFILE follow-up — research only, NOT promoted:</strong> <a href="{name}" download>Download TIFF</a> · <a href="{name[:-4]}.zip" download>single-TIFF ZIP</a> · <a href="{name[:-4]}-audit.json">audit</a> · <a href="{name[:-4]}-candidates.csv">A-only reasoning CSV</a> · <a href="../h55-profile.html">experiment page</a></p>'
    for marker, paragraph in (("main-h55-download", incumbent), ("h55-profile-downloads", h55_link)):
        pattern = rf'<p[^>]*id="{marker}"[^>]*>.*?</p>'
        if re.search(pattern, existing, flags=re.S):
            existing = re.sub(pattern, lambda _: paragraph, existing, flags=re.S)
        else:
            existing = existing.replace("<h1>Research downloads</h1>", "<h1>Research downloads</h1>" + paragraph, 1)
    main_match = re.search(r'<p[^>]*id="main-h55-download"[^>]*>.*?</p>', existing, flags=re.S)
    profile_match = re.search(r'<p[^>]*id="h55-profile-downloads"[^>]*>.*?</p>', existing, flags=re.S)
    if main_match and profile_match:
        existing = re.sub(r'<p[^>]*id="(?:main-h55-download|h55-profile-downloads)"[^>]*>.*?</p>', "", existing, flags=re.S)
        existing = existing.replace("<h1>Research downloads</h1>", "<h1>Research downloads</h1>" + main_match.group(0) + profile_match.group(0), 1)
    downloads.write_text(existing)

    readme_path = ROOT / "README.md"
    readme = readme_path.read_text()
    readme_block = f'''<!--H55PROFILEREADME-->
## H55-PROFILE follow-up — generated, but not promoted

**[Download the unique H55-PROFILE research TIFF](docs/downloads/{name})** · [single-TIFF ZIP](docs/downloads/{name[:-4]}.zip) · [experiment page](docs/h55-profile.html). This follow-up does **not** replace the main H55 candidate or change `submission/LATEST.txt`.

- Unique identifier: `{receipt['submission_name']}`; optional portal note ({len(receipt['note'])} chars): `{receipt['note']}`
- Local format/range/geometry and decoded-pattern uniqueness checks passed against {uniqueness['n_priors_checked']} accessible aligned priors. Bounded audit only; not proof against private/unlinked site assets.
- **Do not submit:** holdout mean lift {gate['mean_dti_lift']:+.6f}, {gate['positive_folds']}/4 folds positive; pre-registered +0.005 lift threshold failed. No official score/upload acceptance and no weekly slot used. The main H55 file and `submission/LATEST.txt` remain unchanged.
- Inputs were SHA-pinned owner mirrors, not organizer-authenticated. No external raster or ComCat data entered this model.
- [Preregistered hypotheses](knowledge/12_hypotheses_H55_preregistered.md) · [holdout](evidence/h55_profile_holdout.json) · [TIFF/uniqueness receipt](evidence/submission_h55.json) · [3-pass review](evidence/h55_review_receipt.json).

**Next-session start:** read this README and the full current task prompt below; the H55 candidate failed its promotion gate. A download link is not approval to spend a contest slot.
<!--/H55PROFILEREADME-->'''
    if "<!--H55PROFILEREADME-->" in readme and "<!--/H55PROFILEREADME-->" in readme:
        readme = re.sub(r"<!--H55PROFILEREADME-->.*?<!--/H55PROFILEREADME-->",
                        lambda _: readme_block, readme, count=1, flags=re.S)
    elif "## Historical H54 candidate" in readme:
        readme = readme.replace("## Historical H54 candidate", readme_block + "\n\n## Historical H54 candidate", 1)
    else:
        readme = readme.replace("# GEMSDOE52", "# GEMSDOE52\n\n" + readme_block, 1)
    readme_path.write_text(readme)


def main() -> None:
    publish()
    print("Published H55-PROFILE follow-up page and byte-checked research download; incumbent preserved")


if __name__ == "__main__":
    main()
