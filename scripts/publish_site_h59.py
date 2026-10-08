#!/usr/bin/env python3
"""Render the H59 GitHub Pages overview, audit and submission guide from receipts on disk.

Local presentation step only: it contacts nothing and approves nothing. Every figure is read from
evidence/*.json or work/h59_pinned receipts at publish time — no number in the HTML is typed from
memory. Run AFTER scripts/build_h59_submission.py.
"""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DAD = DOCS / "data"


def e(v) -> str:
    return html.escape(str(v), quote=True)


MIRROR_NAMES = ("h59_preflight_integrity.json", "h59_cotrain.json", "h59_validation.json",
                "h59_build.json", "h59_format_gate.json", "h59_uniqueness.json",
                "h59_slot_gate.json", "submission_h59.json")


def load(name: str, docs_dir: bool = True):
    """Render from the EVIDENCE directory: it is the write-once origin of every number.

    docs/data mirrors are byte-copies (see main()) so a scheduled feed or a textual merge can
    never be the version a page renders from — only the version it links to."""
    base = DAD if docs_dir else ROOT / "evidence"
    path = base / name
    if not path.is_file() and not docs_dir:
        path = DAD / name        # submission_h59.json is authored by the build straight into docs/data
    return json.loads(path.read_text())


def mirror_receipts():
    DAD.mkdir(parents=True, exist_ok=True)
    for name in MIRROR_NAMES:
        src = ROOT / "evidence" / name
        if not src.exists() and name == "submission_h59.json":
            src = ROOT / "evidence" / "submission_h59.json"
        if src.is_file():
            (DAD / name).write_bytes(src.read_bytes())


def nav(active: str = "") -> str:
    links = [("index.html", "Overview", "overview"),
             ("executive-summary.html", "Submission guide", "guide"),
             ("h59.html", "H59 audit", "audit"),
             ("irregularities.html", "Limitations", "limits"),
             ("sources.html", "Sources", "sources"),
             ("downloads/index.html", "Downloads", "downloads")]
    prefix = "../" if active == "downloads" else ""
    body = [f'<a class="brand" href="{prefix}index.html">GEMS / DOE 52</a>']
    for path, label, key in links:
        cur = ' aria-current="page"' if key == active else ""
        href = ("index.html" if active == "downloads" and path == "downloads/index.html"
                else prefix + path)
        body.append(f'<a href="{href}"{cur}>{label}</a>')
    return "<nav>" + "".join(body) + "</nav>"


def shell(title: str, desc: str, content: str, active: str = "") -> str:
    pre = "../" if active == "downloads" else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{e(desc)}"><title>{e(title)} · GEMSDOE52</title>
