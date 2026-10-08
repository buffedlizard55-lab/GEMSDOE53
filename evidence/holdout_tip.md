# Blocked-holdout arm table (tip, 4 folds, topk emission)

Prevalence matched at 0.200 % of the footprint; the visible catalogue is masked out of both the allowed set and the score, exactly as the organiser does. Mean DTI over folds; `|N` is the emission budget in pixels.

| arm | mean DTI | sd | best fold | worst fold |
|---|---|---|---|---|
| union_cor|37654 | 0.0320 | 0.0125 | 0.0475 | 0.0147 |
| union_cor|25000 | 0.0302 | 0.0104 | 0.0406 | 0.0149 |
| B_only|25000 | 0.0296 | 0.0051 | 0.0370 | 0.0242 |
| B_only|37654 | 0.0291 | 0.0069 | 0.0360 | 0.0209 |
| B_only|15000 | 0.0284 | 0.0057 | 0.0382 | 0.0238 |
| union_cor|15000 | 0.0269 | 0.0097 | 0.0381 | 0.0144 |
| B_only|8000 | 0.0255 | 0.0083 | 0.0378 | 0.0169 |
| random|37654 | 0.0253 | 0.0084 | 0.0360 | 0.0127 |
| union_sup|25000 | 0.0247 | 0.0066 | 0.0335 | 0.0176 |
| union_sup|37654 | 0.0245 | 0.0076 | 0.0320 | 0.0159 |
| union|25000 | 0.0244 | 0.0075 | 0.0343 | 0.0163 |
| union|37654 | 0.0240 | 0.0077 | 0.0319 | 0.0142 |
| union_sup|15000 | 0.0231 | 0.0062 | 0.0337 | 0.0188 |
| union|15000 | 0.0229 | 0.0074 | 0.0350 | 0.0158 |
| random|25000 | 0.0216 | 0.0066 | 0.0301 | 0.0117 |
| union_cor|8000 | 0.0205 | 0.0081 | 0.0331 | 0.0129 |
| union_sup|8000 | 0.0200 | 0.0077 | 0.0316 | 0.0126 |
| union|8000 | 0.0198 | 0.0081 | 0.0322 | 0.0107 |
| cotrain_cor|37654 | 0.0179 | 0.0153 | 0.0425 | 0.0004 |
| random|15000 | 0.0174 | 0.0035 | 0.0214 | 0.0121 |
| A_only_cor|37654 | 0.0160 | 0.0131 | 0.0366 | 0.0004 |
| cotrain_cor|25000 | 0.0157 | 0.0132 | 0.0366 | 0.0002 |
| corridor_blanket|37654 | 0.0154 | 0.0111 | 0.0335 | 0.0045 |
| A_only_cor|25000 | 0.0151 | 0.0123 | 0.0345 | 0.0003 |
| corridor_blanket|25000 | 0.0133 | 0.0088 | 0.0279 | 0.0057 |
| A_only_cor|15000 | 0.0131 | 0.0101 | 0.0285 | 0.0002 |
| cotrain_cor|15000 | 0.0130 | 0.0094 | 0.0267 | 0.0003 |
| random|8000 | 0.0115 | 0.0018 | 0.0137 | 0.0095 |
| corridor_blanket|15000 | 0.0114 | 0.0062 | 0.0216 | 0.0060 |
| A_only_cor|8000 | 0.0113 | 0.0082 | 0.0229 | 0.0003 |
| cotrain_cor|8000 | 0.0106 | 0.0083 | 0.0231 | 0.0004 |
| cotrain|25000 | 0.0086 | 0.0069 | 0.0193 | 0.0002 |
| cotrain|37654 | 0.0084 | 0.0066 | 0.0186 | 0.0001 |
| cotrain_sup|25000 | 0.0084 | 0.0083 | 0.0221 | 0.0000 |
| cotrain|15000 | 0.0084 | 0.0073 | 0.0198 | 0.0003 |
| cotrain_sup|37654 | 0.0084 | 0.0085 | 0.0226 | 0.0000 |
| corridor_blanket|8000 | 0.0084 | 0.0035 | 0.0142 | 0.0047 |
| A_sup|37654 | 0.0080 | 0.0073 | 0.0200 | 0.0003 |
| A_sup|25000 | 0.0076 | 0.0060 | 0.0169 | 0.0005 |
| A_only|25000 | 0.0076 | 0.0058 | 0.0160 | 0.0002 |
| cotrain_sup|15000 | 0.0076 | 0.0084 | 0.0214 | 0.0000 |
| A_sup|15000 | 0.0076 | 0.0052 | 0.0151 | 0.0007 |
| A_only|15000 | 0.0075 | 0.0057 | 0.0152 | 0.0002 |
| A_only|37654 | 0.0075 | 0.0059 | 0.0166 | 0.0001 |
| cotrain|8000 | 0.0072 | 0.0065 | 0.0175 | 0.0004 |
| cotrain_sup|8000 | 0.0068 | 0.0075 | 0.0191 | 0.0000 |
| A_sup|8000 | 0.0058 | 0.0031 | 0.0085 | 0.0006 |
| A_only|8000 | 0.0056 | 0.0043 | 0.0111 | 0.0000 |

## Conditional-independence test (the premise of the method)

- cells: 11 (fold x block) | threshold |r| < 0.6
- false-alarm correlation across cells: 0.4298 (Spearman 0.4455)
- miss correlation across cells: -0.3114 (Spearman -0.5000)
- pixel-level logit correlation on non-catalogue pixels, pooled: 0.1443
- **independent enough: True** - the two views' false-alarm structure is weakly coupled, so a pixel where one view is confident and the other withholds is carrying information the confident view alone does not have


## Gates

- tested arm: `cotrain|25000`
- `beats_union`: {'delta': -0.01582, 'need': 0.01, 'ok': False} -> NOT OK
- `beats_single_view`: {'delta': 0.00097, 'need': 0.0, 'ok': True} -> OK
- `placement_not_mass`: {'delta': -0.01667, 'need': 0.0, 'ok': False} -> NOT OK
- `fold_support`: {'wins': '0/4', 'need': 3, 'ok': False} -> NOT OK
- **promoted: False** (gates not cleared: beats_union, placement_not_mass, fold_support)
