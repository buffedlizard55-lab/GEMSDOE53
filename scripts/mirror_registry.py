#!/usr/bin/env python3
"""Mirror the public GEMSDOE* registry rasters (input to scripts/uniqueness_check.py).

For every public repo buffedlizard55-lab/<GEMSDOE*> that the registry inventory was built from:
  1. shallow-clone it into <workdir>/repos/<REPO> (depth 1),
  2. flatten every *.tif it contains into <outdir>/<REPO>__<repo-relative path with / -> __>,
  3. delete the clone's .git to save disk (the flattened rasters are the only thing kept).

The repo list defaults to the repos named in evidence/registry_inventory/inventory.json, so the
mirror always matches the audited population. Nothing is written into this repository.

Usage:
    python scripts/mirror_registry.py                     # -> /tmp/g53/uniq
    python scripts/mirror_registry.py --outdir /tmp/g53/uniq --workdir /tmp/g53/repos
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB = "https://github.com/buffedlizard55-lab"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default="/tmp/g53/uniq")
    ap.add_argument("--workdir", default="/tmp/g53/repos")
    ap.add_argument("--inventory", default=str(ROOT / "evidence" / "registry_inventory" / "inventory.json"))
    args = ap.parse_args()

    inv = json.loads(Path(args.inventory).read_text())
    repos = sorted({r["file"].split("__")[0] for r in inv["rows"]})
    outdir = Path(args.outdir)
    workdir = Path(args.workdir)
    outdir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)

    n_files = 0
    for repo in repos:
        dst = workdir / repo
        if not (dst / ".git").exists():
            print(f"cloning {repo} ...", flush=True)
            r = subprocess.run(["git", "clone", "--depth", "1", f"{GITHUB}/{repo}.git", str(dst)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  FAILED {repo}: {r.stderr.strip()[:300]}", flush=True)
                continue
        tifs = sorted(p for p in dst.rglob("*.tif") if p.is_file())
        for p in tifs:
            rel = p.relative_to(dst).as_posix()
            flat = outdir / f"{repo}__{rel.replace('/', '__')}"
            if not flat.exists():
                try:
                    shutil.copyfile(p, flat)
                    n_files += 1
                except OSError as e:
                    print(f"  copy failed {rel}: {e}", flush=True)
        shutil.rmtree(dst / ".git", ignore_errors=True)  # keep only the flattened rasters
        print(f"  {repo}: {len(tifs)} tifs (total flattened {n_files})", flush=True)
    print(f"done: {n_files} rasters in {outdir} from {len(repos)} repos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