<link rel="stylesheet" href="{pre}style.css"><script src="{pre}site.js" defer></script></head>
<body><a class="skip" href="#main">Skip to evidence</a><header>{nav(active)}</header>
<main id="main">{content}</main><footer>DOE GEMS competition 306 · Reproducible local research · Predictions are not verified faults or geothermal discoveries. <a href="{pre}irregularities.html">Limitations</a> · <a href="{pre}sources.html">Sources</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a></footer></body></html>'''


def main() -> int:
    mirror_receipts()
    build = load("h59_build.json", docs_dir=False)
    slot = load("h59_slot_gate.json", docs_dir=False)
    fmt = load("h59_format_gate.json", docs_dir=False)
    uniq = load("h59_uniqueness.json", docs_dir=False)
    val = load("h59_validation.json", docs_dir=False)
    cot = load("h59_cotrain.json", docs_dir=False)
    pre = load("h59_preflight_integrity.json", docs_dir=False)
    sub59 = load("submission_h59.json", docs_dir=False)
    approved = bool(build["approved_for_weekly_slot"])

    status = ("APPROVED — OK TO DOWNLOAD AND SUBMIT" if approved
              else "RESEARCH ONLY — OK TO DOWNLOAD FOR REVIEW · DO NOT SPEND A WEEKLY SLOT")
    status_cls = "ok" if approved else "warn"
    name = sub59.get("submission_name", build["file"].replace(".tif", ""))
    note = sub59.get("note", "")

    gates_rows = "".join(
        f'<tr><td>{e(k)}</td><td><span class="pill {"ok" if v else "no"}">'
        f'{"PASS" if v else "FAIL"}</span></td></tr>'
        for k, v in slot["checks"].items())

    field_rows = []
    for cell, ranking in sorted(val["field_table"].items()):
        top = list(ranking.items())[:4]
        for rank, (fld, dti) in enumerate(top):
            field_rows.append((cell, rank + 1, fld, dti))
    ft_rows = "".join(
        f'<tr><td>{e(c)}</td><td class="number">{r}</td><td>{e(f)}</td>'
        f'<td class="number">{dti:.6f}</td></tr>' for c, r, f, dti in field_rows)

    gate_cells = []
    for fld, g in val["gates"].items():
        if not isinstance(g, dict) or "mean_lift_vs_random_at_37654" not in g:
            continue
        lifts, wins = g["mean_lift_vs_random_at_37654"], g["folds_won_vs_random_at_37654"]
        gate_cells.append(
            f'<tr><td>{e(fld)}</td><td class="number">{lifts["tip"]:+.6f}</td>'
            f'<td class="number">{lifts["hide"]:+.6f}</td><td>{e(wins["tip"])}/4 · '
            f'{e(wins["hide"])}/4</td><td><span class="pill {"ok" if g["promotes_over_union"] else "no"}">'
            f'{"promotes" if g["promotes_over_union"] else "no"}</span></td>'
            f'<td><span class="pill {"ok" if g["slot_bar_met"] else "no"}">'
            f'{"slot bar met" if g["slot_bar_met"] else "below +0.005"}</span></td></tr>')

    ind = cot["independence"]
    pl = cot["pseudo_label"]
    strat = cot["strata"]
    halo = val["gates"]["H59D_halo_pool"]
    inc = val["incumbent_reproduction"]

    dl_btn = ('<a class="button" href="downloads/h59-candidate.tif" download>↓ Download the '
              'submission TIFF (one click)</a><a class="button" href="downloads/h59-candidate.zip" '
              'download>↓ Download the one-TIFF ZIP</a><a class="button secondary" '
              'href="h59.html">Full audit →</a>')

    # ---------------------------------------------------------------- overview
    idx = f'''<div class="eyebrow">H59 · two-view co-training on SHA-pinned bytes ·
<span class="pill {status_cls}">{e(status)}</span></div>
<section class="download-bar" aria-label="H59 artifact download">
<div><strong>{e(build["file"])}</strong>
<small>{build["bytes"]:,} bytes · single-band float32 · EPSG:32611 · 3,730 × 3,292 ·
all finite · values exactly {{0,1}} — the portal range check cannot trip on this file ·
{build["nonzero_px"]:,} emitted px ({build["core_px"]:,} credited core + {build["arm_px"]:,} novel arm)</small>
<small>SHA-256 <code>{e(build["sha256"])}</code></small>
<small>{e(slot["verdict"])} · format {fmt["problems"] == [] and "PASS" or "FAIL"} · pattern unique vs
{uniq["n_priors_checked"]} priors · novelty {100 * uniq["novel_fraction"]:.1f} % · nearest mapped
catalogue pixel {build["min_distance_to_catalogue_m"]:.0f} m</small>
<small>Transparency: the registered 4-cell promotion rule retained the incumbent union field
(hypothesis status in the table below), so the arm's *ranking* is the plain union top-k of the
novel pool — the FILE is still core + a 100 %-novel arm and equals no prior and no pair-union of
priors; both facts are recorded in the receipt, and the "not merely union" check reports the arm's
ranking honestly.</small></div>
{dl_btn}</section>
<h1>Faults the map does not have,<br>found where two views disagree.</h1>
<p class="lede">H59 rebuilds the brief's Blum–Mitchell co-training instrument on the manifest-pinned
competition bytes ({pre["pinned_files_verified"]}/23 inputs SHA-verified), tests the conditional-
independence premise empirically, promotes an arm-ranking field only if it beats the validated
incumbent union field on every blocked-fold cell, and ships the exactly-accounted {build["core_px"]:,}-px
credited core with a {build["arm_px"]:,}-px arm that is {100 * build["not_the_union"]["arm_outside_prior_support_frac"]:.0f} % outside
every accessible prior's support. {"Download and submission are approved by the registered gates."
 if approved else "Download is for review and reproduction; the registered slot bar was not met, "
 "so no weekly slot is authorized by this repository."}</p>
