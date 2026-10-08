#!/usr/bin/env python3
"""Publish the H55-EDGE negative result as a separate, research-only page.

This publisher is intentionally non-destructive: it does not replace the main H55
page, the H55-PROFILE page, docs/data/submission.json, or submission/LATEST.txt.
It renders one archive page and adds a clearly failed-gate link to the existing
main H55, overview, and downloads pages.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
import zipfile

import numpy as np
import rasterio
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def esc(value) -> str:
    return html.escape(str(value))


def link(path: str, text: str) -> str:
    return f'<a href="{esc(path)}">{esc(text)}</a>'


def fmt(value: float, places: int = 6) -> str:
    return f"{float(value):.{places}f}"


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{esc(cell)}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def page(title: str, body: str) -> str:
    nav = "".join(link(p, label) for p, label in [
        ("index.html", "Overview"),
        ("h55.html", "Main H55 candidate"),
        ("h55-profile.html", "H55-PROFILE follow-up"),
        ("h55-edge.html", "H55-EDGE negative result"),
        ("validation.html", "Validation"),
        ("downloads/index.html", "Downloads"),
        ("sources.html", "Sources"),
    ])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="H55-EDGE preregistered potential-field edge test: failed spatial promotion and strict support-novelty gates; research-only evidence archive."><title>{esc(title)} · GEMSDOE52</title><link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head><body><a class="skip" href="#main">Skip to evidence</a><header><nav><a class="brand" href="index.html">GEMS / DOE 52</a>{nav}</nav></header><main id="main">{body}</main><footer>H55-EDGE is a historical research result, not the current H55 candidate. Fault-prediction research, not confirmed faults or geothermal vents. {link('sources.html','Sources')} · {link('irregularities.html','Limitations')} · {link('https://github.com/buffedlizard55-lab/GEMSDOE52','Code & complete prompt')}</footer></body></html>'''


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_artifact(sub: dict) -> None:
    name = sub["file"]
    expected = sub["sha256"]
    tiff = ROOT / "submission" / name
    published = DOCS / "downloads" / name
    if not tiff.exists() or hash_file(tiff) != expected or tiff.stat().st_size != sub["bytes"]:
        raise ValueError("H55-EDGE source TIFF differs from its frozen byte receipt")
    if not published.exists() or hash_file(published) != expected or published.stat().st_size != sub["bytes"]:
        raise ValueError("H55-EDGE download TIFF differs from its frozen byte receipt")
    for archive_path in (tiff.with_suffix(".zip"), published.with_suffix(".zip")):
        with zipfile.ZipFile(archive_path) as archive:
            if archive.namelist() != [name] or hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f"H55-EDGE ZIP is not a one-TIFF byte-identical package: {archive_path}")
    marker = ROOT / "submission/LATEST.txt"
    if marker.exists() and marker.read_text().strip() == name:
        raise ValueError("H55-EDGE is a failed-gate archive and must not replace the main LATEST pointer")


def make_preview(sub: dict) -> Path | None:
    labels_path = ROOT / "data/labels.tif"
    asset = DOCS / "assets/prediction-h55-edge.png"
    if not labels_path.exists():
        return asset if asset.exists() else None
    asset.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(DOCS / "downloads" / sub["file"]) as ds:
        pred = ds.read(1) > 0
        footprint = ds.dataset_mask() > 0
    with rasterio.open(labels_path) as ds:
        catalogue = ds.read(1) == 1
    def pool(a: np.ndarray, factor: int = 4) -> np.ndarray:
        h, w = a.shape
        p = np.pad(a, ((0, (-h) % factor), (0, (-w) % factor)))
        return p.reshape(p.shape[0] // factor, factor, p.shape[1] // factor, factor).max((1, 3))
    fp, known, proposed = pool(footprint), pool(catalogue), pool(pred)
    rgb = np.full(fp.shape + (3,), (237, 241, 233), dtype=np.uint8)
    rgb[fp] = (217, 226, 215)
    rgb[known & fp] = (74, 113, 151)
    rgb[proposed & fp] = (202, 133, 57)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    draw.line((35, 60, 35, 24), fill=(24, 51, 46), width=3)
    draw.polygon([(35, 19), (29, 30), (41, 30)], fill=(24, 51, 46))
    draw.text((30, 6), "N", fill=(24, 51, 46))
    image.save(asset)
    return asset


def upsert_section(path: Path, start: str, end: str, block: str, *, after: str | None = None) -> None:
    text = path.read_text()
    wrapped = f"{start}{block}{end}"
    if start in text and end in text:
        left = text.index(start)
        right = text.index(end, left) + len(end)
        text = text[:left] + wrapped + text[right:]
    elif after and after in text:
        i = text.index(after) + len(after)
        text = text[:i] + wrapped + text[i:]
    elif "</main>" in text:
        text = text.replace("</main>", wrapped + "</main>", 1)
    else:
        raise ValueError(f"Cannot insert H55-EDGE archive link into {path}")
    path.write_text(text)


def main() -> int:
    sub = load(EV / "h55_edge_submission.json")
    hold = load(EV / "h55_edge_holdout.json")
    indep = load(EV / "h55_edge_independence.json")
    uniqueness = load(EV / "h55_edge_uniqueness.json")
    deviation = load(EV / "h55_edge_protocol_deviation.json")
    reasoning = sub["view_comparison"]["a_only_reasoning"]
    prereg_hash = hash_file(ROOT / "registry/h55_edge_preregistration.json")
    if prereg_hash != sub["preregistration_sha256"] or prereg_hash != deviation["preregistration_sha256_at_validation"]:
        raise ValueError("H55-EDGE preregistration bytes do not match the frozen result receipts")
    if hold["preregistration_sha256"] != prereg_hash:
        raise ValueError("H55-EDGE holdout receipt does not reference the frozen registration")
    verify_artifact(sub)
    preview = make_preview(sub)

    candidate = hold["candidate"]
    baseline = hold["best_comparable_baseline"]
    lift = float(hold["mean_dti_lift"])
    positive = int(hold["positive_folds"])
    threshold = float(hold["promotion_gate"]["minimum_mean_lift"])
    positive_needed = int(hold["promotion_gate"]["minimum_positive_folds"])
    budget = int(sub["budget"])
    fmt_receipt = sub["format"]
    report_link = "data/h55_edge_submission.json"
    file_name = sub["file"]
    note = sub["submission_note"]

    fold_rows = []
    for fold in hold["folds"]:
        arms = fold["arms"]
        fold_rows.append([
            f"Fold {int(fold['fold']) + 1}",
            fmt(arms["view_B"]["dti"]),
            fmt(arms["R2_structural_contrast"]["dti"]),
            fmt(arms["H55_structural_contrast"]["dti"]),
            f"{float(arms['H55_structural_contrast']['dti'] - arms['view_B']['dti']):+.6f}",
        ])
    fold_table = table(["spatial holdout", "View B", "R2 structural control", "H55-EDGE", "paired Δ vs B"], fold_rows)

    csv_path = EV / reasoning["file"]
    zero_pairs = 0
    positive_pairs = 0
    with csv_path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            value = float(row["paired_gravity_RTP_edge_response"])
            zero_pairs += value == 0.0
            positive_pairs += value > 0.0
    if zero_pairs + positive_pairs != int(reasoning["rows"]):
        raise ValueError("H55-EDGE reasoning CSV has an unexpected paired-edge response value")

    status = ('<div class="status"><strong>Research-only — do not upload or use a weekly slot.</strong> '
              f"The preregistered promotion gates failed: {lift:+.6f} mean paired lift (required ≥{threshold:+.3f}), "
              f"positive in {positive}/{hold['total_folds']} folds (required ≥{positive_needed}). "
              "The strict support-novelty slot diagnostic also failed. No portal upload, official score, or organizer acceptance is claimed.</div>")
    picture = (f'<figure><img src="assets/{preview.name}" alt="North-up overview of the H55-EDGE candidate pixels, known catalogue, and survey footprint."><figcaption>Decoded H55-EDGE raster: amber proposals, blue catalogue labels, muted survey footprint. Display downsample only; no pixel is field-confirmed.</figcaption></figure>' if preview else "")
    downloads = f'''<section class="download-bar" aria-label="H55-EDGE research downloads"><div><strong>H55-EDGE research artifact — failed-gate archive</strong><small><code>{esc(file_name)}</code></small><small>{int(sub['bytes']):,} bytes · one float32 band · EPSG:32611 · {fmt_receipt['width']} × {fmt_receipt['height']} · values [{fmt_receipt['min']}, {fmt_receipt['max']}]</small><small>Byte SHA-256: <code>{esc(sub['sha256'])}</code></small><small>Portal note ({len(note)} / 200 characters): <code>{esc(note)}</code></small></div><a class="button" href="downloads/{esc(file_name)}" download>↓ Download .TIF</a><a class="button" href="downloads/{esc(Path(file_name).stem)}.zip" download>↓ Download one-TIFF .ZIP</a></section>'''

    registered = deviation.get("registered_h55_log_edge_inputs", {})
    implemented = deviation.get("implemented_new_h55_log_edge_inputs", {})
    body = f'''{downloads}<div class="eyebrow">H55-EDGE · separate negative-result archive · no incumbent change</div><h1>Paired gravity–RTP edges.<br>Not promoted.</h1>{status}<p class="lede">This page records a preregistered edge-transform experiment. It is distinct from the main H55 candidate and the H55-PROFILE follow-up; the global <code>submission/LATEST.txt</code> pointer is left untouched. See {link('h55.html','the main H55 candidate')} and {link('h55-profile.html','H55-PROFILE')} for those separate releases.</p><div class="grid"><div class="card"><div class="metric">{budget:,}</div><div class="label">metric-placed cells</div></div><div class="card"><div class="metric">{fmt(hold['means'][candidate])}</div><div class="label">H55-EDGE mean local holdout DTI</div></div><div class="card"><div class="metric">{lift:+.6f}</div><div class="label">paired lift vs {esc(baseline)} · {positive}/{hold['total_folds']} folds positive</div></div><div class="card"><div class="metric">{int(sub['submission_slots_used'])}</div><div class="label">weekly slots used by H55-EDGE</div></div></div><h2>Spatially blocked comparison</h2><p>Four contiguous, spatially blocked whole-component folds; 80-pixel separation buffer; matched 37,654-pixel budget. Catalogue-zero cells are proxy negatives, so these local known-catalogue hide/recover scores do not forecast hidden-label or leaderboard performance.</p>{fold_table}<p>Required gate: mean lift ≥{threshold:.3f} and at least {positive_needed}/{hold['total_folds']} positive folds. Observed: <strong>{lift:+.6f}, {positive}/{hold['total_folds']}</strong>. The candidate did not pass.</p><p>{link('data/h55_edge_holdout.json','Full fold and metric receipt')} · {link('data/h55_edge_independence.json','Blockwise OOF negative-error diagnostic')} (maximum absolute measured correlation {float(indep['max_abs_correlation']):.6f}; this is not proof of conditional independence) · {link('data/h55_edge_pseudo_exchange.json','separate buffered pseudo-label arm')}.</p><h2>Protocol deviation (preserved, not retrofitted)</h2><p>The frozen preregistration named new LoG transforms for gravity bands {esc(registered.get('gravity', '13/11/18'))} and RTP magnetic bands {esc(registered.get('magnetic', '2/9'))}. The implementation transformed only gravity band 13 and RTP band 2. The holdout and release receipt therefore describe this narrower implementation only; the omitted channels were not tested. The preregistration file is unchanged; no same-fold retuning is implied.</p><p>{link('data/h55_edge_preregistration.json','Frozen H55-EDGE preregistration')} · {link('data/h55_edge_protocol_deviation.json','Post-run protocol-deviation receipt')}.</p><p><strong>Execution provenance:</strong> The validator and shared R2 modules were run before merging the later main-branch H55 work. The source snapshot and per-file SHA-256 values are preserved in {link('data/h55_edge_execution_provenance.json','the execution-provenance receipt')} and <a href="https://github.com/buffedlizard55-lab/GEMSDOE52/commit/709ac3b376e9f4d102de41865ae30f4a3dd0b728">commit 709ac3b</a>. Paths were namespaced afterward; a post-merge rerun is not the original experiment. Large ignored input rasters and feature caches are not in the repository, and owner-pinned bytes are not organizer-authenticated.</p><h2>Support novelty and output integrity</h2><p>Decoded canonical-pattern uniqueness: <strong>{esc(uniqueness['canonical_pattern_unique'])}</strong>. Strict ≥20% support-novelty gate: <strong>{esc(uniqueness['support_novelty_gate_ok'])}</strong>; measured novel fraction {float(uniqueness['novel_fraction']):.1%} over {int(uniqueness['n_priors_checked'])} accessible aligned priors. The support diagnostic remains failed for slot use; it is not waived. The raster is a new model inference, not a copied, renamed, recompressed, or literal-union prior file.</p><p>On-disk read-back: one float32 band, shape {fmt_receipt['height']} × {fmt_receipt['width']}, EPSG:32611, finite range [{fmt_receipt['min']}, {fmt_receipt['max']}], {int(fmt_receipt['n_nonzero']):,} nonzero cells, and no positive output outside the sample footprint. These are local checks, not portal acceptance.</p><p>{link('data/h55_edge_uniqueness.json','Per-prior uniqueness audit')} · {link('data/h55_edge_release_verification.json','Release byte/format receipt')} · {link(report_link,'Complete submission audit JSON')}.</p>{picture}<h2>A-only pixel reasoning — measurements, not geological confirmation</h2><p>The accompanying CSV has {int(reasoning['rows'])} rows, one for each emitted H55-EDGE point in the A-confident/B-abstaining stratum. Of these, {zero_pairs} have zero measured paired sigma-3 edge response and {positive_pairs} have a positive response; do not describe all A-only points as coincident-edge locations. The row-level notes list measured bands 15/19 and signed-LoG values, plus alternatives; scores are not calibrated fault probabilities.</p><p>{link('downloads/'+reasoning['file'],'Download the per-pixel reasoning CSV')} · {link('downloads/'+Path(file_name).stem+'-audit.json','Full on-disk audit receipt')}.</p><p>Potential-field contrasts can reflect lithologic contacts, intrusions, alteration, processing seams, or other non-fault causes. No displacement, geothermal flow, vent, or field confirmation is reported. Owner-side SHA pins are not organizer-byte authentication.</p><h2>Source boundary</h2><ul><li>{link('https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/','Official competition task and metric')}: fault labels may be incomplete or inaccurate; this local holdout is not hidden-label evaluation.</li><li>{link('https://pubs.usgs.gov/of/2000/0189/pdf/of00-189.pdf','USGS OF 00-189')} and {link('https://pubs.usgs.gov/of/2000/of00-188/of00-188print.pdf','USGS OF 00-188')}: regional gravity/magnetic context includes competing lithologic and fluvial explanations; neither validates these pixels.</li><li>{link('https://docs.nlr.gov/docs/fy26osti/96647.pdf','Official rules')}: weekly slot limits and AI-disclosure requirements; H55-EDGE used no slot.</li><li>{link('https://gdr.openei.org/submissions/1391','GDR submission 1391')}: metadata advertises data not retrieved or used in H55-EDGE.</li></ul><p>{link('data/h55_edge_source_review.json','Full source/access review')} · {link('https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/13_ai_use_h55_edge.md','AI-use disclosure')}.</p>'''
    (DOCS / "h55-edge.html").write_text(page("H55-EDGE negative result and research-only artifact", body))

    archive_text = (f"Mean spatial holdout lift {lift:+.6f}, positive in {positive}/{hold['total_folds']} folds; "
                    f"required {threshold:+.3f} and {positive_needed}/{hold['total_folds']}. Strict support-novelty gate also failed. No slot or score.")
    archive = f'''<section id="h55-edge-archive" class="card"><h2>H55-EDGE potential-field experiment — failed gates, research only</h2><p>{esc(archive_text)}</p><p><a href="downloads/{esc(file_name)}" download>Download research TIFF</a> · <a href="downloads/{esc(Path(file_name).stem)}.zip" download>one-TIFF ZIP</a> · <a href="downloads/{esc(reasoning['file'])}">A-only reasoning CSV</a> · <a href="h55-edge.html">Full H55-EDGE audit</a></p></section>'''
    archive_downloads = f'''<section id="h55-edge-archive" class="card"><h2>H55-EDGE potential-field experiment — failed gates, research only</h2><p>{esc(archive_text)}</p><p><a href="{esc(file_name)}" download>Download research TIFF</a> · <a href="{esc(Path(file_name).stem)}.zip" download>one-TIFF ZIP</a> · <a href="{esc(reasoning['file'])}">A-only reasoning CSV</a> · <a href="../h55-edge.html">Full H55-EDGE audit</a></p></section>'''
    upsert_section(DOCS / "h55.html", "<!--H55EDGE-ARCHIVE-->", "<!--/H55EDGE-ARCHIVE-->", archive, after="<main id=\"main\">")
    upsert_section(DOCS / "index.html", "<!--H55EDGE-ARCHIVE-->", "<!--/H55EDGE-ARCHIVE-->", archive, after="<!--/H55PROFILE-->")
    upsert_section(DOCS / "downloads/index.html", "<!--H55EDGE-ARCHIVE-->", "<!--/H55EDGE-ARCHIVE-->", archive_downloads, after="</h1>")
    print(f"Published H55-EDGE archive only; preserved current main pointer and H55 candidate ({file_name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
