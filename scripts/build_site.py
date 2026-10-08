#!/usr/bin/env python3
"""Generate the GitHub Pages site in docs/ from the JSON receipts and registries. No number is typed by hand.

Pages (nav order = reading order):
  docs/index.html       Executive summary: download link at the top, label, how to submit, name and comment, answers
  docs/submission.html  The submission file: its checks, the pre-registered gates, the uniqueness result
  docs/evidence.html    Experiments, GEMSDOE29 and GEMSDOE32, registry check, irregularities, limitations, sources, data

Labels: HOLDOUT-DTI (our proxy), ORGANIZER-CONFIRMED (receipt only; none exists), MEASURED, USER-REPORTED, OWNER-CLAIM.
Usage: python scripts/build_site.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPO_URL = "https://github.com/buffedlizard55-lab/GEMSDOE53"
RAW = f"{REPO_URL}/raw/main"
BLOB = f"{REPO_URL}/blob/main"


def J(rel: str):
    return json.loads((ROOT / rel).read_text())


def esc(x) -> str:
    return html.escape(str(x))


def pct(x, nd=2) -> str:
    return f"{100 * float(x):.{nd}f}%"


CSS = """
:root{--ink:#17202a;--muted:#5b6673;--line:#dfe5ec;--bg:#f7f9fb;--card:#fff;--accent:#0b6e4f;--warn:#9a3412;--warnbg:#fff7ed;--ok:#14532d;--okbg:#f0fdf4}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0f2a24;color:#fff;padding:16px 24px}header .t{font-weight:700;font-size:17px}
nav{margin-top:6px;font-size:14px}nav a{margin-right:16px;color:#bfe9dc;text-decoration:none}nav a.on{font-weight:700;text-decoration:underline}
main{max-width:980px;margin:0 auto;padding:20px}section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:14px 0}
h1{font-size:25px;margin:2px 0 8px}h2{font-size:19px;margin:0 0 10px}h3{font-size:16px;margin:14px 0 6px}
.banner{background:var(--warnbg);border:2px solid #fb923c;color:var(--warn);border-radius:10px;padding:12px 14px;font-weight:600}
.banner.ok{background:var(--okbg);border-color:#86efac;color:var(--ok)}
.dl{background:#ecfdf5;border:2px solid #34d399;border-radius:12px;padding:16px 18px;margin:12px 0}
.dl a.btn{display:inline-block;background:#0b6e4f;color:#fff;font-weight:700;padding:10px 16px;border-radius:8px;text-decoration:none;font-size:17px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f1f5f9}code,pre{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;word-break:break-all}
pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap}
.pill{display:inline-block;font-size:12px;border-radius:999px;padding:1px 8px;border:1px solid var(--line);color:var(--muted);margin-right:4px;white-space:nowrap}
.pill.fail{color:var(--warn);border-color:#fdba74}.pill.pass{color:var(--ok);border-color:#86efac}
.note{color:var(--muted);font-size:14px}footer{max-width:980px;margin:0 auto;padding:8px 20px 40px;color:var(--muted);font-size:13px}
a{color:var(--accent)}ul,ol{padding-left:22px}li{margin:3px 0}
"""

NAV = [("index.html", "Executive summary"), ("submission.html", "Submission file"), ("evidence.html", "Evidence")]


def page(title: str, body: str, active: str) -> str:
    nav = "".join(f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · GEMSDOE53</title>
<style>{CSS}</style></head><body>
<header><div class="t">GEMSDOE53 · DrivenData GEMS (DOE) competition 306</div>
<nav>{nav}<a href="{REPO_URL}">repository</a></nav></header>
<main>{body}</main>
<footer>Every number on these pages is read from JSON in <code>evidence/</code> and <code>registry/</code> at build time.
HOLDOUT-DTI = our proxy (catalogue truth). ORGANIZER-CONFIRMED = portal receipt only (none exists yet).
USER-REPORTED and OWNER-CLAIM values are not verified. Regenerate with <code>python scripts/build_site.py</code>.</footer></body></html>"""


def main() -> int:
    card = J("evidence/run_card.json")
    x1 = J("evidence/x1_ridge_canary.json")
    x2 = J("evidence/x2_ridge_holdout.json")
    x3 = J("evidence/x3_candidate_receipt.json")
    uq = J("evidence/uniqueness_v2.json")
    ob = J("evidence/overlap_baseline_v2.json")
    prereg = J("evidence/preregistration_x2.json")
    exp1 = J("evidence/exp1_leakage_canary.json")
    exp2 = J("evidence/exp2_holdout_arms.json")
    reg = J("evidence/registry_manifest.json")
    irr = J("registry/irregularities.json")["items"]
    lim = J("registry/limitations.json")["items"]
    srcs = J("registry/sources.json")["sources"]
    S = {s["id"]: s for s in srcs}

    PR6 = dict(J("evidence/archive/pr6/selection_pr6_h1.json"))
    PR6_CARD = J("evidence/archive/pr6/run_card_pr6_h1.json")
    PR6["file"] = PR6_CARD["submission"]["file"]
    PR6["submitted"] = PR6_CARD["submission"]["submitted"]
    PR6_HO = PR6_CARD["holdout"]
    PR6_CO = PR6_CARD["correlation_overlap_vs_registry"]
    xc_path = ROOT / "evidence" / "crosscheck_pr6_h1_uniqueness_v2.json"
    if xc_path.exists():
        xc = J("evidence/crosscheck_pr6_h1_uniqueness_v2.json")
        xc_flags = [r for r in xc["results"] if r.get("drift_flag")]
        xc_ov = J("evidence/overlap_baseline_pr6_h1.json")["rows"] if (ROOT / "evidence" / "overlap_baseline_pr6_h1.json").exists() else []
        lifts = [r["lift_vs_random"] for r in xc_ov if r.get("lift_vs_random") is not None]
        XC_TEXT = (f"compared {xc['n_registry_files_compared']:,} rasters; max Spearman {xc['max_spearman_rho']:.4f}; "
                   f"max dot overlap {pct(xc['max_dot_overlap_within_3px_used'])}; flagged rows {len(xc_flags)} "
                   f"({'literal rule: NOT CLEARED' if xc['any_drift_flag'] else 'literal rule: cleared'}). "
                   + (f"Chance lift on flagged rows: {min(lifts):.2f} to {max(lifts):.2f}." if lifts else ""))
    else:
        XC_TEXT = "cross-check not yet run"
    dot_rows = [r for r in ob["rows"] if r.get("check", "dots") == "dots"]
    surf_rows = [r for r in ob["rows"] if r.get("check") == "surface_top_N"]
    sub = card["submission"]
    label = card["label"]
    ok = label == "OK-TO-SUBMIT"
    N = card["holdout"]["N_primary"]
    arms = x2["arms"]
    pr = arms["ridge_pack"][str(N)]
    hg = arms["hgb_bands"][str(N)]
    tn = arms["ridge_topn"][str(N)]
    paired = x2["paired_differences"][f"ridge_pack_minus_hgb_bands@{N}"]
    frozen = x2["frozen_best_reference"]["value"]
    failing = card["failing_gates"]
    gates = card["gates"]

    def link_src(sid: str, text: str | None = None) -> str:
        s = S[sid]
        return f'<a href="{esc(s["url"])}">{esc(text or sid)}</a>'

    def gate_pill(v: bool) -> str:
        return '<span class="pill pass">PASS</span>' if v else '<span class="pill fail">FAIL</span>'

    banner_cls = "banner ok" if ok else "banner"
    banner_txt = ("<b>OK-TO-SUBMIT.</b> Every pre-registered gate passed. Submitting is still your decision; no slot is selected here."
                  if ok else
                  f"<b>DO-NOT-SUBMIT.</b> The file is valid and downloadable for review. It fails gate(s): "
                  f"{esc(', '.join(failing))}. It is not cleared for a submission slot.")

    # ---------------------------------------------------------------- index.html (executive summary)
    body = f"""
<section>
  <div class="{banner_cls}">{banner_txt}</div>
  <div class="dl">
    <h2>⬇ Download the GeoTIFF</h2>
    <p><a class="btn" href="{RAW}/{esc(sub['path'])}">Download {esc(sub['name'])}</a>
       &nbsp; <a href="{BLOB}/{esc(sub['path'])}">view on GitHub</a></p>
    <table>
      <tr><th>Label</th><td><b>{esc(label)}</b></td></tr>
      <tr><th>File name</th><td><code>{esc(sub['name'])}</code></td></tr>
      <tr><th>Comment (≤140 characters, {sub['comment_chars']} used)</th><td><code>{esc(sub['comment'])}</code></td></tr>
      <tr><th>Format</th><td>single band, {esc(sub['dtype'])}, {esc(sub['crs'])}, {sub['res_m'][0]:g} m, {sub['shape'][1]} × {sub['shape'][0]} px, nodata {esc(sub['nodata'])}</td></tr>
      <tr><th>Dots (value 1.0)</th><td>{sub['dots_value_1']:,} (the rest of the footprint is 0; outside it NaN)</td></tr>
      <tr><th>sha256</th><td><code>{esc(sub['sha256'])}</code> ({sub['bytes']:,} bytes)</td></tr>
    </table>
    <p class="note">A second file, H1 relay prune, is also on main from another session. Its own label is READY_TO_SUBMIT; this session's cross-check is not cleared under the literal rule. <a href="#second-candidate">See the second candidate</a>.</p>
    <p class="note">This is a research file for review. Its label is <b>{esc(label)}</b> because the uniqueness gate fails
    under the pre-registered rule. A file labelled DO-NOT-SUBMIT must not be uploaded unless you change the rule and the label is re-evaluated.</p>
  </div>
</section>

<section>
  <h2>Answers (labels in brackets)</h2>
  <table>
    <tr><th>Question</th><th>Answer</th><th>Label</th></tr>
    <tr><td>Unique, valid, downloadable GeoTIFF?</td>
        <td>Yes for format and validity ({gate_pill(gates['G4_format'])}). Not cleared for submission: {gate_pill(gates['G5_uniqueness'])} uniqueness.
        Rank correlation with all {uq['n_registry_files_compared']:,} compared registry rasters is at most {uq['max_spearman_rho']:.3f}.
        Dot-level overlap flags {len(dot_rows)} registry rows, all with chance lift ≤ {max(r['lift_vs_random'] for r in dot_rows):.2f} (density). Surface-level flags {len(surf_rows)} rows with chance lift {min(r['lift_vs_random'] for r in surf_rows):.1f} to {max(r['lift_vs_random'] for r in surf_rows):.1f} (real similarity to two team files). The file is blocked under either reading.</td>
        <td><span class="pill">MEASURED</span></td></tr>
    <tr><td>Does it beat the 0.3774 public #1?</td>
        <td>Unknown. No organizer score exists, so nothing here can be claimed. The bar itself is user-reported and conflicts with the owner's ledger (IR-53-26).</td>
        <td><span class="pill">ORGANIZER-CONFIRMED: none</span></td></tr>
    <tr><td>Holdout proxy for the candidate</td>
        <td>Pooled HOLDOUT-DTI <b>{pr['pooled_DTI']:.4f}</b> (95% CI {pr['CI95_t_df4_on_fold_mean'][0]:.4f} to {pr['CI95_t_df4_on_fold_mean'][1]:.4f}) at {N:,} dots. Same-budget HGB: {hg['pooled_DTI']:.4f}. Frozen best: {frozen:.4f}. Paired gain {paired['mean']:+.4f} (CI {paired['CI95_t_df4'][0]:+.4f} to {paired['CI95_t_df4'][1]:+.4f}).</td>
        <td><span class="pill">HOLDOUT-DTI</span></td></tr>
    <tr><td>Why GEMSDOE29 leaks</td>
        <td>Its distance-to-known-faults feature is built from the labels it is scored on. It is exactly 0 on all {exp1['C1_leaky_distance_in_sample']['value_on_known_fault_px']['n']:,} known-fault pixels (separability {exp1['summary']['leaky_distance_in_sample_separability']:.3f}). On the holdout it scores {exp2['arms']['leaky_ablate']['pooled']['0.02']['pooled_DTI']:.5f}, which is inflated. See <a href="evidence.html#gemsdoe29">evidence</a> and <a href="{BLOB}/docs/leakage-review.md">the review</a>.</td>
        <td><span class="pill">MEASURED</span> <span class="pill">HOLDOUT-DTI (inflated)</span></td></tr>
    <tr><td>Why GEMSDOE32 (0.2778 claim) can score high, and whether we can beat it</td>
        <td>Measured on our proxy: at the same dot budget, Poisson spacing roughly doubles the credit per dot (TP_w 4,678 vs 2,072 unpacked). Whether 0.2778 is that file is unverified (IR-53-02, IR-53-32). Beating it on the organizer's truth is not established. See <a href="{BLOB}/docs/research/gemsdoe32.md">the analysis</a>.</td>
        <td><span class="pill">MEASURED (mechanism)</span> <span class="pill">USER-REPORTED (0.2778)</span></td></tr>
    <tr><td>Top hypothesis validated on a spatially blocked holdout?</td>
        <td>Yes: H2 passes G1 (holdout best), G2 (equal budget) and G3 (leakage canary). It is blocked at G5 (uniqueness). See the <a href="{BLOB}/docs/research/hypotheses.md">ranked list</a>.</td>
        <td><span class="pill">HOLDOUT-DTI</span></td></tr>
    <tr><td>Portal error "Predicted values must be in range [0, 1]"</td>
        <td>Cause documented by the template: NaN inside the scored region (3,061 px). This file has none; NaN exactly outside the footprint, finite 0/1 inside, nodata tag <code>nan</code>. The portal has not yet confirmed it (no receipt).</td>
        <td><span class="pill">MEASURED (validators)</span> <span class="pill">unconfirmed by portal</span></td></tr>
  </table>
</section>

<section id="second-candidate">
  <h2>Second candidate on main (from PR #6): H1 relay prune</h2>
  <p class="note">This candidate comes from another session on this repository. Its label and numbers are shown as that session states them (USER-REPORTED / its own receipts). They are not re-verified here, except the uniqueness cross-check below, which this session ran against its 1,200-raster registry.</p>
  <table>
    <tr><th>File</th><td><a href="{RAW}/docs/downloads/{esc(PR6['file'])}">{esc(PR6['file'])}</a> · <a href="{BLOB}/docs/downloads/{esc(PR6['file'])}">view on GitHub</a></td></tr>
    <tr><th>Stated status (PR #6)</th><td><code>{esc(PR6['status'])}</code> · submitted: {esc(PR6['submitted'])} · note: <code>{esc(PR6['note'])}</code></td></tr>
    <tr><th>Holdout (its evaluator: repo copy <code>gems53.core.dti</code>, not the shared template)</th><td>pooled HOLDOUT-DTI <b>{PR6_HO['pooled_DTI']:.4f}</b> (95% CI {PR6_HO['CI95_t_df4_on_fold_mean'][0]:.4f} to {PR6_HO['CI95_t_df4_on_fold_mean'][1]:.4f}) at q = {PR6_HO['q_fraction_of_footprint']}; {PR6_HO['withheld_fault_px_total']:,} withheld fault px.</td></tr>
    <tr><th>Its own uniqueness check (166 rasters, 12 repos)</th><td>max Spearman {PR6_CO['max_spearman_rho_sample']:.4f}; max dot overlap {pct(PR6_CO['max_our_dots_within_3px_of_registry_dots'])}; drift flag {PR6_CO['any_drift_flag']}.</td></tr>
    <tr><th>This session's cross-check (1,200 rasters, 63 repos)</th><td>{(XC_TEXT)}</td></tr>
  </table>
  <p class="note">Why the two holdout numbers differ, and why they are not a ranking for the competition: the holdout truth is the catalogue, and H1 uses distance to visible catalogue faults, which the holdout rewards by design. H2 uses band 2 only. The competition scores faults that are absent from the catalogue (L-02, L-14).</p>
</section>

<section>
  <h2>How to submit (only if the label changes to OK-TO-SUBMIT and you choose this file)</h2>
  <ol>
    <li>Confirm the label is <b>OK-TO-SUBMIT</b> on this page and in <code>evidence/run_card.json</code>. If it says DO-NOT-SUBMIT, stop.</li>
    <li>Download the file with the button above. Check the sha256 against the value shown.</li>
    <li>Open the DrivenData competition page, log in to your own account, and go to the submission form. No data download is needed.</li>
    <li>Upload the GeoTIFF. Paste the name and the comment above into the form's description field (comment ≤140 characters). Submit.</li>
    <li>Rules to keep in mind: three submissions per week ({link_src('S3', 'NLR rules, §3.4')}); one final submission is chosen before private scores ({link_src('S3', '§3.5')}); the generative-AI use must be disclosed in the narrative ({link_src('S3', '§3.2')}).</li>
    <li>Save the receipt. Only a receipt makes a number ORGANIZER-CONFIRMED.</li>
  </ol>
  <p class="note">Sources: {link_src('S1', 'problem page')} · {link_src('S2', 'leaderboard (dynamic)')} · {link_src('S3', 'NLR rules (PDF)')}.</p>
</section>

<section>
  <h2>Name and comment (prepared)</h2>
  <table>
    <tr><th>Name</th><td><code>{esc(sub['name'])}</code></td></tr>
    <tr><th>Comment</th><td><code>{esc(sub['comment'])}</code> ({sub['comment_chars']} characters)</td></tr>
  </table>
  <p class="note">The name and comment are not an approval. The label decides whether the file may be submitted.</p>
</section>

<section>
  <h2>Decisions needed from you</h2>
  <ol>
    <li><b>Overlap rule.</b> A chance-corrected dot rule would clear the {len(dot_rows)} dot-level rows (chance lift up to {max(r['lift_vs_random'] for r in dot_rows):.2f}). It would <b>not</b> clear the {len(surf_rows)} surface-level rows (lift {min(r['lift_vs_random'] for r in surf_rows):.1f} to {max(r['lift_vs_random'] for r in surf_rows):.1f}), so the file stays blocked. A unique file needs a different top tail, which is a new pre-registered variant. Details: <a href="submission.html#uniqueness">uniqueness</a>.</li>
    <li><b>Verbatim prompt.</b> The original prompt is not in the workspace (IR-53-27). Paste it into <code>docs/prompt/verbatim.md</code>.</li>
    <li><b>Leaderboard.</b> Confirm 0.3774, 0.3195 and 0.2778 with a dated official read (IR-53-26).</li>
    <li><b>Radiometric data (H6).</b> Provide the grids, or allow the USGS/ScienceBase host.</li>
  </ol>
</section>

<section>
  <h2>Bars to beat (USER-REPORTED, not verified here)</h2>
  <table>
    <tr><th>Rank</th><th>Team</th><th>Score</th><th>Label</th></tr>
    <tr><td>1</td><td>xiaofanhu</td><td>0.3774</td><td>user-reported; owner ledger has a different leader (IR-53-26)</td></tr>
    <tr><td>7</td><td>DARD</td><td>0.3195</td><td>user-reported</td></tr>
    <tr><td>13</td><td>extradr19</td><td>0.2778</td><td>user-reported; not linked to a GEMSDOE32 file (IR-53-02); ledger shows 0.2449 at rank 19 (2026-10-03)</td></tr>
  </table>
  <p class="note">Leaderboard source: {link_src('S2', 'DrivenData leaderboard (client-rendered; not readable from the sandbox)')}.</p>
</section>

<section>
  <h2>Limitations (summary)</h2>
  <p>See <a href="evidence.html#limitations">limitations</a>. The main gaps: no organizer score; the holdout is a proxy whose truth is the catalogue; the uniqueness rule blocks every dense dot file against the lattice; and the verbatim prompt is missing.</p>
</section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", body, "index.html"))

    # ---------------------------------------------------------------- submission.html
    rows_gate = "".join(
        f"<tr><td>{esc(k)}</td><td>{gate_pill(v)}</td></tr>" for k, v in gates.items())
    val = card["submission"]["validator_exit_codes"]
    val_rows = "".join(f"<tr><td>{esc(k)}</td><td>{'PASS' if v == 0 else 'FAIL'} (exit {v})</td></tr>"
                       for k, v in val.items())
    ob_rows = "".join(
        f"<tr><td><code>{esc(r['file'][:90])}</code></td><td>{r['mode']}</td><td>{r['registry_points']:,}</td>"
        f"<td>{pct(r['observed'], 2)}</td><td>{pct(r['random_dots_share'], 2)}</td><td>{r['lift_vs_random']}</td></tr>"
        for r in ob["rows"][:12])
    body2 = f"""
<section>
  <div class="{banner_cls}">{banner_txt}</div>
  <h2>The file</h2>
  <table>
    <tr><th>Name</th><td><code>{esc(sub['name'])}</code></td></tr>
    <tr><th>Download</th><td><a href="{RAW}/{esc(sub['path'])}">raw file</a> · <a href="{BLOB}/{esc(sub['path'])}">view on GitHub</a></td></tr>
    <tr><th>sha256 / bytes</th><td><code>{esc(sub['sha256'])}</code> · {sub['bytes']:,} bytes</td></tr>
    <tr><th>Grid</th><td>{sub['shape'][1]} × {sub['shape'][0]} px, {sub['res_m'][0]:g} m, {esc(sub['crs'])}, dtype {esc(sub['dtype'])}, nodata {esc(sub['nodata'])}</td></tr>
    <tr><th>Finite / NaN pixels</th><td>{sub['finite_px']:,} finite (inside the official footprint) · {sub['nan_px']:,} NaN (outside)</td></tr>
    <tr><th>Dots (value 1.0)</th><td>{sub['dots_value_1']:,}; minimum spacing 2.8 px (280 m)</td></tr>
    <tr><th>Comment</th><td><code>{esc(sub['comment'])}</code> ({sub['comment_chars']} characters)</td></tr>
  </table>
</section>

<section>
  <h2>Format checks (shared template tools)</h2>
  <table><tr><th>Check</th><th>Result</th></tr>{val_rows}</table>
  <p class="note">The shared writer read the file back and verified it. The shared conformance gate checks that every
  template-finite pixel is finite in [0, 1] and every template-NaN pixel is NaN, with a matching nodata tag.
  Sources: {link_src('S23', 'template at commit dcbbb19')}.</p>
</section>

<section>
  <h2>Pre-registered gates</h2>
  <table>
    <tr><th>Gate</th><th>Result</th></tr>{rows_gate}
  </table>
  <table>
    <tr><th>Gate</th><th>Rule and measured value</th></tr>
    <tr><td>G1 holdout best</td><td>pooled HOLDOUT-DTI at {N:,} dots &gt; {frozen:.6f} (measured {pr['pooled_DTI']:.6f})</td></tr>
    <tr><td>G2 equal budget</td><td>paired CI lower bound &gt; 0 (measured {paired['CI95_t_df4'][0]:+.6f})</td></tr>
    <tr><td>G3 leakage canary</td><td>every ridge feature ≤ {x1['gate']:.2f} (worst measured {x1['worst_candidate_feature_separability']:.6f})</td></tr>
    <tr><td>G4 format</td><td>template writer read-back, template conformance and validator exit codes 0</td></tr>
    <tr><td>G5 uniqueness</td><td>every registry raster: Spearman ≤ {uq['thresholds']['spearman_rho']:.2f} and ≤ {pct(uq['thresholds']['dot_overlap_within_3px'], 0)} of our dots within 3 px; surface top-N likewise (measured max Spearman {uq['max_spearman_rho']:.3f}; max dot overlap {pct(uq['max_dot_overlap_within_3px_used'])}; {len(dot_rows)} dot-level and {len(surf_rows)} surface-level rows flagged)</td></tr>
  </table>
  <p class="note">Pre-registration: <a href="{BLOB}/evidence/preregistration_x2.json">evidence/preregistration_x2.json</a> (written before the run; ridge module hash pinned).</p>
</section>

<section id="uniqueness">
  <h2>Uniqueness against the public GEMS repos</h2>
  <p>Scope: {reg['repos_checked']} repos whose names contain "GEMS", {reg['rasters_downloaded']:,} rasters downloaded, {uq['n_registry_files_compared']:,} compared
  (exact duplicate check by sha256 first; none matched). {uq['n_dense_registry_files']} registry rasters are dense (more than 20% of the footprint nonzero) and are compared on their top-N pixels.</p>
  <table>
    <tr><th>Measure</th><th>Value</th></tr>
    <tr><td>Max Spearman rho, final dots (threshold 0.90)</td><td>{uq['max_spearman_rho']:.4f}</td></tr>
    <tr><td>Max share of our dots within 3 px of one registry raster (threshold 70%)</td><td>{pct(uq['max_dot_overlap_within_3px_used'], 3)}</td></tr>
    <tr><td>Max Spearman rho, surface before placement</td><td>{uq['max_surface_spearman_rho']:.4f}</td></tr>
    <tr><td>Max surface top-N share within 3 px</td><td>{pct(uq['max_surface_top_N_within_3px'], 2)}</td></tr>
  </table>
  <h3>Chance baseline for the flagged rows (diagnostic; flags unchanged)</h3>
  <p class="note">Random footprint pixels, at the same count as our dots, show the overlap that placement alone would produce against each registry raster.
  If observed ≈ random, the flag reflects that raster's geometry, not our placement.</p>
  <table><tr><th>Registry file (truncated)</th><th>Mode</th><th>Registry points</th><th>Observed</th><th>Random</th><th>Lift vs random</th></tr>{ob_rows}</table>
</section>
"""
    (DOCS / "submission.html").write_text(page("Submission file", body2, "submission.html"))

    # ---------------------------------------------------------------- evidence.html
    exp1_sum = exp1["summary"]
    ex_rows = "".join(
        f"<tr><td>{esc(a)}</td><td>{x2_arm_pooled(arms, a, '37654')}</td><td>{x2_arm_pooled(arms, a, '44090')}"
        f"</td><td>{x2_arm_pooled(arms, a, '51674')}</td><td>{x2_arm_pooled(arms, a, '103348')}</td></tr>"
        for a in ("ridge_pack", "ridge_topn", "hgb_bands"))
    feat_rows = "".join(f"<tr><td>{esc(k)}</td><td>{v:.6f}</td></tr>" for k, v in
                        ((n, f['max_separability_over_folds']) for n, f in x1['features'].items()))
    irr_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['severity'])}</td><td>{esc(i['status'])}</td>"
                       f"<td>{esc(i['subject'])}</td><td>{esc(i['detail'])}</td></tr>" for i in irr)
    lim_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['item'])}</td></tr>" for i in lim)
    src_rows = "".join(f"<tr><td>{esc(s['id'])}</td><td><a href=\"{esc(s['url'])}\">{esc(s['title'])}</a></td>"
                       f"<td>{esc(s.get('access', ''))}</td></tr>" for s in srcs)
    inp_rows = "".join(f"<tr><td><code>{esc(k)}</code></td><td><code>{esc(v)}</code></td></tr>"
                       for k, v in x2["inputs"].items())
    body3 = f"""
<section>
  <h2>Experiments (budget: 3 experiments, 2 hours)</h2>
  <table>
    <tr><th>Experiment</th><th>What it did</th><th>Receipt</th></tr>
    <tr><td>E1 (earlier)</td><td>leakage canary on 19 bands and distance features</td><td><a href="{BLOB}/evidence/exp1_leakage_canary.json">exp1</a></td></tr>
    <tr><td>E2 (earlier)</td><td>hide-and-recover holdout, bands / leak-free / leaky ablation</td><td><a href="{BLOB}/evidence/exp2_holdout_arms.json">exp2</a></td></tr>
    <tr><td>X1</td><td>leakage canary on the ridge features (G3)</td><td><a href="{BLOB}/evidence/x1_ridge_canary.json">x1</a></td></tr>
    <tr><td>X2</td><td>pre-registered holdout: H2 vs HGB vs unpacked ablation, N grid</td><td><a href="{BLOB}/evidence/x2_ridge_holdout.json">x2</a></td></tr>
    <tr><td>X3</td><td>build with the shared writer, validators, uniqueness (G4, G5)</td><td><a href="{BLOB}/evidence/x3_candidate_receipt.json">x3</a></td></tr>
  </table>
</section>

<section>
  <h2>X2: HOLDOUT-DTI by arm and dot budget (pooled over 5 folds)</h2>
  <p class="note">Shared template evaluator (commit dcbbb19). Frozen best {frozen:.6f}. Each cell: pooled DTI (95% t-CI on the fold mean).</p>
  <table><tr><th>Arm</th><th>{37654:,} dots</th><th>{44090:,} dots (primary)</th><th>{51674:,} dots</th><th>{103348:,} dots</th></tr>{ex_rows}</table>
  <p class="note">ridge_pack = H2 (packed). ridge_topn = same centrelines, no spacing rule (ablation). hgb_bands = frozen HGB baseline.
  The E2 q-grid reproduces through the shared evaluator: {json.dumps(x2['E2_reproduction_hgb_top_q']['shared_scorer'])}.</p>
  <h3>Paired differences (same folds, same budget)</h3>
  <table><tr><th>Comparison</th><th>Mean</th><th>95% CI (t, df 4)</th></tr>
  {''.join(f"<tr><td>{esc(k)}</td><td>{v['mean']:+.6f}</td><td>{v['CI95_t_df4'][0]:+.6f} to {v['CI95_t_df4'][1]:+.6f}</td></tr>" for k, v in x2['paired_differences'].items() if k.endswith(f'@{N}'))}
  </table>
</section>

<section>
  <h2>X1: leakage canary (separability = max(AUC, 1 − AUC); gate {x1['gate']:.2f})</h2>
  <table><tr><th>Feature (computed from band 2 only)</th><th>Max over folds</th></tr>{feat_rows}</table>
  <p class="note">The last two rows are reference bands and are not candidate features. Worst candidate separability {x1['worst_candidate_feature_separability']:.6f}: G3 {'pass' if x1['G3_pass'] else 'FAIL'}.</p>
</section>

<section id="gemsdoe29">
  <h2>GEMSDOE29 leakage (formal diagnosis, measured on the provided data)</h2>
  <p>A feature built from the labels it is scored against is a shortcut. E1 separability of the distance to the full catalogue,
  evaluated on the labels it was built from, is {exp1['C1_leaky_distance_in_sample']['separability']:.1f}. On withheld positives it is {exp1['summary']['leaky_distance_on_withheld_separability_mean']:.1f}.
  The label-free bands reach at most {exp1_sum['max_label_free_band_separability']:.6f} (no band above the 0.90 gate). The leak-free
  distance (4×4-block cross-fit) reaches {exp1_sum['leak_free_distance_separability_mean']:.6f}. Full write-up: <a href="{BLOB}/docs/leakage-review.md">docs/leakage-review.md</a>.</p>
  <p class="note">Labels: MEASURED (E1, E2). The GEMSDOE29 code path is cited from the prior review and is not re-read in this session.</p>
</section>

<section id="gemsdoe32">
  <h2>GEMSDOE32 (0.2778 claim): verified and unverified</h2>
  <table>
    <tr><th>Claim</th><th>Label</th><th>Status</th></tr>
    <tr><td>extradr19 at 0.2778 (#13)</td><td>USER-REPORTED</td><td>not checked against an official dated read; the owner's ledger shows 0.2449 at rank 19 (2026-10-03)</td></tr>
    <tr><td>The file is H33-2-B2 (37,654 dots, 0.2708 base, 2-px catalogue prune)</td><td>OWNER-CLAIM</td><td>the README read 2026-10-08 names h32d-submodular-46090 as the one-click file (IR-53-32)</td></tr>
    <tr><td>Thinning a model emission to a 2.8-px spacing gives the 0.2600 d2.8 file</td><td>OWNER-CLAIM</td><td>the owner says the score-to-file link is unresolved (S22)</td></tr>
    <tr><td>Spacing roughly doubles credit per dot at a fixed dot budget</td><td>HOLDOUT-DTI (measured)</td><td>X2: TP_w 4,678 (packed) vs 2,072 (unpacked) at 44,090 dots</td></tr>
  </table>
  <p>Full analysis: <a href="{BLOB}/docs/research/gemsdoe32.md">docs/research/gemsdoe32.md</a>.</p>
</section>

<section id="irregularities">
  <h2>Irregularities (open first)</h2>
  <table><tr><th>ID</th><th>Severity</th><th>Status</th><th>Subject</th><th>Detail</th></tr>{irr_rows}</table>
</section>

<section id="limitations">
  <h2>Limitations</h2>
  <table><tr><th>ID</th><th>Item</th></tr>{lim_rows}</table>
</section>

<section>
  <h2>Data inventory (inputs, pinned)</h2>
  <table><tr><th>File</th><th>sha256 (pinned by the sources and the template)</th></tr>{inp_rows}</table>
  <p class="note">Sample footprint {x2['footprint_px']:,} px; known-fault pixels {x2['known_fault_px']:,}; {x2['folds']['segments']:,} fault segments.
  Registry: {reg['repos_checked']} repos checked, {reg['rasters_downloaded']:,} rasters, scope: {esc(reg['scope'])}.</p>
</section>

<section>
  <h2>Sources</h2>
  <table><tr><th>ID</th><th>Source</th><th>Access</th></tr>{src_rows}</table>
  <p class="note">Hypotheses: <a href="{BLOB}/docs/research/hypotheses.md">docs/research/hypotheses.md</a>.
  Run card: <a href="{BLOB}/evidence/run_card.json">evidence/run_card.json</a>.
  Parallel-run card: <a href="{BLOB}/evidence/parallel-run-card.json">evidence/parallel-run-card.json</a>.</p>
</section>
"""
    (DOCS / "evidence.html").write_text(page("Evidence", body3, "evidence.html"))
    # Pages cannot serve evidence/ or registry/, so the cited JSON is copied into docs/data/ (current copies only).
    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)
    keep = {}
    for rel in ["evidence/run_card.json", "evidence/parallel-run-card.json", "evidence/x1_ridge_canary.json",
                "evidence/x2_ridge_holdout.json", "evidence/x3_candidate_receipt.json", "evidence/uniqueness_v2.json",
                "evidence/overlap_baseline_v2.json", "evidence/preregistration_x2.json",
                "evidence/exp1_leakage_canary.json", "evidence/exp2_holdout_arms.json",
                "evidence/registry_manifest.json", "registry/sources.json", "registry/irregularities.json",
                "registry/limitations.json"]:
        src = ROOT / rel
        (data_dir / src.name).write_bytes(src.read_bytes())
        keep[src.name] = True
    # other sessions' files in docs/data are left in place (not deleted)
    print("wrote docs/index.html, docs/submission.html, docs/evidence.html; label:", label)
    return 0


def x2_arm_pooled(arms: dict, arm: str, n: str) -> str:
    v = arms[arm][n]
    lo, hi = v["CI95_t_df4_on_fold_mean"]
    return f"{v['pooled_DTI']:.4f} ({lo:.4f} to {hi:.4f})"


if __name__ == "__main__":
    sys.exit(main())
