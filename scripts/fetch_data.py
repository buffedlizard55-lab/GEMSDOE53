#!/usr/bin/env python3
"""Fetch and verify the official GEMS competition rasters into DATA_DIR (outside the repo by default).

Source chain (all public, all hash-pinned):
  1. The template repo buffedlizard55-lab/GEMSDOE carries the competition rasters as git blobs under
     data/bridge/ (its own README says they were transported from an unrestricted runner; the mirrors
     are the Dropbox links listed in data/bridge/manifest.json, which the user supplied).
  2. This script shallow-clones that repo into a temp dir, copies the 5 split parts, concatenates them,
     and checks every part sha256 and the whole-file sha256 against data/bridge/manifest.json.

Nothing is written into this repository. Use --data-dir to change the destination.

Usage:
    python scripts/fetch_data.py                 # -> /tmp/gems53-data
    python scripts/fetch_data.py --data-dir DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATE_REPO = "https://github.com/buffedlizard55-lab/GEMSDOE.git"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    args = ap.parse_args()
    out = Path(args.data_dir)
    out.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="gems-bridge-"))
    try:
        subprocess.run(["git", "clone", "--depth", "1", TEMPLATE_REPO, str(tmp / "repo")], check=True)
        bridge = tmp / "repo" / "data" / "bridge"
        manifest = json.loads((bridge / "manifest.json").read_text())
        files = {f["name"]: f for f in manifest["files"]}

        feat = files["gems-geodawn-numerical-features.tif"]
        dst_feat = out / feat["canonical"]
        parts_ok = True
        for part in feat["parts"]:
            p = bridge / part["name"]
            if not p.exists() or p.stat().st_size != part["bytes"] or sha256_file(p) != part["sha256"]:
                parts_ok = False
                print(f"FAIL part {part['name']}")
        if not parts_ok:
            return 1

        tmp_feat = out / (feat["canonical"] + ".partial")
        with tmp_feat.open("wb") as w:
            for part in feat["parts"]:
                with (bridge / part["name"]).open("rb") as r:
                    shutil.copyfileobj(r, w, length=1 << 20)
        got = sha256_file(tmp_feat)
        if got != feat["sha256"] or tmp_feat.stat().st_size != feat["bytes"]:
            tmp_feat.unlink(missing_ok=True)
            print(f"FAIL features sha256 {got} != {feat['sha256']}")
            return 1
        tmp_feat.replace(dst_feat)
        print(f"OK {dst_feat} ({feat['bytes']} B, sha256 {got})")

        for name in ("existing_faults.tif", "example_submission.tif"):
            f = files[name]
            src = bridge / name
            if sha256_file(src) != f["sha256"]:
                print(f"FAIL {name} sha256")
                return 1
            shutil.copyfile(src, out / f["canonical"])
            print(f"OK {out / f['canonical']} ({f['bytes']} B, sha256 {f['sha256']})")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
