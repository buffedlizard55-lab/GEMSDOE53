# Blocked-holdout arm table (hide, 4 folds, topk emission)

Prevalence matched at 0.200 % of the footprint; the visible catalogue is masked out of both the allowed set and the score, exactly as the organiser does. Mean DTI over folds; `|N` is the emission budget in pixels.

| arm | mean DTI | sd | best fold | worst fold |
|---|---|---|---|---|
| B_only|37654 | 0.0518 | 0.0150 | 0.0715 | 0.0328 |
| B_only|25000 | 0.0497 | 0.0170 | 0.0723 | 0.0276 |
| B_only|15000 | 0.0435 | 0.0191 | 0.0701 | 0.0187 |
| random|37654 | 0.0396 | 0.0056 | 0.0464 | 0.0308 |
| union|37654 | 0.0381 | 0.0115 | 0.0492 | 0.0222 |
| union_sup|37654 | 0.0379 | 0.0115 | 0.0506 | 0.0241 |
| B_only|8000 | 0.0364 | 0.0188 | 0.0624 | 0.0116 |
| union_sup|25000 | 0.0363 | 0.0132 | 0.0510 | 0.0187 |
| union|25000 | 0.0357 | 0.0128 | 0.0495 | 0.0184 |
| union_sup|15000 | 0.0327 | 0.0132 | 0.0487 | 0.0153 |
| union|15000 | 0.0324 | 0.0131 | 0.0479 | 0.0146 |
| random|25000 | 0.0316 | 0.0045 | 0.0372 | 0.0246 |
| union_sup|8000 | 0.0268 | 0.0128 | 0.0435 | 0.0111 |
| union|8000 | 0.0266 | 0.0123 | 0.0417 | 0.0105 |
| random|15000 | 0.0237 | 0.0022 | 0.0265 | 0.0209 |
| random|8000 | 0.0149 | 0.0006 | 0.0158 | 0.0140 |
| cotrain|37654 | 0.0078 | 0.0044 | 0.0119 | 0.0004 |
| cotrain|25000 | 0.0070 | 0.0046 | 0.0123 | 0.0006 |
| cotrain|15000 | 0.0065 | 0.0044 | 0.0118 | 0.0004 |
| cotrain_sup|25000 | 0.0060 | 0.0053 | 0.0145 | 0.0001 |
| cotrain_sup|37654 | 0.0060 | 0.0052 | 0.0142 | 0.0001 |
| A_only|37654 | 0.0060 | 0.0035 | 0.0092 | 0.0001 |
| cotrain_sup|15000 | 0.0056 | 0.0055 | 0.0142 | 0.0000 |
| A_only|25000 | 0.0055 | 0.0036 | 0.0097 | 0.0000 |
| A_sup|37654 | 0.0050 | 0.0036 | 0.0104 | 0.0004 |
| cotrain|8000 | 0.0048 | 0.0031 | 0.0083 | 0.0003 |
| A_only|15000 | 0.0046 | 0.0033 | 0.0088 | 0.0000 |
| A_sup|25000 | 0.0045 | 0.0027 | 0.0079 | 0.0005 |
| A_sup|15000 | 0.0042 | 0.0022 | 0.0067 | 0.0007 |
| cotrain_sup|8000 | 0.0039 | 0.0038 | 0.0095 | 0.0000 |
| A_sup|8000 | 0.0038 | 0.0022 | 0.0067 | 0.0005 |
| A_only|8000 | 0.0035 | 0.0024 | 0.0063 | 0.0000 |
| corridor_blanket|37654 | 0.0006 | 0.0004 | 0.0012 | 0.0000 |
| corridor_blanket|25000 | 0.0004 | 0.0004 | 0.0010 | 0.0000 |
| corridor_blanket|15000 | 0.0002 | 0.0004 | 0.0009 | 0.0000 |
| cotrain_cor|37654 | 0.0002 | 0.0003 | 0.0007 | 0.0000 |
| union_cor|25000 | 0.0001 | 0.0002 | 0.0005 | 0.0000 |
| union_cor|37654 | 0.0001 | 0.0002 | 0.0004 | 0.0000 |
| A_only_cor|37654 | 0.0001 | 0.0002 | 0.0004 | 0.0000 |
| union_cor|15000 | 0.0001 | 0.0002 | 0.0004 | 0.0000 |
| corridor_blanket|8000 | 0.0000 | 0.0001 | 0.0001 | 0.0000 |
| union_cor|8000 | 0.0000 | 0.0000 | 0.0001 | 0.0000 |
| cotrain_cor|8000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cotrain_cor|15000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| cotrain_cor|25000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| A_only_cor|8000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| A_only_cor|15000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| A_only_cor|25000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Conditional-independence test (the premise of the method)

- cells: 11 (fold x block) | threshold |r| < 0.6
- false-alarm correlation across cells: -0.1406 (Spearman -0.2273)
- miss correlation across cells: -0.2881 (Spearman -0.2364)
- pixel-level logit correlation on non-catalogue pixels, pooled: 0.1103
- **independent enough: True** - the two views' false-alarm structure is weakly coupled, so a pixel where one view is confident and the other withholds is carrying information the confident view alone does not have


## Gates

- tested arm: `cotrain|37654`
- `beats_union`: {'delta': -0.03027, 'need': 0.01, 'ok': False} -> NOT OK
- `beats_single_view`: {'delta': 0.00183, 'need': 0.0, 'ok': True} -> OK
- `placement_not_mass`: {'delta': -0.03183, 'need': 0.0, 'ok': False} -> NOT OK
- `fold_support`: {'wins': '0/4', 'need': 3, 'ok': False} -> NOT OK
- **promoted: False** (gates not cleared: beats_union, placement_not_mass, fold_support)
