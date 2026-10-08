"""Legacy package: the earlier sessions' implementation of this competition (PR #1 and PR #2),
kept runnable and untouched under its own name.

It lives here, rather than inside ``gems52``, because this repo now carries a second,
independently-tested implementation of the same official metric, and two incompatible ``metric.py``
modules in one package is how a repository stops being checkable. Nothing was rewritten: these are
the bytes from ``origin/main``. The measurements that PR #1/#2 produced are still published in
``evidence/`` (``cotraining_rounds.json``, ``holdout_validation.json``, ``uniqueness_gate.json``,
``a_only_geological_reasoning.json`` and the rest); only the import path moved, so their own test
suite (``tests/test_gems52_h1_pipeline.py``) still runs against their own code.
"""
"""GEMSDOE52: Blum-Mitchell (COLT '98) Two-View Co-Training & Disagreement Discovery
for the DOE GEMS Prize Challenge (DrivenData #306, GeoDAWN / Great Basin).
"""

__version__ = "1.0.0"
