#!/usr/bin/env python3
"""Render the H58 GitHub Pages overview, audit and conditional submission guide from receipts.

This is a local presentation step only. It does not contact DrivenData or approve an upload.
Run scripts/refresh_feed.py first so docs/data and the short download aliases are staged.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def e(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_dti(value) -> str:
    return "—" if value is None else f"{float(value):.6f}"


def nav(active: str = "") -> str:
    links = [
        ("index.html", "Overview", "overview"),
        ("executive-summary.html", "Submission guide", "guide"),
        ("h58.html", "H58 audit", "audit"),
        ("irregularities.html", "Limitations", "limits"),
        ("sources.html", "Sources", "sources"),
        ("downloads/index.html", "Downloads", "downloads"),
    ]
    prefix = "../" if active == "downloads" else ""
    body = [f'<a class="brand" href="{prefix}index.html">GEMS / DOE 52</a>']
    for path, label, key in links:
        current = ' aria-current="page"' if key == active else ""
        href = ("index.html" if active == "downloads" and path == "downloads/index.html"
                else prefix + path)
        body.append(f'<a href="{href}"{current}>{label}</a>')
    return "<nav>" + "".join(body) + "</nav>"


def shell(title: str, description: str, content: str, active: str = "") -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{e(description)}"><title>{e(title)} · GEMSDOE52</title>
<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head>
<body><a class="skip" href="#main">Skip to evidence</a><header>{nav(active)}</header>
<main id="main">{content}</main><footer>DOE GEMS competition 306 · Reproducible local research · Predictions are not verified faults or geothermal discoveries. <a href="irregularities.html">Limitations</a> · <a href="sources.html">Sources</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and evidence</a></footer></body></html>'''


def download_bar(artifact: dict, result: dict, short: bool = True) -> str:
    name = str(artifact["file"])
    holdout = result["holdout"]
    modes = holdout.get("mode_summary", holdout.get("modes", {}))
    holdout_state = "PASS" if holdout["local_promotion_gate"]["holdout_pass_both_modes"] else "FAIL"
    reason = result.get("promotion_decision", "Research-only; no approval recorded.")
    links = [
        '<a class="button" href="downloads/h58-candidate.tif" download>↓ Download research TIFF</a>',
        '<a class="button" href="downloads/h58-candidate.zip" download>↓ Download one-TIFF ZIP</a>',
        '<a class="button secondary" href="h58.html">Full audit →</a>',
    ] if short else [
        '<a class="button" href="../downloads/h58-candidate.tif" download>↓ Download research TIFF</a>',
        '<a class="button" href="../downloads/h58-candidate.zip" download>↓ Download one-TIFF ZIP</a>',
        '<a class="button secondary" href="../h58.html">Full audit →</a>',
    ]
    return f'''<section class="download-bar" aria-label="H58 research artifact download">
<div><strong>H58-A · RESEARCH ONLY · DO NOT UPLOAD</strong>
<small><code>{e(name)}</code></small>
<small>{int(artifact['bytes']):,} bytes · single-band float32 · EPSG:32611 · 3,292 × 3,730 · values [0,1] · {int(artifact['emitted_pixels']):,} emitted pixels</small>
<small>Local matched holdout: <b>{holdout_state}</b> · hide lift {float(modes['hide']['mean_lift_vs_strongest_same_fold_baseline']):+.6f} ({int(modes['hide']['fold_wins'])}/4); block lift {float(modes['block']['mean_lift_vs_strongest_same_fold_baseline']):+.6f} ({int(modes['block']['fold_wins'])}/4)</small>
<small>SHA-256 <code>{e(artifact['sha256'])}</code></small>
<small>{e(reason)}</small></div>{''.join(links)}</section>'''


def metric_card(value: str, label: str) -> str:
    return f'<div class="card"><div class="metric">{e(value)}</div><div class="label">{e(label)}</div></div>'


def main() -> None:
    result = json.loads((EV / "h58_result.json").read_text())
    holdout_receipt = json.loads((EV / "h58_holdout.json").read_text())
    postrun_review_path = EV / "h58_postrun_review.json"
    postrun_review = json.loads(postrun_review_path.read_text()) if postrun_review_path.is_file() else {}
    prereg = json.loads((ROOT / "registry/h58_preregistration.json").read_text())
    artifact = result["artifact"]
    name = artifact["file"]
    stem = Path(name).stem
    submission_receipt_path = EV / f"submission_{stem}.json"
    submission = json.loads(submission_receipt_path.read_text())
    canonical = ROOT / "submission" / name
    if not canonical.is_file() or hashlib.sha256(canonical.read_bytes()).hexdigest() != artifact["sha256"]:
        raise RuntimeError("H58 TIFF on disk does not match its evidence receipt; refusing to render download instructions")
    if (result.get("approved_for_weekly_slot") is not False
            or submission.get("approved_for_weekly_slot") is not False
            or int(result.get("submission_slots_used", -1)) != 0):
        raise RuntimeError("H58 must remain explicitly not approved and zero-slot in this publisher")
    note = str(result.get("portal", {}).get("note", submission.get("submission_note", "")))
    if len(note) > 200:
        raise RuntimeError(f"H58 portal note exceeds the 200-character limit ({len(note)})")

    modes = result["holdout"].get("mode_summary", result["holdout"].get("modes", {}))
    aggregate = result["holdout"]["local_promotion_gate"]
    passed_artifacts = bool(artifact.get("all_artifact_gates_pass"))
    local_pass = bool(result.get("local_research_gate_passed"))
    status_detail = (
        "The registered local holdout and artifact checks pass, but the input-provenance blocker remains open. "
        "That local result is not organizer-authenticated validation and does not authorize a weekly slot."
        if local_pass else
        "The registered local promotion gate did not clear, or an artifact check failed. The TIFF is preserved as a research result only."
    )
    reasons = result.get("promotion_decision", "No promotion approval is recorded.")
    primary = int(artifact["emitted_pixels"])
    unique = artifact.get("uniqueness", {})
    exact_prior_matches = [row.get("path") for row in unique.get("per_prior", []) if row.get("identical")]
    canonical_unique = bool(unique.get("canonical_pattern_unique")) and not exact_prior_matches
    gates = artifact.get("artifact_gates", {})
    mode_rows = []
    for mode in ("hide", "block"):
        summary = modes[mode]
        for row in summary["folds"]:
            mode_rows.append(
                f'<tr><td>{e(mode)}</td><td>{int(row["fold"]) + 1}</td>'
                f'<td>{fmt_dti(row["candidate_dti"])}</td>'
                f'<td>{e(row["strongest_baseline"])}</td>'
                f'<td>{fmt_dti(row["strongest_baseline_dti"])}</td>'
                f'<td>{float(row["lift"]):+.6f}</td><td>{"Yes" if row["strict_win"] else "No"}</td>'
                f'<td>{"Yes" if row["budget_comparable"] else "No"}</td></tr>')
    holdout_table = '''<div class="table-wrap"><table><thead><tr><th>Mode</th><th>Fold</th><th>H58-A DTI</th><th>Strongest same-fold baseline</th><th>Baseline DTI</th><th>Lift</th><th>Win</th><th>Full-budget comparable</th></tr></thead><tbody>''' + "".join(mode_rows) + "</tbody></table></div>"
    summaries = []
    for mode in ("hide", "block"):
        row = modes[mode]
        summaries.append(
            f'<tr><td>{e(mode)}</td><td>{fmt_dti(row["candidate_mean"])}</td>'
            f'<td>{fmt_dti(row["strongest_same_fold_baseline_mean"])}</td>'
            f'<td>{float(row["mean_lift_vs_strongest_same_fold_baseline"]):+.6f}</td>'
            f'<td>{int(row["fold_wins"])}/4</td><td>{"PASS" if row["local_research_gate"] else "FAIL"}</td></tr>')
    summary_table = '''<div class="table-wrap"><table><thead><tr><th>Mode</th><th>Candidate mean DTI</th><th>Strongest same-fold baseline mean</th><th>Mean lift</th><th>Fold wins</th><th>Registered mode gate</th></tr></thead><tbody>''' + "".join(summaries) + "</tbody></table></div>"

    artifact_rows = [
        ("Pinned input bytes", "PASS" if all(x.get("matches_pin") for x in result.get("manifest_inputs", [])) else "FAIL"),
        ("TIFF / sample-template format", "PASS" if artifact.get("format_gate", {}).get("ok") else "FAIL"),
        ("Decoded pattern distinct from accessible priors", "PASS" if canonical_unique else "FAIL"),
        ("Per-pixel H58-A geology reasoning", "PASS" if artifact.get("reasoning", {}).get("one_reason_per_emitted_candidate") else "FAIL"),
        ("F_geo support capacity (no zero-score backfill)", "PASS" if gates.get("candidate_support_capacity") else "FAIL"),
        ("Full-budget fold comparability", "PASS" if all(modes[m]["all_primary_folds_budget_comparable"] for m in ("hide", "block")) else "FAIL"),
        ("Input provenance / organizer authentication", "OPEN — unresolved"),
    ]
    gate_rows = "".join(f"<tr><td>{e(label)}</td><td><b>{e(value)}</b></td></tr>" for label, value in artifact_rows)
    independence = result.get("independence", {})
    pseudo = result.get("pseudo_label_diagnostic", {})
    if pseudo.get("ran"):
        pseudo_status = f"Diagnostic attempted on {len(pseudo.get('folds', []))} outer folds; it never changes H58-A."
    else:
        pseudo_status = f"Not run: {pseudo.get('reason') or 'independence gate did not allow exchange'}."

    bar = download_bar(artifact, result)
    hero_status = f'''<div class="status"><strong>H58 is not approved for competition upload.</strong>{e(status_detail)} Open blocker: <code>IR-H58-001</code>. No portal upload, organizer score, or weekly slot is recorded. {e(reasons)}</div>'''
    index_body = f'''{bar}<div class="eyebrow">H58 · cold-geothermometer proposal · local evidence only</div>
<h1>A research candidate,<br>not an upload approval.</h1>
<p class="lede">Four preregistered geology hypotheses are recorded in the repository. H58-A is the only one runnable from the pinned local inputs; it tests whether carefully selected cold discharges with agreeing high reservoir-geothermometer estimates provide a useful proxy for mapped fault segments.</p>
{hero_status}
<div class="grid">{metric_card(f"{primary:,}", "F_geo-supported binary cells in the unique research TIFF")}{metric_card("PASS" if aggregate["holdout_pass_both_modes"] else "FAIL", "registered local hide + block holdout gate")}{metric_card("NOT APPROVED", "weekly competition slot; provenance remains unresolved")}</div>
<div class="two"><section><h2>What was tested</h2><p>The rank field is frozen as <code>F_geo(x) = max(1 − distance / 5 km, 0)</code> around qualified sites. Qualification requires measured discharge temperature ≤30°C, both owner-derived geothermometers ≥100°C and agreement within 20°C. The pre-holdout table audit found {int(result['h58_a']['site_audit']['threshold_qualifying_rows'])} qualifying rows at {int(result['h58_a']['site_audit']['unique_qualified_sites'])} unique raster cells. It is a geochemical hypothesis, not a mapped fault probability.</p><p>The comparison refits View A, View B and their max/union on the same pinned inputs and four spatial folds. All arms share the fold's legal emission pool. H58-A emits only where frozen <code>F_geo &gt; 0</code>; support shortfall is reported and cannot be filled with zero-score cells.</p><p><a class="button secondary" href="h58.html">Open fold tables, assumptions and full audit →</a></p></section>
<section class="card"><h2>Current decision</h2><p><b>Local holdout:</b> {"PASS" if aggregate["holdout_pass_both_modes"] else "FAIL"} in both modes is {"true" if aggregate["holdout_pass_both_modes"] else "false"}.</p><p><b>Artifact checks:</b> {"PASS" if passed_artifacts else "one or more FAILED"}.</p><p><b>Organizer provenance:</b> unresolved. Pinned bytes authenticate the owner mirror against the frozen repository manifest, not against organizer data.</p><p><b>Official performance:</b> no submission/leaderboard score exists in this run.</p></section></div>
<h2>Registered holdout summary</h2>{summary_table}
<p class="small">The required comparison is a mean lift of at least +0.005 and at least 3/4 fold wins in both hide and block, with full same-budget emissions. Catalogue labels are an imperfect proxy; a local pass cannot settle organizer-authenticated performance.</p>
<h2>The rest of the frozen slate</h2><div class="grid">'''
    for item in prereg.get("candidate_slate", []):
        state = "ONLY LOCALLY RUNNABLE" if item.get("id") == "H58-A" else item.get("status", "deferred")
        index_body += f'<section class="card"><h3>{e(item.get("id"))} · {e(item.get("name"))}</h3><p>{e(state)}</p><p class="small">{e(item.get("data_status", item.get("implementation_cost", "")))}</p></section>'
    index_body += '''</div><h2>Evidence and next steps</h2><p>Start with the <a href="h58.html">full H58 audit</a>, then the <a href="executive-summary.html">conditional submission guide</a>. Review the <a href="data/h58_holdout.json">fold-level receipt</a>, <a href="data/h58_result.json">complete run receipt</a>, <a href="data/h58_preregistration.json">frozen protocol</a>, and <a href="data/h58_preflight_integrity.json">input-provenance incident</a> · <a href="data/h58_restore_receipt.json">23-file restore receipt</a> · <a href="data/h58_postrun_review.json">post-run code review</a> · <a href="data/h58_postmerge_uniqueness.json">post-merge uniqueness check</a>. Download the <a href="downloads/'''+e(Path(str(artifact.get("reasoning", {}).get("path", ""))).name)+'''">per-pixel H58-A reasoning CSV</a> or <a href="downloads/'''+e(Path(str(artifact.get("a_only_reasoning", {}).get("path", ""))).name)+'''">A-only diagnostic reasoning CSV</a>. These explanations are hypotheses, not independent geological verification.</p><p>Historical rounds and separate research archives remain available: <a href="h57.html">H57 union arm</a> · <a href="h57-creditcore.html">H57 credited-core alternate (research only)</a> · <a href="downloads/gems57-h57-credit-core25517-plus-novel8000-33517px-zeros.tif" download>H57 alternate TIFF</a> · <a href="h56.html">H56</a> · <a href="h55-paired-shoulders.html">H55 matched holdout</a> · <a href="h55-edge.html">H55-EDGE negative result</a>. They are not this H58 result.</p><div class="live-feed" id="feed">Automatic local evidence feed. The official board is a dated observation, not a live feed.</div>'''
    (DOCS / "index.html").write_text(shell("H58 research overview", "H58-A local catalogue-proxy holdout and audit; research only, not approved for upload.", index_body, "overview"))

    # The complete review page separates local validation, data provenance, and organizer claims.
    holdout_rows = holdout_receipt.get("rows", [])
    raw_arm_names = ("H58-A F_geo", "View A", "View B", "Max(View A, View B)", "A-only diagnostic", "Seeded random")
    mode_detail = []
    for mode in ("hide", "block"):
        mode_detail.append(f'<h3>{e(mode.title())} mode · {"PASS" if modes[mode]["local_research_gate"] else "FAIL"}</h3>')
        mode_detail.append(f'<p>Candidate mean DTI {fmt_dti(modes[mode]["candidate_mean"])}; strongest same-fold single-view/union baseline mean {fmt_dti(modes[mode]["strongest_same_fold_baseline_mean"])}; lift {float(modes[mode]["mean_lift_vs_strongest_same_fold_baseline"]):+.6f}; wins {int(modes[mode]["fold_wins"])}/4; all primary folds budget-comparable: {bool(modes[mode]["all_primary_folds_budget_comparable"])}.</p>')
    pseudo_rows = []
    for fold in pseudo.get("folds", []):
        for rec in fold.get("receivers", []):
            pseudo_rows.append(f'<tr><td>{int(fold["fold"]) + 1}</td><td>{e(rec.get("receiver_view"))}</td><td>{int(rec.get("pseudo_pixels", 0))}</td><td>{e(rec.get("before_dti"))}</td><td>{e(rec.get("after_dti"))}</td><td>{e(rec.get("delta_dti"))}</td></tr>')
    if not pseudo_rows:
        pseudo_rows.append(f'<tr><td colspan="6">{e(pseudo_status)}</td></tr>')
    result_path = f"data/submission_{stem}.json"
    audit_body = f'''{download_bar(artifact, result)}<div class="eyebrow">Independent read-through of the registered execution</div>
<h1>H58-A · holdout, provenance<br>and artifact review.</h1>
{hero_status}<section class="card"><h2>Verdict in one paragraph</h2><p>The emitted TIFF is a fresh, binary inference from the frozen H58-A field, not a copied prior. It was re-opened and locally checked against the sample raster's grid and range. The holdout is a local catalogue-proxy test on the 23-file owner-mirror manifest. {"Even if the local gate passes, the open input-provenance irregularity blocks upload approval and no organizer-authenticated leaderboard gain is established." if aggregate["holdout_pass_both_modes"] else "The registered local gate did not pass, so no research promotion is justified; the open input-provenance irregularity independently blocks upload approval."}</p></section>
<h2>Primary same-input, same-fold comparison</h2>{summary_table}{"".join(mode_detail)}{holdout_table}
<section class="status"><strong>Why the local gate failed:</strong> H58-A emitted {primary:,} / {int(artifact['requested_pixels']):,} requested nodes (shortfall {int(artifact.get('support_shortfall', 0)):,}) despite {int(result['h58_a']['field']['support_pixels']):,} positive <code>F_geo</code> support cells. The frozen five-pixel square local-maximum prefilter leaves essentially the smooth field's site peaks before the three-pixel spacing pass. No zero-score fill, threshold change or post-result rerun was made. The negative DTI lifts above are not comparable-budget estimates; see <a href="data/h58_postrun_review.json">post-run code review</a> and <code>IR-H58-002</code>.</section>
<p>Every arm uses the same fold-specific legal pool and requested budget. Any support shortfall in H58-A or the selected baseline fails that fold's budget comparability; there is no zero-score backfill.</p>
<h2>All primary and secondary score rows</h2><div class="table-wrap"><table><thead><tr><th>Mode</th><th>Fold</th><th>Budget</th><th>Arm</th><th>Requested</th><th>Emitted</th><th>Shortfall</th><th>DTI</th><th>Legal cells</th><th>Truth prevalence</th></tr></thead><tbody>'''
    for row in holdout_rows:
        if row.get("budget_label") not in ("primary", "secondary"):
            continue
        audit_body += f'<tr><td>{e(row["mode"])}</td><td>{int(row["fold"]) + 1}</td><td>{e(row["budget_label"])}</td><td>{e(row["arm"])}</td><td>{int(row["requested_budget"]):,}</td><td>{int(row["emitted"]):,}</td><td>{int(row["support_shortfall"]):,}</td><td>{float(row["dti"]):.6f}</td><td>{int(row["legal_pixels"]):,}</td><td>{100*float(row["actual_truth_prevalence"]):.4f}%</td></tr>'
    audit_body += f'''</tbody></table></div>
<h2>Protocol and spatial leakage safeguards</h2><ul><li>Whole 8-connected catalogue components are assigned to their majority quadrant and held whole. If a component assigned elsewhere crosses into a block's scored quadrant, the entire component is quarantined from that fold's training and visible mask but not added to its truth.</li><li>Both positive and negative training samples stay within the fold's fit region; negative clearance sees only labels visible inside fit.</li><li>Hide truth is sampled at 0.2% of the full valid scored region; block truth at 0.2% of the quadrant plus three-pixel metric halo. The fold-level receipt records realized prevalence.</li><li>An 80-pixel buffer protects block evaluation from adjacent training. Error-dependence statistics use spatial blocks and catalogue-zero proxy negatives; insufficient/undefined/highly correlated errors fail closed for pseudo-label exchange.</li></ul>
<h2>Co-training diagnostic, separate from H58-A</h2><p>OOF error blocks: {int(independence.get("n_blocks", 0))} usable; maximum absolute correlation {e(independence.get("max_abs_correlation"))}; exchange allowed: {bool(independence.get("allow_exchange"))}. {e(pseudo_status)} Any pseudo-label experiment is diagnostic only and is not used in H58-A's geochemical rank field.</p><p class="status"><strong>Pseudo-AUC limitation (IR-H58-003):</strong> post-run review found the proxy-negative clearance used five iterations of the default cross-shaped dilation, not a Euclidean 500 m radius. The saved AUC values do not meet the preregistered mask definition and are exploratory only; they do not support a co-training conclusion. The primary hide/block gate is independent of these values.</p><div class="table-wrap"><table><thead><tr><th>Outer fold</th><th>Receiver</th><th>Pseudo pixels</th><th>Before DTI</th><th>After DTI</th><th>Change</th></tr></thead><tbody>{''.join(pseudo_rows)}</tbody></table></div>
<h2>Artifact integrity and scope</h2><div class="table-wrap"><table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>{gate_rows}</tbody></table></div>
<p>File: <code>{e(name)}</code> · submission name: <code>{e(artifact.get("submission_name"))}</code> · SHA-256: <code>{e(artifact["sha256"])}</code> · bytes: {int(artifact["bytes"]):,} · output cells: {primary:,} / {int(artifact["requested_pixels"]):,} requested.</p>
<p>The run-time decoded-pattern receipt checked {int(unique.get("n_priors_checked", 0))} accessible aligned prior rasters. After merging upstream H57 research files, a supplemental byte/grid check also compared the H58 pattern with the newly added H57 credited-core raster (zero support intersection); see <a href="data/h58_postmerge_uniqueness.json">post-merge check</a>. Canonical exact-pattern unique: {canonical_unique}. The separate support-novelty diagnostic is {"PASS" if unique.get("support_novelty_gate_ok") else "FAIL"}; it is disclosed independently from exact decoded-pattern uniqueness. Private/unlinked submissions were not checked. Same-budget OOF decoded comparisons are recorded in the result receipt.</p>
<h2>Data provenance — the hard blocker</h2><p>All {len(result.get("manifest_inputs", []))} manifest members match the owner-supplied byte/SHA pins. The manifest itself is SHA-bound to the preregistration. This proves consistency with this repository's mirror only. The preflight comparison found material differences between tracked TIFFs and staged copies; it does not resolve which bytes are organizer-intended. <code>IR-H58-001</code> remains open and critical. Do not upload, spend a weekly slot, or call a local lift an organizer leaderboard gain.</p>
<h2>Four preregistered hypotheses</h2><ol>'''
    for item in prereg.get("candidate_slate", []):
        audit_body += f'<li><strong>{e(item.get("id"))} · {e(item.get("name"))}.</strong> {e(item.get("data_status", item.get("status")))}</li>'
    audit_body += f'''</ol><p>H58-A alone was runnable from the current staged mirror. Raw chemistry and the paleo-feature archive were not downloaded/validated for H58-C and H58-D; H58-B was deferred. No result is claimed for those candidates.</p>
<p>Full files: <a href="data/h58_holdout.json">H58 holdout</a> · <a href="data/h58_result.json">full result</a> · <a href="{e(result_path)}">per-artifact receipt</a> · <a href="data/h58_preregistration.json">frozen registry</a> · <a href="data/h58_preflight_integrity.json">input preflight</a> · <a href="data/h58_restore_receipt.json">restore receipt</a> · <a href="data/h58_postrun_review.json">post-run review</a> · <a href="data/h58_postmerge_uniqueness.json">post-merge uniqueness check</a> · <a href="downloads/{e(Path(str(artifact['reasoning']['path'])).name)}">H58-A reasoning CSV</a> · <a href="downloads/{e(Path(str(artifact['a_only_reasoning']['path'])).name)}">A-only reasoning CSV</a></p>'''
    (DOCS / "h58.html").write_text(shell("H58 holdout and provenance audit", "Fold-level H58-A catalogue-proxy holdout, matched baselines, input provenance and TIFF validation.", audit_body, "audit"))

    guide_body = f'''{download_bar(artifact, result)}<div class="eyebrow">Executive summary · explicit submission status</div>
<h1>How to submit—<br>and why not to yet.</h1>
<div class="status"><strong>Do not upload this TIFF or spend a weekly slot.</strong> It is a research artifact only. The input-provenance irregularity <code>IR-H58-001</code> remains open, organizer authentication is unresolved, and no organizer score exists. {e(reasons)}</div>
<p class="lede">The direct download and ZIP below are one click away for review and reproduction. They are not upload approval.</p>
<section class="card"><h2>Artifact identification (for audit, not a current submission)</h2><p><b>File:</b> <code>{e(name)}</code></p><p><b>Unique submission label:</b> <code>{e(artifact.get("submission_name"))}</code></p><p><b>SHA-256:</b> <span class="mono">{e(artifact["sha256"])}</span></p><p><b>Format:</b> one-band float32, EPSG:32611, 3,292 × 3,730, finite values in [0,1]; local sample-template check: {"PASS" if artifact.get("format_gate", {}).get("ok") else "FAIL"}.</p><label for="submission-note">Portal note for this research artifact ({len(note)}/200 characters). Do not paste into the portal while approval is closed.</label><textarea id="submission-note" readonly>{e(note)}</textarea><button data-copy="submission-note">Copy research note</button><p class="small">Canonical output: <code>{e(name)}</code>. Short download: <code>h58-candidate.tif</code>. The ZIP contains exactly one TIFF. Neither is authorized for upload.</p></section>
<h2>What to do now</h2><ol><li><strong>Do not submit.</strong> No portal interaction or weekly slot use occurred in this run.</li><li>Resolve <code>IR-H58-001</code>: establish organizer-authenticated input provenance and label alignment. A matching owner-mirror SHA manifest is not that resolution.</li><li>Review the registered hide/block fold comparisons and all artifact checks on the <a href="h58.html">H58 audit page</a>. The local catalogue proxy is not organizer validation.</li><li>Only after provenance is resolved and an independent review records approval should a new gate decision be made. If any protocol/input/code/artifact changes, rerun and re-audit before reconsidering a slot.</li></ol>
<h2>Conditional portal steps—only after written approval</h2><ol><li>Open the official <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS competition page</a> using the registered eligible team account.</li><li>Download the exact audited <code>.tif</code> from the research link above (or its one-TIFF ZIP). Do not reproject, rescale, recompress or edit it; verify the SHA-256 first.</li><li>On the competition's submission form, choose the GeoTIFF (or one-TIFF ZIP) in <b>File to submit</b>. Use the exact submission label above if a name field is offered.</li><li>Paste the concise note above in the optional note field, but only if the later review authorizes this exact artifact. Verify the portal response before treating anything as submitted.</li><li>Record the returned submission ID, organizer score, timestamp and exact file hash. Do not infer a leaderboard result from this local holdout.</li></ol>
<div class="status"><strong>Current action: none.</strong> This page is an audit guide, not a submission command. Slots used: {int(result.get("submission_slots_used", 0))}.</div><p><a href="h58.html">Full H58 audit →</a> · <a href="data/h58_result.json">Machine-readable run receipt</a> · <a href="data/h58_preflight_integrity.json">Input-provenance review</a> · <a href="data/h58_postrun_review.json">Post-run code review</a></p>'''
    (DOCS / "executive-summary.html").write_text(shell("H58 conditional submission guide", "Exact H58 research-file identification and conditional portal steps; do not upload before provenance resolution and approval.", guide_body, "guide"))

    downloads_dir = DOCS / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    downloads_html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="One-click H58 research downloads with explicit no-upload status and audited filename/hash."><title>H58 research downloads · GEMSDOE52</title><link rel="stylesheet" href="../style.css"></head><body><a class="skip" href="#main">Skip to downloads</a><header>{nav("downloads")}</header><main id="main">{download_bar(artifact, result, short=False)}<div class="eyebrow">One-click research files</div><h1>H58-A downloads<br>are not approval.</h1><div class="status"><strong>NOT APPROVED TO SUBMIT — DO NOT UPLOAD.</strong> Input provenance remains unresolved; the local holdout cannot establish organizer-authenticated gain.</div><p>Unique TIFF: <code>{e(name)}</code><br>SHA-256: <code>{e(artifact["sha256"])}</code><br>Portal note ({len(note)} chars, conditional only): <code>{e(note)}</code></p><p><a href="{e(name)}" download>Download the audited research TIFF</a> · <a href="h58-candidate.tif" download>Short TIFF link</a> · <a href="h58-candidate.zip" download>One-TIFF ZIP</a> · <a href="{e(Path(str(artifact['reasoning']['path'])).name)}">H58-A reasoning CSV</a> · <a href="../h58.html">Full audit</a></p><p>Historical artifacts remain linked from the <a href="../index.html">overview</a> · <a href="../h57-creditcore.html">H57 credited-core alternate (research-only archive)</a> · <a href="../h55-edge.html">H55-EDGE negative-result archive</a>. They are not this H58 output.</p></main></body></html>'''
    (downloads_dir / "index.html").write_text(downloads_html)

    print(f"Published receipt-driven H58 overview, audit and conditional submission guide for {name}")


if __name__ == "__main__":
    main()
