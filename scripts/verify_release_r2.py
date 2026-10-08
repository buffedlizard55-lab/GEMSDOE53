#!/usr/bin/env python3
"""Pass-3 on-disk release check, including the matched-budget max-view union."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import zipfile

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from gems52 import gates
import run_structural_pipeline as pipeline


def main():
    receipt_path = ROOT / 'evidence/submission_r2.json'
    receipt = json.loads(receipt_path.read_text())
    path = ROOT / 'docs/downloads' / receipt['file']
    with rasterio.open(path) as src:
        prediction, mask = src.read(1), src.dataset_mask() > 0
        assert src.count == 1 and src.dtypes == ('float32',)
        assert np.isfinite(prediction).all() and 0 <= prediction.min() <= prediction.max() <= 1
    with rasterio.open(ROOT / 'data/sample_submission.tif') as src:
        sample = src.read(1, masked=True)
        fp = ~np.ma.getmaskarray(sample) & np.isfinite(sample.data) & (sample.data > -1e38)
        assert np.array_equal(mask, fp)
    fmt = gates.format_report(path, ROOT / 'data/sample_submission.tif')
    assert fmt['ok'] and fmt['sha256'] == receipt['sha256']
    with zipfile.ZipFile(path.with_suffix('.zip')) as archive:
        assert archive.namelist() == [path.name]
        assert hashlib.sha256(archive.read(path.name)).hexdigest() == receipt['sha256']
    why = receipt['a_only_reasoning']
    csv_path = ROOT / 'docs/downloads' / why['file']
    rows = list(csv.DictReader(csv_path.open()))
    assert len(rows) == why['rows'] == receipt['stats_by_stratum']['A_only']
    assert hashlib.sha256(csv_path.read_bytes()).hexdigest() == why['sha256']
    assert len({row['candidate_id'] for row in rows}) == len(rows)
    for row in rows:
        assert prediction[int(row['row']), int(row['col'])] == 1
        assert 'MODEL HYPOTHESIS' in row['verification_status']
    # The literal union of two 37,654-pixel view outputs is a weak/trivial control;
    # also compare the max-probability union field re-emitted at the SAME budget.
    valid = np.load(ROOT / 'work/r2/features/valid.npy')
    with rasterio.open(ROOT / 'data/labels.tif') as src:
        cat = src.read(1) == 1
    pa = np.load(ROOT / 'work/r2/final/view_A.npy')
    pb = np.load(ROOT / 'work/r2/final/view_B.npy')
    prior = receipt['training']['catalogue_prior']
    union_pred, stats = pipeline.place(pipeline.prior_adjust(np.maximum(pa, pb), prior), valid, cat, valid, 37654)
    comparison = dict(equal=bool(np.array_equal(prediction, union_pred)),
        emitted=int(union_pred.sum()), intersection=int(((prediction > 0) & (union_pred > 0)).sum()),
        novel_vs_matched_max_union=int(((prediction > 0) & ~(union_pred > 0)).sum()),
        matched_max_union_pixels_dropped=int(((union_pred > 0) & ~(prediction > 0)).sum()), placement=stats)
    assert not comparison['equal'], 'Candidate is just a matched-budget max-view union'
    receipt['view_comparison']['matched_budget_max_union'] = comparison
    receipt['view_comparison']['not_merely_union'] &= not comparison['equal']
    # Keep original scientific and saturated-support failures; never force promotion.
    assert not receipt['validation']['approved_for_slot'] and not receipt['promoted']
    assert receipt['official_score'] is None
    output = json.dumps(receipt, indent=2, allow_nan=False) + '\n'
    receipt_path.write_text(output)
    (ROOT / 'evidence' / ('submission_' + path.stem + '.json')).write_text(output)
    (path.parent / (path.stem + '-audit.json')).write_text(output)
    (ROOT / 'evidence/not_union_r2.json').write_text(json.dumps(receipt['view_comparison'], indent=2) + '\n')
    proof = dict(tiff_sha256=receipt['sha256'], raw_range_and_geometry=True,
        mask_exact=True, zip_single_tiff_bytes_match=True, a_only_rows=len(rows),
        every_reasoning_pixel_emitted=True, matched_budget_max_union=comparison,
        scientific_slot_approval=False, official_score=None)
    (ROOT / 'evidence/release_verification_r2.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
