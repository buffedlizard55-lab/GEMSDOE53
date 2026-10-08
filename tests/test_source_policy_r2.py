"""No unauthorized network call or false freshness from the local feed."""
from pathlib import Path
import importlib.util
import json

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disabled_board_fetch_never_opens_url(monkeypatch):
    feed = load_script('refresh_feed')
    snapshots = sorted((ROOT / 'registry').glob('leaderboard_snapshot_*.json'))
    old = json.loads(snapshots[-1].read_text())
    observation_key = 'fetched_utc' if 'fetched_utc' in old else 'observed_date_utc'
    def fail(*args, **kwargs):
        raise AssertionError('Network called despite disabled policy')
    monkeypatch.setattr(feed.urllib.request, 'urlopen', fail)
    result = feed.fetch_board(True)
    assert not result['automated_fetch_allowed']
    assert result['fetch_requested_but_disabled']
    assert result[observation_key] == old[observation_key]


def test_source_crawler_applies_policy_before_any_network(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    audit = load_script('review_sources')
    def fail(*args, **kwargs):
        raise AssertionError('Network called despite disabled policy')
    monkeypatch.setattr(audit.urllib.request, 'urlopen', fail)
    with pytest.raises(PermissionError, match='disabled'):
        audit.get('https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/')


def test_dense_control_does_not_make_fresh_sparse_pattern_a_copy(tmp_path):
    from test_gates import write_tif
    from gems52 import gates
    dense = np.ones((6, 6), np.float32)
    p = np.zeros_like(dense); p[3, 3] = 1
    result = gates.uniqueness_report(p, [write_tif(tmp_path, 'density_probe.tif', dense)])
    assert result['canonical_pattern_unique']
    assert result['research_publication_ok']
    assert not result['equals_literal_prior_union']
    assert result['novel_fraction'] == 0
    assert not result['support_novelty_gate_ok']
    assert not result['ok']  # original failed diagnostic is not relabelled passed


def test_literal_union_remains_blocked_for_research_publication(tmp_path):
    from test_gates import write_tif
    from gems52 import gates
    a = np.zeros((6, 6), np.float32); a[1, 1] = 1
    b = np.zeros_like(a); b[4, 4] = 1
    result = gates.uniqueness_report(a + b, [write_tif(tmp_path, 'a.tif', a), write_tif(tmp_path, 'b.tif', b)])
    assert result['canonical_pattern_unique']
    assert result['equals_literal_prior_union']
    assert not result['research_publication_ok']


def test_legacy_constant_correlations_fail_closed():
    from gems52 import cotrain
    result = cotrain.view_correlation(np.zeros(11), np.zeros(11))
    assert result['abandon'] and not result['measured']
    assert result['spearman_rho'] is None


def test_all_r2_json_is_strict_browser_json():
    def invalid(value):
        raise ValueError(value)
    for directory in (ROOT / 'evidence', ROOT / 'docs/data'):
        for path in directory.glob('*_r2.json'):
            json.loads(path.read_text(), parse_constant=invalid)
