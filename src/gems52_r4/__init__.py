"""Round-4 package: two-view co-training with a budget-confound-aware instrument.

Rebuilt from scratch on 2026-10-08 after a workspace reset destroyed the original
``src/gems52_r4/`` (uncommitted) together with every artifact in ``work/``.  The
rebuild keeps the designs that survived in the session record and adds the fixes
that were found the hard way:

* ``model.gather`` is element-wise -- ``np.ix_`` with three index arrays is a cross
  product and asked numpy for 5.90 TiB.
* ``instrument.budget_confound`` returns ``degenerate=True`` instead of the
  fabricated ``r=0.0, p=1.0`` it emitted when the residual was exactly zero.
* ``cotraining.whole_segment_folds`` separates the training-exclusion mask from the
  emission-allowed mask; conflating them silently produced 0.000 truth survival.
* ``cotraining.block_error_table`` ranks positives over ``pos | allowed``; ranking
  inside the emission mask made the miss rate all-NaN.

Every number this package emits is written through ``scripts/run_r4.jsonable`` so a
single NaN cannot cost an eight-minute receipt the way it did once.
"""

__all__ = ["layers", "model", "cotraining", "instrument", "arms", "bias", "reasoning"]