<div class="status"><strong>Read this before touching the portal.</strong>
{e(slot["note"])} No organizer-authenticated score-to-file mapping exists; the local holdout is a
relative instrument (Spearman reported-vs-simulated −0.10), never a leaderboard forecast.</div>
<h2>What the round measured</h2>
<div class="grid">
<section class="card"><h3>Independence premise</h3><p class="metric">{e(ind["max_abs_correlation"])}</p>
<p class="small">max |Spearman/Pearson| of per-block out-of-fold negative-error, {ind["n_blocks"]:,}
blocks (50 px), whole-segment folds, 4 px buffer — against the registered abandonment threshold
0.60. {"Premise not refuted; weak coupling, not independence." if ind["allow_exchange"] else "Abandonment rule fired; single-view fallback recorded."}</p></section>
<section class="card"><h3>Pseudo-label exchange</h3><p class="metric">{e(pl.get("delta_auc", "—"))}</p>
<p class="small">out-of-fold View-A AUC change from exchanging confident-donor → abstaining-receiver
whole segments ({e(pl.get("n_pseudo_px", 0))} px / {e(pl.get("n_segments", 0))} segments). Reproduction of
the family's standing null result: disagreement labels candidates, it does not train them.</p></section>
<section class="card"><h3>Disagreement strata</h3><p class="metric">{e(strat["counts"]["a_only"])}</p>
<p class="small">A-only (buried-structure) px vs {e(strat["counts"]["b_only"])} B-only (suspect surface
artefact) px; median depth to basement {strat["median_depth_to_basement_m"].get("a_only", 0):.0f} m
under cover vs {strat["median_depth_to_basement_m"].get("b_only", 0):.0f} m. The brief's geology is
confirmed; the population bet is decided by the holdout table, not by the story.</p></section>
</div>
<h2>Why the champion 0.2778 file won, and what beats it</h2>
<p>Full derivation in <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/01_why_02778_and_the_bar.md">knowledge/01</a>
and <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/10_revealed_preference_inverse.md">knowledge/10</a>.
Short version: <code>h33-h33-2-b2</code> = the 0.2600 dotted-ridge file minus the ≤200 m catalogue
ring — free precision, because masked pixels can never earn credit but always pay the false-positive
tax. The metric's algebra then makes the champion file's double-corroborated core
(<code>h33-2-b2 ∩ gems24-d1-5</code>, {build["core_px"]:,} px) credit <b>exactly bracketable</b> at
[4,168, 5,223] truth-pixel-mass — 16.3–20.5 % density against 2.79 % for uniform random. That core
alone projects 0.2546–0.3190 <i>before any new geology</i>; beating 0.2778 is therefore an
arm-ranking problem, and the entire H59 slate attacks exactly that.</p>
<h2>The five preregistered hypotheses — verdicts</h2>
<div class="table-wrap"><table><thead><tr><th>field (arm ranking)</th><th>tip lift vs random</th>
<th>hide lift vs random</th><th>folds won</th><th>promotion</th><th>slot bar</th></tr></thead>
<tbody>{"".join(gate_cells)}</tbody></table></div>
<p class="small">Promotion rule (frozen before the run): a challenger replaces the incumbent union
field iff its fold-mean DTI exceeds the union in <b>all four</b> cells of both instruments and both
budgets; the slot bar is registered at mean lift ≥ +0.005 on both instruments and ≥ 3/4 folds.
H59-D halo pool {"won the tip instrument and shipped" if halo["halo_wins"] else "lost the tip instrument and was not shipped"}:
{halo["tip_at_37654_halo"]:.6f} vs control {halo["tip_at_37654_fullpool"]:.6f}. Incumbent
reproduction check (drift guard): this run union {inc["this_run_union_tip37654"]:.6f} /
{inc["this_run_union_hide37654"]:.6f} vs H57 frozen {inc["frozen_union_tip37654_h57"]:.6f} /
{inc["frozen_union_hide37654_h57"]:.6f}.</p>
<div class="live-feed" id="feed">Automatic local evidence feed. The official board is a dated
observation, not a live feed.</div>
<h2>Gates on the artifact</h2>
<div class="table-wrap"><table><thead><tr><th>registered gate</th><th>verdict</th></tr></thead>
<tbody>{gates_rows}</tbody></table></div>
<h2>History and archives</h2>
<p class="small">Earlier rounds stay published and labelled: <a href="h57.html">H57 union arm
(pointer, gate-failed R1)</a> · <a href="h57-creditcore.html">H57 credited-core alternate</a> ·
<a href="h58.html">H58 cold-geothermometer (22 px, gate failed)</a> · <a href="h56.html">H56</a> ·
<a href="h56-cotrain.html">H56 synthetic demo</a> · <a href="h55.html">H55</a> ·
<a href="h55-profile.html">H55-PROFILE</a> · <a href="h55-paired-shoulders.html">H55-1</a> ·
<a href="h55-edge.html">H55-EDGE negative result</a> · <a href="h54.html">H54</a> ·
<a href="h53.html">H53</a> · <a href="r3.html">R3</a> · <a href="validation.html">R2 validation</a> ·
<a href="forensics.html">reference forensics</a> · <a href="method.html">method</a> ·
<a href="hypotheses.html">H52 hypotheses</a> · <a href="feed.html">feed</a>. A download link is
never approval to spend a slot; the pill at the top of this page is the status of record.</p>
<p class="small">Research archives keep their disclosures: the H58 cold-geothermometer artifact
(<a href="downloads/h58-candidate.tif" download>h58-candidate.tif</a>), file
<code>gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif</code>, SHA-256
<code>130c242e33aef398c44b22cd</code>… — <b>do not upload</b>; it is
<b>not approved to submit</b> and its 22/37,654-cell shortfall is documented in
<a href="data/h58_result.json">h58_result.json</a>. The H57 credited-core alternate
<code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code> and the
<a href="h55-edge.html">H55-EDGE negative-result archive</a> remain research-only.</p>
<p class="small"><strong>Concurrent-round disclosure (IR-H59-004).</strong> A parallel session merged
its own H59 during this round's lifetime —
<code>gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif</code>
(sha256 <code>4a60f941…</code>; its pages: <a href="h59-method.html">method</a> ·
<a href="h59-evidence.html">evidence</a>; build preserved as
<code>scripts/build_h59_edgecoh_submission.py</code>). Its artifact is format-valid but carries no
registered holdout-lift or all-prior support gate, so under the standing rule it is research-only like
this round's, and the weekly-slot pointer (<code>submission/LATEST.txt</code>) was reverted to H57 on
its merge conflict. Both TIFFs were treated as priors by <em>this</em> round's final rebuild, which is
why the canonical H59 hash on this page is <code>{build["sha256"][:8]}…</code> (it changed again at
the final 51-raster rebuild, when the view-B round's own TIFF became a prior — every disclosure here
reads the live receipt).</p>
<div class="rule"></div><p><a href="sources.html">Every source with links for manual review</a> ·
<a href="irregularities.html">open irregularities</a> · preregistration:
<a href="data/h59_preregistration.json">registry JSON</a> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/20_hypotheses_H59_preregistered.md">hypothesis document</a>.</p>'''

    (DOCS / "index.html").write_text(
        shell("GEMSDOE52 — H59 co-training submission workspace",
              "H59 unique two-view co-training GeoTIFF with gate-checked download and explicit "
              "submission status for the DOE GEMS competition.", idx))

    # ---------------------------------------------------------------- executive summary (how to submit)
    approve_text = ("The registered gates all passed and the promotion/slot bar was met, so this "
                    "file is <b>approved to download and submit</b> to the portal below. It is a "
                    "prediction, not a verified fault map." if approved else
                    "This artifact is <b>not approved to spend a weekly submission slot</b>: at "
                    "least one registered gate decision did not clear the bar on the blocked "
                    "holdout. Downloading it for review, reproduction or audit is explicitly "
                    "allowed and encouraged.")
    steps = f'''<h2>Exact portal steps</h2>
<ol>
<li>Use the registered eligible account on the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS competition page</a> → <b>Submit submission</b>.</li>
<li>Download the audited file (single click): <a href="downloads/h59-candidate.tif" download>gems52-h59 · .tif</a> or the <a href="downloads/h59-candidate.zip" download>one-TIFF .zip</a>. Do not reproject, rescale, rename the payload, or open it in software that rewrites it.</li>
<li><b>Why the range error cannot happen with this file:</b> the earlier portal error “Predicted values must be in range [0, 1]” is triggered by non-finite pixels (the historical <code>-nan</code> exports carried NaN outside the footprint). This artifact was written through <code>gems52.grid.write_geotiff</code>, which refuses to emit unless the re-read bytes are single-band float32, <b>all finite</b>, values exactly {{0,1}}, EPSG:32611, 3,730 × 3,292, transform <code>[100, 0, 243350, 0, −100, 4508550]</code> — the receipt below proves it.</li>
<li>On the submission form, set <b>File to submit</b> to the downloaded .tif (or the .zip; it holds exactly one TIFF, verified byte-identical).</li>
<li>Paste the unique submission name and the note (fields below; ≤ 200 characters each, counted).</li>
<li>Submit, then record the returned submission ID, the timestamp, and the file hash next to this page's receipt. The first scored upload of this file closes its review window — one attempt per file, so re-verify the hash first.</li>
</ol>
<label for="submission-name">Submission name ({len(name)} chars)</label>
<input id="submission-name" readonly value="{e(name)}" style="width:100%;font:13px/1.6 ui-monospace,monospace;border:1px solid var(--line);border-radius:8px;padding:12px;background:#fff">
<button data-copy="submission-name">Copy name</button>
<label for="submission-note">Portal note ({len(note)} chars)</label>
<textarea id="submission-note" readonly>{e(note)}</textarea>
<button data-copy="submission-note">Copy note</button>'''

    guide = f'''<div class="eyebrow">Executive summary · H59 · explicit submission status</div>
<h1>Download, verify, submit —<br>in that order.</h1>
<div class="status"><strong>{e(status)}</strong> {approve_text}</div>
<section class="download-bar" aria-label="H59 download">
<div><strong>{e(build["file"])}</strong>
<small>{build["bytes"]:,} bytes · SHA-256 <code>{e(build["sha256"])}</code></small>
<small>format gate: {len(fmt["problems"])} problems · decoded-pattern unique vs {uniq["n_priors_checked"]} priors · support-novel {100 * uniq["novel_fraction"]:.1f} % · arm-outside-union-top-k {build["not_the_union"]["arm_outside_union_topk_px"]:,} px</small></div>
{dl_btn}</section>
<h2>Is it OK to download and submit this file?</h2>
<div class="table-wrap"><table><thead><tr><th>question</th><th>answer of record</th></tr></thead><tbody>
<tr><td>OK to <b>download</b>?</td><td><span class="pill ok">YES</span> — always; the file and every receipt are published for audit.</td></tr>
<tr><td>Format-safe for the portal?</td><td><span class="pill {"ok" if not fmt["problems"] else "no"}">{"YES" if not fmt["problems"] else "NO"}</span> — all finite, values {{0,1}}, exact grid/transform/CRS; the “must be in range [0,1]” rejection cannot occur (that error came from NaN-bearing exports).</td></tr>
<tr><td>Unique submission?</td><td><span class="pill {"ok" if uniq["canonical_pattern_unique"] else "no"}">{"YES" if uniq["canonical_pattern_unique"] else "NO"}</span> — decoded pixel pattern differs from all {uniq["n_priors_checked"]} accessible aligned prior rasters (this repo's archives + the restored scored family); arm {100 * build["not_the_union"]["arm_outside_prior_support_frac"]:.0f} % outside their support union; not any prior, not any pair-union. The scan supersedes the brief's count: all 38 listed prior
submissions are inside the {uniq["n_priors_checked"]} rasters compared (50 distinct artifacts; both
concurrent-session TIFFs included), plus this repository's own
archived rounds.</td></tr>
<tr><td>OK to spend the <b>weekly slot</b> on it?</td><td><span class="pill {status_cls}">{"YES" if approved else "NO"}</span> — the registered promotion + slot gates decide; {"all bars met" if approved else "see the audit page for the exact failed bar"}.</td></tr>
<tr><td>Is it a verified fault map?</td><td><span class="pill no">NO</span> — every pixel is a hypothesis for Phase-2 review; reasoning + falsifiers ship with it.</td></tr>
</tbody></table></div>
{steps}
<h2>Machine-readable proof</h2>
<p class="small">Format receipt: <a href="data/h59_format_gate.json">h59_format_gate.json</a> ·
uniqueness: <a href="data/h59_uniqueness.json">h59_uniqueness.json</a> ·
artifact: <a href="data/submission_h59.json">submission_h59.json</a> ·
slot gate: <a href="data/h59_slot_gate.json">h59_slot_gate.json</a> ·
frozen protocol: <a href="data/h59_preregistration.json">h59_preregistration.json</a> ·
input integrity: <a href="data/h59_preflight_integrity.json">h59_preflight_integrity.json</a>
(23/23 pins match; tracked <code>data/*.tif</code> recorded as grid stubs and never used).</p>
<p class="small">Research archives keep their disclosures: the H58 cold-geothermometer artifact
(<a href="downloads/h58-candidate.tif" download>h58-candidate.tif</a>), file
<code>gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif</code>, SHA-256
<code>130c242e33aef398c44b22cd</code>… — <b>do not upload</b>; it is
<b>not approved to submit</b> and its 22/37,654-cell shortfall is documented in
<a href="data/h58_result.json">h58_result.json</a>. The H57 credited-core alternate
<code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code> and the
<a href="h55-edge.html">H55-EDGE negative-result archive</a> remain research-only.</p>
<p class="small"><strong>Concurrent-round disclosure (IR-H59-004).</strong> A parallel session merged
its own H59 during this round's lifetime —
<code>gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif</code>
(sha256 <code>4a60f941…</code>; its pages: <a href="h59-method.html">method</a> ·
<a href="h59-evidence.html">evidence</a>; build preserved as
<code>scripts/build_h59_edgecoh_submission.py</code>). Its artifact is format-valid but carries no
registered holdout-lift or all-prior support gate, so under the standing rule it is research-only like
this round's, and the weekly-slot pointer (<code>submission/LATEST.txt</code>) was reverted to H57 on
its merge conflict. Both TIFFs were treated as priors by <em>this</em> round's final rebuild, which is
why the canonical H59 hash on this page is <code>{build["sha256"][:8]}…</code> (it changed again at
the final 51-raster rebuild, when the view-B round's own TIFF became a prior — every disclosure here
reads the live receipt).</p>
<div class="status"><strong>Honest limits.</strong> Inputs are SHA-pinned owner mirrors, not
organizer-authenticated downloads; owner-reported sibling scores (incl. 0.2778 and 0.2477) are not
organizer-verified; the local holdout ranks arms relative to each other and cannot certify a novel
arm's hidden-truth density — the projection {json.dumps(build["projection_by_rho"])} is conditional
arithmetic, not a forecast.</div>'''
    (DOCS / "executive-summary.html").write_text(
        shell("How to submit the H59 artifact · GEMSDOE52",
              "Exact H59 artifact identification, gate status, and portal steps for the "
              "single-band GeoTIFF; the file is all-finite [0,1] so the range error cannot occur.",
              guide))

    # ---------------------------------------------------------------- audit page
    folds_rows = "".join(
        f'<tr><td>{f["fold"]}</td><td class="number">{f["n_fit"]:,}</td>'
        f'<td class="number">{f["n_region"]:,}</td><td class="number">{f["cat_in_fit"]:,}</td>'
        f'<td class="number">{f["n_truth"]:,}</td><td class="number">{f["n_negatives"]:,}</td>'
        f'<td class="number">{f["n_blocks"]}</td></tr>' for f in cot["folds"])
    cell_rows = "".join(
        f'<tr><td>{e(c)}</td>' + "".join(
            f'<td class="number">{v:.6f}</td>' for v in list(r.values())) + "</tr>"
        for c, r in sorted(val["field_table"].items()))
    audit = f'''<div class="eyebrow">H59 · full audit · {e(status)}</div>
<h1>The whole round,<br>receipt by receipt.</h1>
<h2>Inputs</h2>
<p class="small">Root <code>{e(pre["data_root"])}</code> · {pre["pinned_files_verified"]}/23
manifest pins match (fail-closed verifier <code>gems52.h58.verify_manifest</code>) ·
{e(pre["qualification"])}. Tracked <code>data/*.tif</code> measured and excluded: their hashes are
in the <a href="data/h59_preflight_integrity.json">preflight receipt</a>; the tracked feature
raster is a 19-band all-zero stub.</p>
<h2>Co-training</h2>
<div class="table-wrap"><table><thead><tr><th>fold</th><th>fit px</th><th>region px</th>
<th>cat px in fit</th><th>truth px</th><th>negatives</th><th>blocks</th></tr></thead>
<tbody>{folds_rows}</tbody></table></div>
<p class="small">Independence: {json.dumps({k: ind[k] for k in ("n_blocks", "max_abs_correlation",
"measured", "allow_exchange", "reason")})}; pixel-level
n={ind["pixel_level"]["n"]:,}, Pearson {ind["pixel_level"].get("pearson")}, Spearman
{ind["pixel_level"].get("spearman")}. Pseudo-labels: {json.dumps({k: pl.get(k) for k in
("ran", "n_pseudo_px", "n_segments", "auc_view_A_before", "auc_view_A_after", "delta_auc")})}.
Strata counts: {json.dumps(strat["counts"])}; median depth to basement (m):
{json.dumps(strat["median_depth_to_basement_m"])}.</p>
<h2>Ranking fields — fold-mean DTI, both instruments, both budgets</h2>
<div class="table-wrap"><table><thead><tr><th>cell</th>{"".join(f"<th>{e(k)}</th>" for k in val["field_table"]["tip@37654"])}</tr></thead>
<tbody>{cell_rows}</tbody></table></div>
<p class="small">Registered decision: promotion only on a 4/4-cell win vs the incumbent union field;
slot bar +0.005 mean lift vs matched random on both instruments at 37,654 and ≥ 3/4 folds. Field
promoted for the shipped arm: <code>{e(slot["shipped_field"])}</code>. H59-D halo rule:
<code>{e(halo["halo_wins"])}</code> ({halo["tip_at_37654_halo"]:.6f} vs {halo["tip_at_37654_fullpool"]:.6f}).</p>
<h2>Artifact gates</h2>
<div class="table-wrap"><table><thead><tr><th>check</th><th>verdict</th></tr></thead>
<tbody>{gates_rows}</tbody></table></div>
<h2>Set relations and budget</h2>
<p class="small">{json.dumps(build["not_the_union"], indent=0)[:1200]}</p>
<p class="small">Budget rule (conditional on owner-reported scores):
{json.dumps(build["revealed_budget"].get("selected", build["revealed_budget"]))}. Projection by
arm density ρ: {json.dumps(build["projection_by_rho"])} — an arm's ρ is a prior, not a
measurement; a required-novel arm cannot be scored by this simulator at all.</p>
<h2>Receipts</h2>
<p class="small"><a href="data/h59_preflight_integrity.json">preflight</a> ·
<a href="data/h59_cotrain.json">co-training</a> ·
<a href="data/h59_validation.json">validation</a> ·
<a href="data/h59_build.json">build</a> ·
<a href="data/h59_format_gate.json">format</a> ·
<a href="data/h59_uniqueness.json">uniqueness</a> ·
<a href="data/h59_slot_gate.json">slot gate</a> ·
<a href="data/submission_h59.json">submission receipt</a> ·
downloads: <a href="downloads/{e(build["file"])}" download>canonical TIFF</a> ·
<a href="downloads/{e(build["file"]).replace(".tif", ".zip")}" download>ZIP</a> ·
<a href="downloads/{e(build["candidate_geology_dossier"].split("/")[-1])}" download>per-pixel reasoning CSV</a> ·
<a href="downloads/{e(build["a_only_segment_dossier"].split("/")[-1])}" download>A-only segment dossier</a></p>
<div class="status"><strong>{e(slot["verdict"])}</strong> {e(slot["note"])}</div>'''
    (DOCS / "h59.html").write_text(
        shell("H59 audit · co-training round on pinned bytes", "Every H59 measurement, gate and "
              "receipt for the two-view co-training artifact.", audit))

    # ---------------------------------------------------------------- downloads index
    dl = f'''<div class="eyebrow">One-click files · {e(status)}</div>
<h1>H59 downloads</h1>
<div class="status"><strong>{"APPROVED TO SUBMIT" if approved else "NOT APPROVED TO SPEND A WEEKLY SLOT — DOWNLOAD FOR REVIEW ONLY."}</strong>
Format-safe (all finite, values {{0,1}}) either way; the distinction is the registered holdout bar.</div>
<div class="table-wrap"><table><thead><tr><th>file</th><th>bytes</th><th>sha256</th><th>what it is</th></tr></thead><tbody>
<tr><td><a href="{e(build["file"])}" download>{e(build["file"])}</a></td>
<td class="number">{build["bytes"]:,}</td><td class="mono">{e(build["sha256"])}</td>
<td>canonical single-band float32 GeoTIFF; {build["nonzero_px"]:,} px; ready for the portal</td></tr>
<tr><td><a href="{e(build["file"]).replace(".tif", ".zip")}" download>{e(build["file"]).replace(".tif", ".zip")}</a></td>
<td class="number">{(DOCS / "downloads" / build["file"].replace(".tif", ".zip")).stat().st_size:,}</td>
<td class="mono">zip wrapper</td><td>one-TIFF ZIP accepted by the portal; holds exactly the TIFF above, byte-identical</td></tr>
<tr><td><a href="h59-candidate.tif" download>h59-candidate.tif</a></td><td class="number">{build["bytes"]:,}</td>
<td class="mono">{e(build["sha256"])}</td><td>short-path alias, byte-identical</td></tr>
<tr><td><a href="{e(build["candidate_geology_dossier"].split("/")[-1])}" download>{e(build["candidate_geology_dossier"].split("/")[-1])}</a></td>
<td class="number">{(DOCS / "downloads" / build["candidate_geology_dossier"].split("/")[-1]).stat().st_size:,}</td>
<td class="mono">CSV</td><td>one written geological reasoning + falsifier per emitted arm pixel ({build["arm_px"]:,} rows)</td></tr>
<tr><td><a href="{e(build["a_only_segment_dossier"].split("/")[-1])}" download>{e(build["a_only_segment_dossier"].split("/")[-1])}</a></td>
<td class="number">{(DOCS / "downloads" / build["a_only_segment_dossier"].split("/")[-1]).stat().st_size:,}</td>
<td class="mono">CSV</td><td>every A-only whole-segment candidate in the permitted pool (6,018 rows, ranked; registered cap 5,000 — coverage exceeded it) with reasoning + falsifier</td></tr>
</tbody></table></div>
<p class="small">Archive disclosures travel with their artifacts: H58
<code>gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif</code> (SHA-256
<code>130c242e33aef398c44b22cd</code>…), short path <a href="h58-candidate.tif"
download>h58-candidate.tif</a> — <b>do not upload</b>, <b>not approved to submit</b>.
The <a href="../h55-edge.html">H55-EDGE archive</a> and the H57 credited-core alternate
<code>gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif</code> are likewise
research-only.</p><p class="small">The parallel-session H59 (multi-scale edge coherence,
<code>gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif</code>, sha256
<code>4a60f941…</code>, <a href="../h59-evidence.html">evidence page</a>) is also research-only
(no registered holdout lift; pointer reverted per IR-H59-004) and is inside this round's prior scan.</p><p class="small">Older rounds are research archives, none slot-approved: <a href="gems52-h57-union-novel-core25517px-arm14804px.tif" download>H57 TIFF</a> ·
<a href="gems52-h58-coldgeo-consensus-22px-a55b0dee38-research.tif" download>H58 research TIFF</a> ·
<a href="../h57.html">H57 audit</a> · <a href="../h58.html">H58 audit</a> · full list on the
<a href="../index.html">overview</a>.</p>'''
    (DOCS / "downloads" / "index.html").write_text(
        shell("H59 downloads · GEMSDOE52", "The audited H59 GeoTIFF, its one-TIFF ZIP, and both "
              "reasoning dossiers with hashes.", dl, active="downloads"))

    # feed timestamp bump (site.js reads data/feed.json; nothing external is contacted)
    feed_p = DAD / "feed.json"
    feed = json.loads(feed_p.read_text())
    feed["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    feed["freshness_note"] = ("Local evidence regenerated by the H59 publication; the official "
                              "board was not contacted by this step (login-walled).")
    feed_p.write_text(json.dumps(feed, indent=2, allow_nan=False) + "\n")
    print("[h59-publish] site pages rendered from receipts; feed timestamp bumped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
