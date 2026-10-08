#!/usr/bin/env python3
"""Fetch every public GEMS submission raster in the buffedlizard55-lab GEMS repos (the uniqueness registry).

Why: the parallel-run protocol requires the duplicate check to run against EVERY registry raster, not a
subset. This script enumerates the public repositories whose names contain "GEMS" (via the GitHub API),
lists every *.tif / *.tiff / *.zip blob in each default branch, downloads them through api.github.com
(an allowed host), unzips zip archives that contain GeoTIFFs, and writes a manifest with blob SHAs,
byte counts and SHA-256 hashes.

Nothing is written into the repository except the manifest (evidence/registry_manifest.json).
Rasters go to --dest (default /tmp/gems53-registry), outside the repo.

Usage:
    python scripts/fetch_registry.py --dest /tmp/gems53-registry --manifest evidence/registry_manifest.json
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

OWNER = "buffedlizard55-lab"
MAX_BYTES = 60_000_000  # skip very large blobs (the template's data bridge is 94 MB parts; not submissions)


def gh_json(args: list[str]):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True, timeout=300)
    return json.loads(out.stdout)


def list_gems_repos() -> list[dict]:
    rows = gh_json(["repo", "list", OWNER, "--limit", "300", "--json", "name,isPrivate,defaultBranchRef,diskUsage"])
    keep = []
    for r in rows:
        name = r["name"]
        if r.get("isPrivate"):
            continue
        if re.search(r"gems", name, re.I):
            branch = (r.get("defaultBranchRef") or {}).get("name") or "main"
            keep.append({"name": name, "branch": branch, "diskUsage_kb": r.get("diskUsage")})
    return sorted(keep, key=lambda r: r["name"].lower())


def list_rasters(repo: str, branch: str) -> list[dict]:
    tree = gh_json(["api", f"repos/{OWNER}/{repo}/git/trees/{branch}?recursive=1"])
    out = []
    for e in tree.get("tree", []):
        if e.get("type") != "blob":
            continue
        p = e["path"]
        if not re.search(r"\.(tif|tiff|zip)$", p, re.I):
            continue
        size = int(e.get("size") or 0)
        out.append({"path": p, "sha": e["sha"], "size": size, "skipped_large": size > MAX_BYTES})
    return out


def download_blob(repo: str, sha: str) -> bytes:
    j = gh_json(["api", f"repos/{OWNER}/{repo}/git/blobs/{sha}"])
    if j.get("encoding") != "base64":
        raise RuntimeError(f"unexpected encoding for {repo}:{sha}")
    return base64.b64decode(j["content"])


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_one(job: dict, dest: Path) -> list[dict]:
    repo, path, sha = job["repo"], job["path"], job["sha"]
    raw = download_blob(repo, sha)
    stem = f"{repo}__{path.replace('/', '__')}"
    rows = []
    if path.lower().endswith(".zip"):
        zpath = dest / (stem + ".zip")
        zpath.write_bytes(raw)
        with zipfile.ZipFile(zpath) as z:
            for member in z.namelist():
                if member.lower().endswith((".tif", ".tiff")):
                    data = z.read(member)
                    local = dest / f"{stem}__{member.replace('/', '__')}"
                    local.write_bytes(data)
                    rows.append({"repo": repo, "path": f"{path}!/{member}", "blob_sha": sha,
                                 "bytes": len(data), "sha256": sha256_bytes(data), "local": str(local)})
        return rows
    local = dest / stem
    local.write_bytes(raw)
    return [{"repo": repo, "path": path, "blob_sha": sha, "bytes": len(raw),
             "sha256": sha256_bytes(raw), "local": str(local)}]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="/tmp/gems53-registry")
    ap.add_argument("--manifest", default=str(Path(__file__).resolve().parents[1] / "evidence" / "registry_manifest.json"))
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    repos = list_gems_repos()
    jobs, skipped, listing = [], [], []
    for r in repos:
        try:
            rasters = list_rasters(r["name"], r["branch"])
        except subprocess.CalledProcessError as exc:  # empty repos have no tree
            listing.append({"repo": r["name"], "branch": r["branch"], "n_rasters": 0,
                            "note": "tree unavailable: " + (exc.stderr or "").strip()[:200]})
            continue
        listing.append({"repo": r["name"], "branch": r["branch"], "n_rasters": len(rasters)})
        for x in rasters:
            if x["skipped_large"]:
                skipped.append({"repo": r["name"], "path": x["path"], "size": x["size"]})
                continue
            jobs.append({"repo": r["name"], "path": x["path"], "sha": x["sha"]})

    files: list[dict] = []
    errors: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_one, j, dest): j for j in jobs}
        for fut in cf.as_completed(futs):
            j = futs[fut]
            try:
                files.extend(fut.result())
            except Exception as exc:  # record, never silently drop
                errors.append({"repo": j["repo"], "path": j["path"], "error": str(exc)[:300]})

    files.sort(key=lambda r: (r["repo"].lower(), r["path"]))
    manifest = {
        "schema": "gems53.registry_manifest.v1",
        "owner": OWNER,
        "scope": "public repositories whose name contains 'gems' (case-insensitive); default branch; *.tif/*.tiff/*.zip blobs",
        "repos_checked": len(repos),
        "rasters_downloaded": len(files),
        "skipped_large": skipped,
        "errors": errors,
        "repos": listing,
        "files": files,
    }
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    Path(args.manifest).write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: manifest[k] for k in ("repos_checked", "rasters_downloaded")}, indent=2))
    print(f"skipped_large={len(skipped)} errors={len(errors)} manifest={args.manifest}")
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
