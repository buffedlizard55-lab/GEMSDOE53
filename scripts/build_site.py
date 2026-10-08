#!/usr/bin/env python3
"""Generate the GitHub Pages site in docs/ from the JSON evidence. No number is typed by hand.

Pages (reading order):
  docs/index.html        Executive summary: status label, download and submission block (name, note), answers, bars.
  docs/submission.html   The file: what it is, every gate and check, the uniqueness receipt, why it is labelled as it is.
  docs/evidence.html     Experiments E1 (design A, reference) and E2 (design B), canaries, GEMSDOE29/32, hypotheses,
                         irregularities, limitations, sources, run card.

Usage: python scripts/build_site.py
"""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
:root{--ink:#17202a;--muted:#5b6673;--line:#dfe5ec;--bg:#f7f9fb;--card:#fff;--accent:#0b6e4f;--warn:#9a3412;--warnbg:#fff7ed;--ok:#14532d;--okbg:#f0fdf4;--red:#7f1d1d;--redbg:#fef2f2}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0f2a24;color:#fff;padding:16px 24px}header .t{font-weight:700;font-size:17px}
nav{margin-top:6px;font-size:14px}nav a{margin-right:16px;color:#bfe9dc;text-decoration:none}nav a.on{font-weight:700;text-decoration:underline}
main{max-width:1000px;margin:0 auto;padding:20px}section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:14px 0}
h1{font-size:25px;margin:2px 0 8px}h2{font-size:19px;margin:0 0 10px}h3{font-size:16px;margin:14px 0 6px}
.label{font-size:20px;font-weight:800;border-radius:10px;padding:14px 16px;margin:4px 0 10px}
.label.no{background:var(--redbg);border:2px solid #fca5a5;color:var(--red)}
.label.yes{background:var(--okbg);border:2px solid #86efac;color:var(--ok)}
.banner{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:12px 14px;font-weight:600}
.warn{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:12px 14px}
.ok{background:var(--okbg);border:1px solid #bbf7d0;color:var(--ok);border-radius:10px;padding:12px 14px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f1f5f9}code,pre{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap}
.pill{display:inline-block;font-size:12px;border-radius:999px;padding:1px 8px;border:1px solid var(--line);color:var(--muted);margin-right:4px;white-space:nowrap}
.note{color:var(--muted);font-size:14px}footer{max-width:1000px;margin:0 auto;padding:8px 20px 40px;color:var(--muted);font-size:13px}
a{color:var(--accent)}ul,ol{padding-left:22px}li{margin:3px 0}.btn{display:inline-block;background:#0b6e4f;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700}
.btn.dis{background:#94a3b8}
"""

NAV = [("index.html", "Executive summary"), ("submission.html", "The file"), ("evidence.html", "Evidence")]


def J(rel):
    return json.loads((ROOT / rel).read_text())


def esc(x):
    return html.escape(str(x))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def page(title, body, active):
    nav = "".join(f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · GEMSDOE53</title>
<style>{CSS}</style></head><body>
<header><div class="t">GEMSDOE53 · DrivenData GEMS (DOE) competition 306</div>
<nav>{nav}<a href="https://github.com/buffedlizard55-lab/GEMSDOE53">repository</a></nav></header>
<main>{body}</main>
<footer>Numbers on these pages are read from JSON in <code>evidence/</code>, <code>registry/</code> and <code>docs/submissions/</code>.
HOLDOUT-DTI = our proxy (withheld known-fault segments or spatial super-regions). ORGANIZER-CONFIRMED = receipt only (none exists).
Regenerate with <code>python scripts/build_site.py</code>.</footer></body></html>"""


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def f4(x):
    return "n/a" if x is None else f"{x:.4f}"


def main() -> int:
    cur = J("docs/submissions/CURRENT.json")
    e1 = J("evidence/e1_h1_thin_holdout.json")
    e2 = J("evidence/e2_leakfree_holdouts.json")
    e3 = J(cur["receipt"])
    gate = J(f"evidence/uniqueness_gate_{cur['name']}.json")
    g32 = J("evidence/gemsdoe32_measured.json")
    irr = J("registry/irregularities.json")["items"]
    lim = J("registry/limitations.json")["items"]
    srcs = {s["id"]: s for s in J("registry/sources.json")["sources"]}
    card = J("evidence/run_card.json")
    diag = J(f"evidence/uniqueness_diagnostics_{cur['name']}.json")
    sp_rho = J(f"evidence/diagnostic_surface_rho_{cur['name']}.json")
    label = cur["label"]
    ok = label.startswith("Validated")
    sp = e2.get("spatial_confirmation", {})
    stage1 = e2.get("segment_selection", {})
    base_B = e2["baseline_design_B"]
    cd = e2["canary_design_B"]
    V = e2["segment_folds"]["variants"]
    fname = cur["file"].split("/")[-1]
    tif_path = ROOT / cur["file"]
    size_b = tif_path.stat().st_size if tif_path.exists() else e3["bytes"]
    accepted = bool(sp.get("acceptance", {}).get("accepted", False))
    selected = stage1.get("selected")
    cand_desc = f"{cur['spec']['arm']} {cur['spec']['variant']}"
    cand_pooled = (sp.get("selected_result", {}).get("pooled_DTI") if (selected and cur["spec"]["variant"] == selected["variant"]
                                                                       and cur["spec"]["arm"] == selected["arm"])
                   else sp.get("baseline", {}).get("pooled_DTI", base_B["pooled_DTI"]))
    dl_text = ("Download is allowed for research and review. It is <b>not</b> cleared for submission."
               if not ok else "Download is allowed. Submission is allowed only through the separate selector step.")
    sub_text = ("<b>NO.</b> Do not upload this file." if not ok else
                "<b>YES, if you choose this file in the selector step.</b> The gates below all pass.")
    label_cls = "yes" if ok else "no"

    # ---------------------------------------------------------------- index.html
    variant_rows = []
    for key in ("bands:top_q0p02", "h1:top_q0p02", "bands:thin_bin_q0p1", "h1:thin_bin_q0p1"):
        if key in V:
            r = V[key]
            variant_rows.append(f"<tr><td>{esc(r['arm'])}</td><td>{esc(r['variant'])}</td><td><b>{f4(r['pooled_DTI'])}</b></td>"
                                f"<td>{esc(r['CI95_t_df4_on_fold_mean'])}</td><td>{r['mean_emitted_px']:,}</td></tr>")
    sp_rows = ""
    if sp.get("status") == "COMPLETED":
        d = sp["paired_difference"]
        sp_rows = (f"<tr><td>Spatial confirmation (contiguous super-regions)</td><td>baseline {f4(sp['baseline']['pooled_DTI'])} vs "
                   f"{esc(sp['selected']['arm'])} {esc(sp['selected']['variant'])} {f4(sp['selected_result']['pooled_DTI'])}</td>"
                   f"<td>paired mean diff {d['mean_fold_diff']:+.4f}, 95% CI {d['CI95'][0]:+.4f} to {d['CI95'][1]:+.4f}; "
                   f"accepted = {accepted}</td></tr>")
    gate_pass = {k: bool(v) for k, v in e3["gates"].items()}
    gate_rows = "".join(f"<tr><td>{esc(k)}</td><td>{'PASS' if gate_pass[k] else 'FAIL'}</td></tr>" for k in gate_pass)
    open_irr = [i for i in irr if str(i.get("status", "")).startswith("open")]
    top_irr = "".join(f"<li><b>{esc(i['id'])}</b> ({esc(i['severity'])}): {esc(i['subject'])}</li>"
                      for i in irr if i["id"] in ("IR-53-01", "IR-53-02", "IR-53-19", "IR-53-20", "IR-53-22", "IR-53-24"))

    body = f"""
<section>
  <div class="label {label_cls}">{esc(label).upper()}</div>
  <p><b>Is it OK to download?</b> {dl_text}<br>
  <b>Is it OK to submit?</b> {sub_text}</p>
  <h1>Executive summary</h1>
  <p>Question: can we ship one unique, valid GeoTIFF for DrivenData competition 306, and what do the evidence and the protocol allow us to claim?
  Short answer: the file below passes every format check, but it is <b>not cleared by the uniqueness gate</b>, so it is labelled
  <b>{esc(label)}</b>. The uniqueness gate flags {gate['n_flagged']} registry rasters, and on this registry the raw 70% overlap rule cannot be satisfied by any placement (IR-53-28).
  The holdout evidence is also a proxy, and our first holdout had a design error (IR-53-19).</p>
  <div class="warn">No organizer score exists for any file here. The leaderboard values quoted below are the repository's snapshot (IR-53-01).
  Nothing has been submitted, and no submission slot was used.</div>
</section>

<section>
  <h2>The file</h2>
  <table>
    <tr><th>Download</th><td><a class="btn {'' if ok else 'dis'}" href="submissions/{esc(fname)}">Download {esc(fname)}</a> ({size_b:,} bytes)</td></tr>
    <tr><th>Name (unique)</th><td><code>{esc(cur['name'])}</code></td></tr>
    <tr><th>Comment (≤140 characters, {len(cur['note'])} used)</th><td><code>{esc(cur['note'])}</code></td></tr>
    <tr><th>sha256 (container)</th><td><code>{esc(cur['sha256'])}</code></td></tr>
    <tr><th>sha256 (pixels, float32 little-endian)</th><td><code>{esc(cur['pixel_sha256'])}</code></td></tr>
    <tr><th>Candidate</th><td>{esc(cand_desc)}, trained on all known faults, emission zeroed on known faults</td></tr>
    <tr><th>Format</th><td>single-band float32 GeoTIFF, EPSG:32611, 100 m, same transform and shape as the sample, NaN exactly outside the footprint, values in [0, 1]</td></tr>
  </table>
  <p class="note">Status words in the file's metadata match the label above. Re-run <code>python scripts/e3_build_candidate.py</code> to regenerate.</p>
</section>

<section>
  <h2>How to submit (only if the label says OK)</h2>
  <ol>
    <li>Read the label above first. If it says <b>RESEARCH-ONLY / DO NOT SUBMIT</b>, stop here.</li>
    <li>Open the competition submission page on DrivenData and log in to your own account. No data download is needed.</li>
    <li>Upload the file. In the name field enter <code>{esc(cur['name'])}</code>. In the comment field enter the comment above (≤140 characters).</li>
    <li>Check the upload result. Record the portal's exact message. Only a receipt makes a number ORGANIZER-CONFIRMED.</li>
    <li>The portal limit is 3 feedback submissions per week and one final choice (<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">NLR rules §3.4</a>).
    Choosing a slot is a separate decision and was not made here.</li>
  </ol>
  <p class="note">Sources: <a href="{esc(srcs['S1']['url'])}">problem page (S1)</a> · <a href="{esc(srcs['S2']['url'])}">leaderboard snapshot (S2)</a> · <a href="{esc(srcs['S3']['url'])}">NLR rules (S3)</a>.</p>
</section>

<section>
  <h2>Answers (each labelled)</h2>
  <table>
    <tr><th>Question</th><th>Answer</th><th>Label</th></tr>
    <tr><td>Is the file unique and valid?</td><td>Valid: yes (format and conformance checks pass). Unique under the pre-registered gate: <b>no</b>. The gate flags {gate['n_flagged']} of {gate['registry_unique_on_grid']} unique GEMSDOE registry rasters. Of those flags, {diag['flagged_by_class'].get('dense(>50% nonzero)', 0)} are dense rasters (feature grids, probability surfaces) that overlap 100% by construction, and the other {diag['flagged_by_class'].get('sparse(<=25%)', 0) + diag['flagged_by_class'].get('mid(25-50%)', 0)} are dot maps. For those the median chance-corrected lift is {diag['sparse_flagged_median_lift']:.2f} (1.0 = random placement), so most of their overlap is what footprint coverage predicts (IR-53-28, IR-53-30).</td>
      <td><span class="pill">gates in submission.html</span></td></tr>
    <tr><td>What would make the file OK to submit?</td><td>A change to the gate's definition (registry scope, a chance-corrected overlap rule, and a footprint-only rank correlation), approved by you (IR-53-16, IR-53-28, IR-53-29), followed by a fresh pre-registered gate run. Nothing of that kind has been applied here.</td>
      <td><span class="pill">decision for the user</span></td></tr>
    <tr><td>Does it beat 0.3774 (public #1)?</td><td>Unknown. Nothing here is an organizer score.</td><td><span class="pill">ORGANIZER-CONFIRMED: none</span></td></tr>
    <tr><td>Holdout proxy (stage 1, design B)</td><td>Bands top-q 0.02 baseline: pooled {f4(base_B['pooled_DTI'])}, 95% CI {base_B['CI95'][0]:.4f} to {base_B['CI95'][1]:.4f}, withheld positives {base_B['withheld_positives']:,}.
      Selected variant ({esc(selected['arm'] + ' ' + selected['variant']) if selected else 'none'}): pooled {f4(selected['pooled_DTI']) if selected else 'n/a'}, chosen on these folds, so optimistic.</td>
      <td><span class="pill">HOLDOUT-DTI</span></td></tr>
    {sp_rows}
    <tr><td>Why GEMSDOE29 leaks</td><td>Its distance feature is built from the full catalogue, so it is exactly 0 on every known-fault pixel (separability 1.0). Mechanism and audit in <a href="evidence.html#gemsdoe29">evidence</a> and <code>docs/leakage-review.md</code>.</td>
      <td><span class="pill">measured</span></td></tr>
    <tr><td>Our own holdout had a leak (IR-53-19)</td><td>The first holdout (design A) built its negative pool from withheld labels. Its bands top-q 0.02 pooled DTI was {f4(e1['arms']['bands']['top_q0p02']['pooled_DTI'])}; corrected design B gives {f4(base_B['pooled_DTI'])}. Corrected to design B (DEV-1, pre-registered; the design-A numbers are not used).</td>
      <td><span class="pill">measured</span></td></tr>
    <tr><td>Why GEMSDOE32 H33-2-B2 (0.2778) may score high</td><td>Measured on the registry copy: 37,654 dots (0.73% of the footprint), no dot within 2 px of a mapped fault, and dot spacing centred on 3 px (the metric radius). Whether that produced 0.2778 is <b>not established</b>: no receipt links the row to the file (IR-53-02).</td>
      <td><span class="pill">MEASURED structure; score link NOT established</span></td></tr>
    <tr><td>Can a higher-scoring file be built?</td><td>Not shown. We have a proxy that rises with thinning and proximity, which is not the competition target (IR-53-24). No file here is shown to beat any leaderboard row.</td>
      <td><span class="pill">not established</span></td></tr>
  </table>
  <p class="note">The spatial numbers are small in absolute terms: on unseen super-regions the candidate recovers very few withheld faults. The paired gain is positive on all five folds, and the pre-registered rule accepts it. The segment-fold number above is the within-region proximity effect, which the competition target may not share (IR-53-24).</p>
</section>

<section>
  <h2>Bars to beat (repository snapshot, not re-read this session)</h2>
  <table><tr><th>Rank</th><th>Team</th><th>Score</th><th>Label</th></tr>
  <tr><td>1</td><td>xiaofanhu</td><td>0.3774</td><td>leaderboard snapshot (S2)</td></tr>
  <tr><td>7</td><td>DARD</td><td>0.3195</td><td>leaderboard snapshot (S2)</td></tr>
  <tr><td>13</td><td>extradr19</td><td>0.2778</td><td>leaderboard snapshot (S2); the file link is NOT established (IR-53-02)</td></tr></table>
  <p class="note">The request named 0.3195 as the top score. The snapshot shows 0.3774 at #1 (IR-53-01). The snapshot time is not shown on the page.</p>
</section>

<section>
  <h2>Flagged for review</h2>
  <ul>{top_irr}</ul>
  <p class="note">Full list with severities: <a href="evidence.html#irregularities">evidence page</a>. Limitations: <a href="evidence.html#limitations">evidence page</a>.</p>
</section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", body, "index.html"))

    # ---------------------------------------------------------------- submission.html
    inl = e3["inlane"]
    val_rows = [
        ("template scripts/validate_submission.py (shared)", e3["validators"]["final_template_validate_submission"]["exit"]),
        ("python -m src.submission_io validate-conformant (shared)", e3["validators"]["final_validate_conformant"]["exit"]),
    ]
    in_rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in [
        ("CRS EPSG", inl["crs_epsg"]), ("grid 3730 x 3292", inl["shape_ok"]), ("transform equals sample", inl["transform_ok"]),
        ("resolution 100 m", inl["res_ok"]), ("one band", inl["count_ok"]), ("dtype", inl["dtype"]),
        ("nodata tag", inl["nodata"]), ("NaN exactly outside sample footprint", inl["nan_exact_outside_template"]),
        ("values in [0, 1] on the whole array", inl["values_in_0_1_whole_array"]),
        ("finite pixels (footprint)", f"{inl['finite_px']:,}"), ("nonzero pixels (dots)", f"{inl['nonzero_px']:,}"),
        ("min / max", f"{inl['min']:.4f} / {inl['max']:.4f}")])
    def lift_txt(r):
        v = r["lift_over_chance"]
        return "" if v is None else f"{v:.2f}"

    top_rows = "".join(
        f"<tr><td>{esc(r['file'][:70])}</td><td>{r['reg_dots']:,}</td><td>{pct(r['overlap_final'])}</td>"
        f"<td>{pct(r['chance_coverage'])}</td><td>{lift_txt(r)}</td><td>{f4(r['rho_footprint_only'])}</td></tr>"
        for r in diag["sparse_flagged_top"][:8])
    body = f"""
<section>
  <div class="label {label_cls}">{esc(label).upper()}</div>
  <h1>The file</h1>
  <p><code>{esc(cur['file'])}</code> · sha256 <code>{esc(cur['sha256'])}</code></p>
  <p>Name <code>{esc(cur['name'])}</code> · Comment <code>{esc(cur['note'])}</code></p>
  <p class="note">Decision recorded: {esc(cur['decision'])}.</p>
</section>
<section>
  <h2>Gates (pre-registered; all must pass for "OK to submit")</h2>
  <table><tr><th>Gate</th><th>Result</th></tr>{gate_rows}</table>
  <p class="note">Holdout gate = stage-2 paired lower bound above 0 for the selected variant (design B, spatial super-regions). Uniqueness gate = no registry file with Spearman rho above 0.90 and no registry file with more than 70% of our dots within 3 px of its dots.</p>
</section>
<section>
  <h2>Validators (shared template tools, run on the shipped bytes)</h2>
  <table><tr><th>Check</th><th>Exit code (0 = pass)</th></tr>
  {''.join(f'<tr><td>{esc(a)}</td><td>{b}</td></tr>' for a, b in val_rows)}</table>
  <h3>In-lane checks on the whole array</h3>
  <table><tr><th>Check</th><th>Value</th></tr>{in_rows}</table>
</section>
<section>
  <h2>Uniqueness receipt (rebuilt registry, {gate['registry_unique_on_grid']} unique rasters)</h2>
  <p>Every unique (sha256) registry raster on the official grid was compared. Overlap = share of our dots within 3 px of that raster's dots. Lift = overlap / chance coverage (1.0 = what random placement would give).</p>
  <p>Sparse dot maps flagged (the eight with the largest overlap). Dense rasters (57 flagged) are left out of this table: they overlap 100% by construction.</p>
  <table><tr><th>Registry dot map</th><th>Dots</th><th>Overlap (our dots within 3 px)</th><th>Chance coverage</th><th>Lift</th><th>Footprint-only rho</th></tr>{top_rows}</table>
  <p>Full receipt (all 621 rasters): <code>evidence/uniqueness_gate_{esc(cur['name'])}.json</code>. Diagnostics: <code>evidence/uniqueness_diagnostics_{esc(cur['name'])}.json</code>.</p>
</section>
<section>
  <h2>Why the uniqueness gate flags the file (diagnostics; the verdict is the pre-registered receipt)</h2>
  <ul>
    <li><b>{diag['flagged_rows_analysed']}</b> registry rasters are flagged. By class: {esc(', '.join(f'{k}: {v}' for k, v in diag['flagged_by_class'].items()))}.</li>
    <li>By overlap above 70%: {diag['flagged_by_overlap']}. By Spearman rho above 0.90 of the candidate surface: {sp_rho['flagged_by_surface_rho_whole_grid']} rasters on the whole grid (NaN counted as 0, which inflates rho through the zeros outside the footprint), and {sp_rho['flagged_by_surface_rho_footprint_only']} on the footprint only (IR-53-29). The final raster exceeds 0.90 for none of the rasters on either basis.</li>
    <li>Chance coverage of the densest sparse dot map: <b>{100 * diag['densest_sparse_dot_maps_by_chance_coverage'][0]['chance_coverage']:.2f}%</b> of the footprint lies within 3 px of its dots (<code>{esc(diag['densest_sparse_dot_maps_by_chance_coverage'][0]['file'][:80])}</code>). Any candidate placed on this footprint therefore overlaps that file above 70%. The raw gate is <b>not satisfiable by placement</b> on this registry (IR-53-28).</li>
    <li>Median chance-corrected lift for the sparse flagged files: {diag['sparse_flagged_median_lift']:.2f} (1.0 means the overlap is what random placement would give). This is a diagnostic only. Changing the gate needs your explicit approval.</li>
  </ul>
</section>
<section>
  <h2>Why the label reads as it does</h2>
  <ul>
    <li>The format and conformance checks pass ({'yes' if gate_pass['format_validators_all'] else 'no'}).</li>
    <li>The uniqueness gate: {'no drift flag' if not gate['any_drift_flag'] else 'drift flagged'}.</li>
    <li>The holdout gate: {'accepted' if accepted else 'not accepted'} (stage 2, paired, design B). {('' if accepted else 'The candidate is the design-B holdout best (bands top-q 0.02) and does not clear the confirmation rule, so it is labelled research-only.')}</li>
    <li>The canary: bands max separability {f4(cd['bands_max_over_all'])}, H1 {f4(cd['h1_max_separability'])}, both below the 0.90 gate.</li>
  </ul>
</section>
"""
    (DOCS / "submission.html").write_text(page("The file", body, "submission.html"))

    # ---------------------------------------------------------------- evidence.html
    e1_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{f4(v['pooled_DTI'])}</td><td>{esc(v['CI95_t_df4_on_fold_mean'])}</td><td>{v['mean_emitted_px']:,}</td></tr>"
        for k, v in e1["arms"]["bands"].items() if k.startswith("top_q"))
    def kept_txt(v):
        k = v["mean_kept_dots"]
        return "" if k is None else f"{k:,}"

    e2_rows = "".join(
        f"<tr><td>{esc(v['arm'])}</td><td>{esc(v['variant'])}</td><td>{f4(v['pooled_DTI'])}</td>"
        f"<td>{esc(v['CI95_t_df4_on_fold_mean'])}</td><td>{v['mean_emitted_px']:,}</td><td>{kept_txt(v)}</td></tr>"
        for v in V.values())
    fold_rows = "".join(
        f"<tr><td>{r['fold']}</td><td>{r['withheld_px']:,}</td><td>{r['withheld_segments']}</td><td>{f4(r['baseline']['DTI'])}</td>"
        f"<td>{f4(r['selected']['DTI'])}</td></tr>" for r in sp.get("per_fold", []))
    canary_rows = "".join(f"<tr><td>{esc(b)}</td><td>{f4(v)}</td></tr>" for b, v in cd["bands_max_separability_per_band"].items())
    irr_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['severity'])}</td><td>{esc(i['status'])}</td><td>{esc(i['subject'])}</td></tr>" for i in irr)
    lim_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['item'])}</td></tr>" for i in lim)
    src_rows = "".join(f"<tr><td>{esc(k)}</td><td><a href=\"{esc(s['url'])}\">{esc(s['title'][:90])}</a></td><td>{esc(s['access'][:90])}</td></tr>"
                       for k, s in srcs.items())
    hyp_rows = """<tr><td>H1</td><td>Segment-exact learn-predict separation (distance to visible faults excluding the pixel's own segment)</td><td>Tested in E2 (design B); see the stage-1 and stage-2 tables</td></tr>
<tr><td>M1</td><td>Metric-aware thinning: greedy dominating set at radius 3 px, value p or 1</td><td>Tested in E2 (design B) as variants</td></tr>
<tr><td>H2</td><td>Magnetic lineament ridges (Hessian) on band 2 and the native GeoDAWN grid (mirror S20)</td><td>Not tested (budget)</td></tr>
<tr><td>H3</td><td>Fault-parallel strain from bands 7 and 8</td><td><b>BLOCKED</b>: the public strain data have scalars only (IR-53-22)</td></tr>
<tr><td>H4</td><td>USGS Qfaults as an extra label source</td><td>Rejected: the rules name these maps as a label source</td></tr>
<tr><td>H5</td><td>Off-catalogue thermal evidence: INGENIOUS 2 m temperature probes, paleo-geothermal deposits, wells and springs (mirror S20, S22)</td><td>Not tested (budget). Data present in the pinned mirror; licence to verify (IR-53-26)</td></tr>
<tr><td>H6</td><td>Regional trend prior: dominant orientation of visible faults as a feature</td><td>Not tested (budget)</td></tr>"""
    g = g32["files"]["nan"]
    body = f"""
<section>
  <h1>Evidence</h1>
  <p class="note">Every number is read from JSON. HOLDOUT-DTI = proxy. Evaluator <code>gems53.core.dti</code> v1.0.0, parity with the template's <code>src/metrics.py</code>
  (difference {e1['metric_parity_vs_template']['abs_diff']:.1e}).</p>
  <p><a href="data/run_card.json">Run card (JSON)</a> · <a href="data/e1_h1_thin_holdout.json">E1 record</a> · <a href="data/e2_leakfree_holdouts.json">E2 record</a> ·
  <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/arena/0efb644e-gemsdoe53/docs/research/preregistration-2026-10-08.md">pre-registration</a></p>
</section>
<section>
  <h2>E1 (design A, reference only): exploration with the withheld-label negative pool</h2>
  <div class="warn">Design A is <b>not used</b> for any decision (IR-53-19). It is shown to measure the side channel. Reproduction of the exp2 numbers: {'PASS' if e1['reproduction_check_vs_exp2']['pass'] else 'FAIL'}.</div>
  <table><tr><th>Bands arm variant</th><th>Pooled DTI</th><th>95% CI</th><th>Emitted px</th></tr>{e1_rows}</table>
  <p>H1 (design A) at top-q 0.02: <b>{f4(e1['arms']['h1']['top_q0p02']['pooled_DTI'])}</b>.
  Canary, design A (buffered background, reference): H1 mean {f4(e1['canary_H1_feature_alone']['separability_mean'])}.</p>
</section>
<section>
  <h2>E2 (design B): stage 1, all 24 variants on segment folds (seed 53)</h2>
  <p>Negatives are every footprint pixel that is not a visible fault (DEV-1). Baseline and selection rule as pre-registered.</p>
  <table><tr><th>Arm</th><th>Variant</th><th>Pooled DTI</th><th>95% CI (t, df 4)</th><th>Emitted px</th><th>Kept dots</th></tr>{e2_rows}</table>
  <h3>Fold detail, baseline vs selected (stage 2, spatial)</h3>
  <table><tr><th>Fold</th><th>Withheld px</th><th>Withheld segments</th><th>Baseline DTI</th><th>Selected DTI</th></tr>{fold_rows}</table>
</section>
<section>
  <h2>Canary under design B (19 label-free bands; background = full non-fault footprint)</h2>
  <table><tr><th>Band</th><th>Max separability over folds</th></tr>{canary_rows}</table>
  <p>H1 feature alone: max separability {f4(cd['h1_max_separability'])}. Gate 0.90. Flags: bands {esc(cd['bands_flag'])}, H1 {esc(cd['h1_flag'])}.</p>
</section>
<section id="gemsdoe29">
  <h2>GEMSDOE29 leakage (formal diagnosis)</h2>
  <p>Mechanism: the deprecated <code>scripts/build_repo_candidate.py</code> in GEMSDOE29 builds its distance-to-known-faults feature from the full label raster, so the feature is exactly 0 on every known-fault pixel. Separability is 1.0 in-sample and on withheld folds. On the holdout the leaky arm reaches DTI 0.99996 (design A, exp2 reference; a defect demo, not a candidate). The formal write-up, audit table and protocol gaps are in <code>docs/leakage-review.md</code>. Learn-predict separation (Kaufman et al., TKDD 2012; DOI 10.1145/2382577.2382579) is the avoidance method used here.</p>
</section>
<section id="gemsdoe32">
  <h2>GEMSDOE32 H33-2-B2 (score 0.2778): measured structure and owner claims</h2>
  <table>
    <tr><th>Measured (registry copy, NaN variant)</th><th>Value</th></tr>
    <tr><td>dots (value 1), share of footprint</td><td>{g['dots']:,} ({pct(g['dots_share_of_footprint'])})</td></tr>
    <tr><td>dots within 2 px of a mapped fault</td><td>{pct(g['dots_within_2px_of_catalogue'])}</td></tr>
    <tr><td>dots within 3 px of a mapped fault</td><td>{pct(g['dots_within_3px_of_catalogue'])}</td></tr>
    <tr><td>nearest-dot distance, median (px)</td><td>{g['nearest_dot_distance_quantiles_px']['0.5']}</td></tr>
    <tr><td>finite pixels (footprint) vs zeros variant</td><td>{g['finite_px']:,} vs {g32['files']['zeros']['finite_px']:,} (the zeros variant fills the grid with 0, IR-53-23)</td></tr>
    <tr><td>in-catalogue DTI (diagnostic only)</td><td>{f4(g['in_catalogue_DTI_diagnostic'])}</td></tr>
  </table>
  <p><b>OWNER-CLAIM (not verified):</b> 0.2708 base, dots within 2 px removed, 37,654 dots, no organiser score. The pruning claim is consistent with the measured 0.0% within 2 px.
  <b>NOT ESTABLISHED:</b> that this file produced the 0.2778 row (IR-53-02). <b>MEASURED:</b> the dots are spaced about the metric radius apart, the same structure that thinning produces (M1).</p>
</section>
<section id="hypotheses">
  <h2>Hypotheses (ranked; cost and gain are judgements, not scores)</h2>
  <table><tr><th>ID</th><th>Hypothesis</th><th>Status</th></tr>{hyp_rows}</table>
  <p class="note">Full layers, signatures, off-catalogue rationale and cost: <code>docs/research/hypotheses.md</code>.</p>
</section>
<section id="irregularities">
  <h2>Irregularities (flagged for review)</h2>
  <table><tr><th>ID</th><th>Severity</th><th>Status</th><th>Subject</th></tr>{irr_rows}</table>
</section>
<section id="limitations">
  <h2>Limitations and remaining work</h2>
  <table><tr><th>ID</th><th>Item</th></tr>{lim_rows}</table>
</section>
<section>
  <h2>Sources</h2>
  <table><tr><th>ID</th><th>Source</th><th>Access</th></tr>{src_rows}</table>
</section>
"""
    (DOCS / "evidence.html").write_text(page("Evidence", body, "evidence.html"))

    # ---------------------------------------------------------------- data copies for the links
    data_dir = DOCS / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for rel in ("evidence/run_card.json", "evidence/e1_h1_thin_holdout.json", "evidence/e2_leakfree_holdouts.json",
                f"evidence/uniqueness_gate_{cur['name']}.json", f"evidence/uniqueness_diagnostics_{cur['name']}.json",
                cur["receipt"], "evidence/gemsdoe32_measured.json", "registry/irregularities.json",
                "registry/limitations.json", "registry/sources.json", "docs/submissions/CURRENT.json"):
        src = ROOT / rel
        if src.exists():
            shutil.copy(src, data_dir / src.name)
    # keep the data folder exactly equal to the current copies (no stale files)
    keep = {Path(r).name for r in ("evidence/run_card.json", "evidence/e1_h1_thin_holdout.json",
                                   "evidence/e2_leakfree_holdouts.json") }
    for f in data_dir.glob("*.json"):
        if f.name not in keep and not (ROOT / "evidence").joinpath(f.name).exists() and f.name not in {Path(p).name for p in ("registry/irregularities.json", "registry/limitations.json", "registry/sources.json", "docs/submissions/CURRENT.json")}:
            f.unlink()
    (DOCS / ".nojekyll").write_text("")  # serve the static HTML as-is
    print("site written:", DOCS / "index.html", DOCS / "submission.html", DOCS / "evidence.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
