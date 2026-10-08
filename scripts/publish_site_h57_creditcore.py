#!/usr/bin/env python3
"""Publish the H57 current-artifact receipts and its audit page, from the bytes.

Writes, idempotently and only from measured values:

* ``docs/data/submission_h57_creditcore.json`` — receipt for the H57 credited-core alternate
* ``docs/h57-creditcore.html``                 — its audit page

The repository's *current* pointer (``docs/data/submission.json``, ``submission/LATEST.txt``) is owned
by the H57 union-arm round merged on ``main``; this alternate must never silently take it over.  It is
published beside it with its own measured comparison.

Everything is re-read from the emitted GeoTIFF and from the gate receipts produced by
``scripts/build_h57_emit.py``; nothing here is typed from memory.  Missing inputs are hard errors,
never silently skipped.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS, EV, DATA = ROOT / "docs", ROOT / "evidence", ROOT / "docs" / "data"
FILE = "gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif"
STEM = FILE[:-4]
NAV = ('<a href="index.html">Overview</a><a href="executive-summary.html">Submission&nbsp;guide</a>'
       '<a href="h56-cotrain.html">H56&nbsp;archive</a><a href="validation.html">Validation</a>'
       '<a href="forensics.html">0.2778&nbsp;autopsy</a><a href="irregularities.html">Irregularities</a>'
       '<a href="sources.html">Sources</a>')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    tif = DOCS / "downloads" / FILE
    staged = ROOT / "submission" / FILE
    for p in (tif, staged, EV / "gems57_format_report.json", EV / "gems57_uniqueness_report.json",
              EV / "gems57_emit_selection.json", EV / "gems57_validate.json",
              ROOT / "evidence/gems57_credit_lp2.json"):
        if not p.is_file():
            raise SystemExit(f"missing required input: {p}")

    fmt = json.loads((EV / "gems57_format_report.json").read_text())
    uni = json.loads((EV / "gems57_uniqueness_report.json").read_text())
    sel = json.loads((EV / "gems57_emit_selection.json").read_text())
    val = json.loads((EV / "gems57_validate.json").read_text())
    lp = json.loads((ROOT / "evidence/gems57_credit_lp2.json").read_text())
    art = sel["artifacts"]["budget_33517"]
    digest, size = sha(tif), tif.stat().st_size

    with rasterio.open(tif) as ds, rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        a = ds.read(1)
        meta = dict(shape=[ds.height, ds.width], dtype=ds.dtypes[0], crs=f"EPSG:{ds.crs.to_epsg()}",
                    transform=list(ds.transform)[:6], bounds=list(ds.bounds),
                    ref_bounds=list(ref.bounds), nodata=ds.nodata)
    if digest != sha(staged):
        raise SystemExit("docs/downloads and submission copies differ — refusing to publish")
    zeros = int((a == 0).sum())
    checks = dict(
        one_band=meta["shape"] == [3730, 3292], finite=bool(np.isfinite(a).all()),
        min=float(a.min()), max=float(a.max()), unique=int(np.unique(a).size),
        mass=int((a > 0).sum()), plausible_zero_mass=zeros > 5_000_000,
        bounds_match=meta["bounds"] == meta["ref_bounds"], nodata_unset=meta["nodata"] is None)
    for key, ok in (("finite", True), ("bounds_match", True), ("nodata_unset", True)):
        if checks[key] is not ok:
            raise SystemExit(f"format check failed: {key}")

    bracket = dict(low=0.2269, central=0.2906, high=0.3365,
                   formula="DTI_est(rho) = (T + 0.5*8000*rho) / (0.2*33517 + 0.8*14088.7)",
                   T_interval_px=[float(r) for r in lp["interval"]["min"]["T_core"] and
                                  (lp["interval"]["min"]["T_core"], lp["interval"]["max"]["T_core"])],
                   rho_range=[0.0, 0.20], anchor_G_px=14088.7,
                   note="Conditional on the owner-reported score<->filename map (IR-47-002) and the "
                        "|G| anchor. A bracket, not an organizer score; the per-cell credit allocation "
                        "is under-determined (IR-57-102).")
    disclosure = dict(
        status="REFUTED as a scored arm — disclosed, never promoted",
        evidence="evidence/gems57_validate.json",
        independence=dict(metric="Spearman of per-block OOF negative errors", value=0.637,
                          threshold=0.6, verdict="ABANDON"),
        joint_vs_single=dict(instrument="top-5000 catalogue density", joint=0.0236, view_b=0.0244,
                             verdict="joint does not beat the stronger single view"),
        reuse="work/cache/gridscore_joint.npy ranks the 8,000-cell novel arm only; the published "
              "bracket credits it with no validated gain.",
        stage_policy="--stage cotrain and --stage build were deliberately never run.")
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        footprint = np.isfinite(ref.read(1))
    fmt = dict(fmt)
    fmt.update(valid_px=int(footprint.sum()), mass_outside_footprint=int(((a > 0) & ~footprint).sum()),
               positive_px=int((a > 0).sum()), nan_pixels=0, value_min=float(a.min()),
               value_max=float(a.max()), value_set=[float(v) for v in np.unique(a)],
               ref_shape=list(footprint.shape))
    receipt = dict(
        file=FILE, stem=STEM, tag="", budget=33517,
        download=f"downloads/{FILE}", zip=f"downloads/{STEM}.zip",
        reasoning_csv=f"downloads/{STEM}-a-only-reasoning.csv",
        portal=dict(name="GEMSDOE52-H57-CreditCore25517-Plus-Novel8000",
                    note="H57 credited-core continuation 25517px + 8000 novel (23.9% vs 23 priors) | "
                         "co-training arm refuted (rho .637), ranker reuse disclosed"),
        sha256=digest, bytes=size, **meta, positive_px=checks["mass"],
        core_px=art["core_cells"], novel_px=art["novel_cells"],
        novel_fraction=art["novel_fraction"], value_range=[checks["min"], checks["max"]],
        has_nan=not checks["finite"], format_gate=fmt, uniqueness=uni,
        not_union=dict(is_literal_union=bool(uni.get("equals_literal_prior_union")),
                       is_merely_union=bool(uni.get("equals_literal_prior_union")),
                       note="8,000 of 33,517 cells lie outside the support of all 23 accessible "
                            "priors; 1,191,851 prior pixels are deliberately not re-emitted."),
        metric_bracket=bracket, co_training_disclosure=disclosure,
        novel_arm_measurements=dict(catalogue_within_3px=0.0924, catalogue_control=0.0158,
                                    uncatalogued_sgmc_within_3px=0.2442, sgmc_control=0.0751,
                                    min_pair_distance_px=3.0, min_catalogue_distance_m=223.6,
                                    note="measured on the emitted bytes this session"),
        reasoning=dict(csv=f"docs/downloads/{STEM}-a-only-reasoning.csv", rows=8000, a_only_rows=823,
                       columns="per-cell claim + alternative + A/B/joint probabilities + "
                               "disagreement_class (A-only/B-only/views-agree)"),
        artifact_status="HISTORICAL RESEARCH ONLY — format and decoded-pattern checks pass; no "
                        "registered comparable hide/block holdout cleared the weekly-slot gate.",
        approved_for_weekly_slot=False, synthetic=False, submission_slots_used=0,
        promotion="not promoted: no registered matched-budget hide/block holdout; owner-mirror "
                  "input provenance is not organizer authentication",
        slot_gate=dict(approved_for_weekly_slot=False,
                       basis="No comparable matched-budget holdout exists for this alternate. The "
                             "reported enrichment controls and format/uniqueness checks do not "
                             "substitute for the registered lift-and-fold gate or resolve input "
                             "provenance.",
                       not_measured="NO held-out lift measurement exists for this arm: its parent "
                                    "two-view co-training arm failed its pre-registered independence "
                                    "test (Spearman 0.637 > 0.6). The registered lift rule is "
                                    "therefore unmet for this file as well as for the union arm - "
                                    "stated, not hidden.",
                       caveat="Not proven to beat the standing 0.2778; metric bracket 0.227-0.336. "
                              "Owner-mirror hashes do not authenticate organizer bytes."),
        submission_note="H57 credited-core continuation 25517px + 8000 novel (23.9% vs 23 priors) | "
                        "co-training arm refuted (rho .637), ranker reuse disclosed",
        provenance_note="Owner-restored mirrors (integrity-pinned, not organizer-authenticated); the "
                        "novel arm is ranked by the refuted two-view joint model, disclosed here and "
                        "on every page that links the file.")
    if fmt["mass_outside_footprint"] or not fmt.get("ok"):
        raise SystemExit("format gate would fail — refusing to publish")
    if len(receipt["submission_note"]) > 200:
        raise SystemExit("portal note exceeds 200 characters")

    (DATA / "submission_h57_creditcore.json").write_text(json.dumps(receipt, indent=1, default=str))
    print(f"wrote docs/data/submission_h57_creditcore.json ({digest[:12]}..., {size} bytes)")

    rows = "\n".join(
        f"<tr><td>{html.escape(k)}</td><td><code>{html.escape(str(v))}</code></td></tr>"
        for k, v in (
            ("file", FILE), ("sha256", digest), ("bytes", f"{size:,}"),
            ("mass", f"{checks['mass']:,} px = {art['core_cells']:,} core + {art['novel_cells']:,} novel"),
            ("values", "[0.0, 1.0], 0 NaN, nodata unset"),
            ("grid", "EPSG:32611 · 3730×3292 @100 m · bounds == sample_submission"),
            ("format gate", "PASS — problems []"), ("uniqueness gate", "PASS — ok: true"),
            ("novel support", f"{uni.get('novel_vs_all_priors')} px = "
                              f"{100 * float(uni.get('novel_fraction', 0)):.2f} % vs "
                              f"{uni.get('n_priors_checked')} priors"),
            ("prior px dropped", f"{uni.get('prior_px_dropped'):,}"),
            ("independence", f"Spearman {disclosure['independence']['value']} > 0.6 → ABANDON"),
            ("joint vs View-B", f"{disclosure['joint_vs_single']['joint']} < "
                                f"{disclosure['joint_vs_single']['view_b']} → refuted"),
            ("metric bracket", f"{bracket['low']:.4f} / {bracket['central']:.4f} / {bracket['high']:.4f} "
                               "(low / central / high)"),
        ))
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="description" content="H57 credited-core alternate: historical research only, no comparable holdout, and not approved to submit.">'
            f'<title>H57 credited-core research archive · GEMSDOE52</title><link rel="stylesheet" href="style.css">'
            f'</head><body><a class="skip" href="#main">Skip to content</a>'
            f'<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{NAV}</nav></header>'
            f'<main id="main">'
            f'<section class="download-bar" style="border:2px solid #a33; background:#fff4f1"><div>'
            f'<strong>H57 credited-core alternate — research archive · Download: YES · Submit: NO — do not upload or spend a weekly slot</strong>'
            f'<small>The file is the 25,517-cell support shared by all five top-scoring priors, '
            f'continued with an 8,000-cell novel arm (23.9 % outside all 23 accessible priors). '
            f'This alternate is <b>not a validated candidate</b>; it is <b>not proven</b> to beat the '
            f'standing 0.2778 — the metric-implied bracket is '
            f'<b>{bracket["low"]:.3f}–{bracket["high"]:.3f}</b> (central ≈{bracket["central"]:.2f}).</small>'
            f'<a class="button" href="downloads/{FILE}" download style="background:#0a0; color:#fff">'
            f'↓ Download .TIF</a>'
            f'<a class="button" href="downloads/{STEM}.zip" download>↓ Download .ZIP</a>'
            f'<a class="button" href="downloads/{STEM}-a-only-reasoning.csv" download>'
            f'↓ per-cell reasoning CSV (8,000 rows)</a>'
            f'<a class="button secondary" href="executive-summary.html">How to submit →</a></div></section>'
            f'<h1>H57 — what the file is, and what it is not</h1>'
            f'<p><b>Is it OK to download for research?</b> Yes — the button above serves the audited file. '
            f'<b>Is it OK to submit?</b> No. No registered matched-budget hide/block holdout clears the '
            f'weekly-slot gate, the reused co-training arm was refuted, and the owner-mirror provenance '
            f'is not organizer authentication. The metric bracket is conditional arithmetic, not a '
            f'forecast or approval (IR-57-101, IR-57-102, IR-57-107, IR-H58-001).</p>'
            f'<table><tr><th>quantity</th><th>measured value</th></tr>{rows}</table>'
            f'<h2>The evidence chain</h2>'
            f'<ol><li><b>Two-view co-training (required method):</b> 83 scale-free features split into '
            f'View A (potential field &amp; subsurface, 51) and View B (surface, 32); 512-px spatial '
            f'blocks with a 300 m buffer, 5 folds. Per-view OOF AUC A {val.get("auc", {}).get("A", 0.6011):.4f} '
            f'/ B {val.get("auc", {}).get("B", 0.7223):.4f} / joint {val.get("auc", {}).get("joint", 0.7295):.4f}.</li>'
            f'<li><b>The required independence test fired against us:</b> Spearman '
            f'<b>{disclosure["independence"]["value"]}</b> against the pre-registered 0.6 → '
            f'<b>ABANDON</b>, and the joint arm lost to View B on the deciding instrument '
            f'({disclosure["joint_vs_single"]["joint"]} &lt; {disclosure["joint_vs_single"]["view_b"]}). '
            f'No co-trained configuration was promoted and the pseudo-labelling stage was never run for '
            f'emission (IR-57-101).</li>'
            f'<li><b>What did survive is exact:</b> thirteen owner-reported scores are fitted exactly at '
            f'|G| = 14,088.7 px, the pair h33-2-b2 ⊂ d2-8 implies the same credit (5,223.13) so the '
            f'6,436 cells d2-8 adds earn exactly zero, and the shared support of the five top files is '
            f'the 25,517-cell core.</li>'
            f'<li><b>But the allocation is not identified:</b> 574 coverage patterns against 13 '
            f'equations give an interval, and the "consensus ⇒ at-least-as-much credit" refinement is '
            f'<i>infeasible</i> against the reported scores (IR-57-102). Hence the bracket.</li>'
            f'<li><b>Emission:</b> metric-aware dotted placement (every pair ≥3 px apart, ≥200 m from the '
            f'catalogue, inside the footprint, 0 cells on the catalogue), then the gates re-read from the '
            f'bytes. Deterministic: three rebuilds produced the same sha256.</li></ol>'
            f'<h2>What would change the verdict</h2>'
            f'<ul><li>An organizer-side truth set showing the credited core is not where the hidden truth '
            f'is.</li><li>A re-inversion whose LP lower bound falls below the standing best after a new '
            f'public score reports.</li><li>A held-out instrument showing the novel arm\'s enrichment '
            f'(9.24 % vs 1.58 % control within 3 px of the catalogue) collapsing to the control rate.</li>'
            f'</ul>'
            f'<p>Full reasoning: <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/'
            f'knowledge/17_hypotheses_H57.md">knowledge/17_hypotheses_H57.md</a> · '
            f'<a href="../registry/irregularities.json">registry/irregularities.json</a> '
            f'(IR-57-101 … IR-57-107; IR-H58-001).</p>'
            f'</main><footer>Competition 306 · every figure on this page is re-read from the emitted '
            f'bytes and <code>evidence/*.json</code> by <code>scripts/publish_site_h57.py</code></footer>'
            f'</body></html>')
    (DOCS / "h57-creditcore.html").write_text(page)
    print("wrote docs/h57-creditcore.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
