#!/usr/bin/env python3
"""Run the H53-1 detector in the order that makes the expensive half cacheable.

    # pass 1 only  (~2 min, 350 MB): candidates + per-tile azimuths -> work/dicoincidence/tiles.npz
    PYTHONPATH=src .venv/bin/python scripts/h53_detect.py --stage tiles

    # statistics + arms (~1 min, re-reads nothing heavy): needs tiles.npz and nodes.npz
    PYTHONPATH=src .venv/bin/python scripts/h53_detect.py --stage stats

    # node evidence only (~8 min): needs tiles.npz, writes nodes.npz
    PYTHONPATH=src .venv/bin/python scripts/h53_detect.py --stage nodes

`--stage all` does everything.  Each stage is idempotent and writes its own artefact, so a statistic
can be corrected without re-deriving sixteen structure tensors, and the failure of one stage cannot
silently invalidate another.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import dicoincidence as DC      # noqa: E402

WORK = ROOT / "work" / "dicoincidence"
EV = ROOT / "evidence"


def stage_tiles(args) -> dict:
    tiles = DC.build_tiles(work_dir=str(WORK), sigma_tensor_m=args.sigma_tensor_m,
                           tile_px=args.tile_px, topk_per_channel=args.topk,
                           coh_gate=args.coh_gate, persist_gate=args.persist_gate)
    return tiles


def stage_stats(args, tiles: dict | None = None) -> dict:
    if tiles is None:
        tiles = DC.load_tiles(work_dir=str(WORK))
        tiles["cand_union"] = None
    pairs, pm = DC.coincidence_table(tiles, n_perm=args.n_perm, seed=args.seed)
    z = np.load(WORK / "nodes.npz")
    node = {k: z[k] for k in z.files}
    arms, meta = DC.arm_scores(node, pairs, pm["pct_by_pair"], z_gate=pm["z_gate"],
                               agree_deg=args.agree_deg, tile_pct_gate=args.tile_pct)
    np.savez_compressed(WORK / "arms.npz", **{k: v.astype(np.float32) for k, v in arms.items()})
    ev = {
        "what": "H53-1 cross-dataset orientation coincidence, permutation-calibrated",
        "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tile_px": tiles.get("tile_px", args.tile_px),
        "tile_km": tiles.get("tile_px", args.tile_px) * 100.0 / 1000.0,
        "sigma_tensor_m": tiles.get("sigma_tensor_m", args.sigma_tensor_m),
        "n_perm": args.n_perm, "seed": args.seed,
        "agree_deg": args.agree_deg,
        "coh_gate": tiles.get("coh_gate", args.coh_gate),
        "persist_gate": tiles.get("persist_gate", args.persist_gate),
        "topk_per_channel": tiles.get("topk_per_channel", args.topk),
        "candidate_union_px": int(tiles.get("candidate_px") or
                                  (int(tiles["cand_union"].sum()) if tiles.get("cand_union")
                                   is not None else -1)),
        "n_nodes": int(node["row"].size),
        "channels": [{"key": c.key, "path": c.path, "band": c.band, "family": c.family,
                      "physical": c.physical,
                      "n_candidates": tiles["per_channel"][c.key]["n_candidates"],
                      "tiles_with_azimuth": int(np.isfinite(tiles["per_channel"][c.key]["theta"]).sum())}
                     for c in DC.CHANNELS],
        "coincidence_pairs": pairs,
        "z_gate": pm["z_gate"],
        "arm_meta": meta,
        "tile_pct_gate": args.tile_pct,
        "arm_sizes": {k: int((v > 0).sum()) for k, v in arms.items()},
    }
    EV.mkdir(exist_ok=True)
    (EV / "dicoincidence.json").write_text(json.dumps(ev, indent=1, default=str))
    print(json.dumps({k: v for k, v in ev.items() if k not in ("coincidence_pairs", "channels")},
                     indent=1, default=str))
    print("\ntop coincidences by z (global same-map agreement):")
    for p in sorted(pairs, key=lambda r: -r["z"])[:8]:
        print(f"  {p['a']:14s} vs {p['b']:14s} obs {p['obs']:+.3f} null {p['null_mean']:+.4f}"
              f"+-{p['null_sd']:.4f} z {p['z']:+8.1f} p {p['p']:.4f} "
              f"tiles_z>=3 {p['tile_z_share_ge3']:.4f} tiles={p['n_tiles']}")
    return ev


def stage_nodes(args, tiles: dict | None = None) -> dict:
    tiles = tiles or stage_tiles(args)
    pairs, pm = DC.coincidence_table(tiles, n_perm=args.n_perm, seed=args.seed)
    node = DC.build_nodes(tiles, pairs, work_dir=str(WORK), seed=args.seed)
    arms, meta = DC.arm_scores(node, pairs, pm["pct_by_pair"], z_gate=pm["z_gate"],
                               agree_deg=args.agree_deg, tile_pct_gate=args.tile_pct)
    np.savez_compressed(WORK / "arms.npz", **{k: v.astype(np.float32) for k, v in arms.items()})
    return node


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="stats", choices=["tiles", "stats", "nodes", "all"])
    ap.add_argument("--sigma-tensor-m", type=float, default=300.0)
    ap.add_argument("--tile-px", type=int, default=DC.TILE_PX)
    ap.add_argument("--topk", type=int, default=60_000)
    ap.add_argument("--coh-gate", type=float, default=0.30)
    ap.add_argument("--persist-gate", type=float, default=0.35)
    ap.add_argument("--agree-deg", type=float, default=22.5)
    ap.add_argument("--n-perm", type=int, default=400)
    ap.add_argument("--tile-pct", type=float, default=0.90)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.stage == "tiles":
        stage_tiles(args)
    elif args.stage == "stats":
        stage_stats(args)
    elif args.stage == "nodes":
        stage_nodes(args)
    else:
        tiles = stage_tiles(args)
        stage_nodes(args, tiles)
        stage_stats(args, tiles)
    return 0


if __name__ == "__main__":
    sys.exit(main())
