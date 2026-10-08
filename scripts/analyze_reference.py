#!/usr/bin/env python3
"""Measure the 0.2778 reference edit, without pretending to know hidden truth."""
from pathlib import Path
import json
import sys

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

BASE_URL = 'https://buffedlizard55-lab.github.io/GEMSDOE28/docs/downloads/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif'
REFERENCE_URL = 'https://buffedlizard55-lab.github.io/GEMSDOE32/docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif'


def load(path):
    with rasterio.open(path) as src:
        return np.nan_to_num(src.read(1), nan=0) > 0


def main():
    entries = json.loads((ROOT / 'evidence/prior_inventory_r2.json').read_text())['entries']
    by_url = {r['url']: r for r in entries if r.get('eligible_prior')}
    base_row, ref_row = by_url[BASE_URL], by_url[REFERENCE_URL]
    base, ref = load(ROOT / base_row['local_path']), load(ROOT / ref_row['local_path'])
    cat = load(ROOT / 'data/labels.tif')
    dist = ndi.distance_transform_edt(~cat)
    removed, added = base & ~ref, ref & ~base
    bands = {'on_catalogue': dist == 0, 'off_catalogue_le_200m': (dist > 0) & (dist <= 2),
             '200_to_300m': (dist > 2) & (dist <= 3), 'farther_than_300m': dist > 3}
    report = dict(base=base_row, reference=ref_row, base_pixels=int(base.sum()), reference_pixels=int(ref.sum()),
                  removed_pixels=int(removed.sum()), added_pixels=int(added.sum()),
                  removed_by_distance={k: int((removed & v).sum()) for k, v in bands.items()},
                  reference_pixels_within_200m_of_catalogue=int((ref & (dist <= 2)).sum()),
                  equals_base_with_200m_flank_deleted=bool(np.array_equal(ref, base & (dist > 2))),
                  equals_base_with_catalogue_pixels_deleted=bool(np.array_equal(ref, base & ~cat)),
                  attributed_public_scores={'base': 0.2708, 'reference': 0.2778, 'evidence_class': 'user/owner-reported filename attribution, not organizer-authenticated'},
                  relative_reported_score_change=0.2778 / 0.2708 - 1,
                  attribution_limit='Leaderboard exposes participant best scores, not artifact filenames, checksums or hidden scoring terms. Cannot recover TP/FP/FN or prove cause of gain.',
                  staff_mask_url='https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4',
                  metric_url='https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/',
                  marginal_rule='c*(1 - 0.2*DTI) > 0.2*DTI*f, c=incremental max-cover credit, f=1-max_g kernel against NEW truth',
                  single_uncovered_pixel_special_case={'bar_at_02778': 0.2 * 0.2778,
                          'kernel_at_diagonal_200m_200m': 1 - np.sqrt(8) / 3,
                          'diagonal_clears_bar_at_02778': bool(1 - np.sqrt(8) / 3 > 0.2 * 0.2778),
                          'note': 'No universal distance-only rule: multiple/previously-covered truth pixels change incremental credit.'},
                  same_FP_and_truth_required_TP_ratio_to_03774=(0.3774 / (1 - 0.2 * 0.3774)) / (0.2778 / (1 - 0.2 * 0.2778)),
                  pure_pruning_metric_constraints='Same truth/mask: subset cannot increase TPw/FPw or decrease FNw. Gain requires FP reduction outweighing lost max-cover credit.',
                  removal_help_rule='lost_credit*(1-0.2*baseline_DTI) < 0.2*baseline_DTI*removed_FP_mass',
                  new_truth_prevalence_identifiable_from_public_scores=False,
                  previous_0464_ceiling_supported=False,
                  conclusion='Reference is a near-catalogue flank ablation of a sparse dotted field. Known pixels are masked and do NOT pay a penalty. Improvement is consistent with reducing weak off-catalogue prediction mass, but hidden truth and authenticated paired submissions are needed for causal attribution.')
    (ROOT / 'evidence/reference_forensics_r2.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('base', 'reference')}, indent=2))


if __name__ == '__main__':
    main()
