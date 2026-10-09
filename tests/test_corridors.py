"""Sanity tests for the H8 corridor surfaces (deterministic rules, no label fitting)."""
import numpy as np

from gems53.corridors import (
    prune_mask,
    relay_surface,
    segment_table,
    tip_continuation_surface,
    tips_and_strikes,
)


def test_segment_table_counts():
    vis = np.zeros((50, 50), dtype=bool)
    vis[10:12, 5:20] = True          # horizontal segment
    vis[30:45, 40:42] = True         # vertical segment
    L, n, rows_list, cols_list = segment_table(vis)
    assert n == 2
    assert sum(len(r) for r in rows_list) == int(vis.sum())


def test_tips_point_outward():
    vis = np.zeros((50, 50), dtype=bool)
    vis[25, 10:30] = True            # horizontal segment, centre row 25
    rows = np.nonzero(vis)[0]
    cols = np.nonzero(vis)[1]
    recs = tips_and_strikes(rows, cols)
    assert len(recs) == 2
    (t0, s0, _), (t1, s1, _) = recs
    # tips at the two ends
    assert abs(t0[1] - 10) <= 1 or abs(t0[1] - 29) <= 1
    # outward strikes point away from the segment centre
    centre_col = cols.mean()
    assert (t0[1] - centre_col) * s0[0] > 0
    assert (t1[1] - centre_col) * s1[0] > 0


def test_tip_surface_extends_beyond_tip():
    vis = np.zeros((80, 80), dtype=bool)
    vis[40, 20:40] = True
    s = tip_continuation_surface(vis, reach_px=30)
    beyond = s[38:43, 42:48].max()      # just past the right tip
    far = s[38:43, 60:70].max()         # 20-30 px past the tip
    behind = s[38:43, 10:16].max()      # past the left tip (other branch)
    on = s[40, 30]
    assert beyond > 0.3, beyond
    assert 0 < far < beyond, (far, beyond)   # decaying
    assert behind > 0.3
    assert on <= 1.0 + 1e-6


def test_relay_surface_between_facing_tips():
    vis = np.zeros((120, 120), dtype=bool)
    vis[40, 10:60] = True             # lower segment
    vis[52, 45:100] = True            # overlapping, 12 px above at the overlap
    s = relay_surface(vis, max_gap_px=60)
    mid = s[42:50, 50:70].max()       # between the facing tips
    far = s[80:100, 50:70].max()      # away from both
    assert mid > 0.05, mid
    assert far == 0.0


def test_relay_requires_overlap():
    vis = np.zeros((120, 120), dtype=bool)
    vis[40, 10:40] = True
    vis[52, 70:100] = True            # no along-strike overlap
    s = relay_surface(vis, max_gap_px=60)
    assert s.max() == 0.0


def test_prune_mask():
    vis = np.zeros((30, 30), dtype=bool)
    vis[15, 15] = True
    m = prune_mask(vis, px=2)
    assert not m[15, 15]
    assert not m[15, 16] and not m[15, 17]     # 1 px and 2 px away are pruned ("within 2 px")
    assert m[15, 18]                            # 3 px away is allowed
