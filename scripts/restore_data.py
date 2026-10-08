#!/usr/bin/env python3
"""Restore the competition rasters from the owner's hash-pinned sibling mirrors.

Why this exists
---------------
The DrivenData data tab (https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
is login-walled and this sandbox has no credentials, so the official rasters cannot be pulled from
the portal directly.  Earlier sessions in this project family mirrored the *bytes they had
downloaded from the portal* into sibling GitHub repositories, pinned by SHA-256.  This script
restores from those mirrors and **verifies every file against the pinned SHA-256 and byte count
before it is accepted**.  A mismatch is a hard error, never a warning.

Provenance discipline (the point of the script)
------------------------------------------------
* Verified: bytes match a SHA-256 pinned in ``registry/data_manifest.json``; the pins were
  imported verbatim from sibling repository GEMSDOE47 and are re-checked here after download.
* NOT verified: that the pinned bytes are what the *organiser* published.  That would require an
  authenticated portal download.  Every downstream report therefore labels these rasters
  "integrity-pinned, not organizer-authenticated".

Transport
---------
Only ``api.github.com`` / ``github.com`` are reachable from this sandbox
(``raw.githubusercontent.com`` and the USGS / GDR / DrivenData hosts time out), so blobs are read
through the Git Data API ``/git/blobs/{sha}`` with the ``raw`` media type, which streams blobs up
to 100 MB -- above the largest 94.37 MB part here.  ``--only`` lets a caller stage the small core
files first and the 419 MB feature raster afterwards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
UA = "gems52-restore/1.0"


def _headers(accept: str) -> dict[str, str]:
    h = {"Accept": accept, "User-Agent": UA}
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not tok:  # the sandbox exposes a repo-scoped token through the gh CLI
        try:
            tok = subprocess.run(["gh", "auth", "token"], capture_output=True,
                                 text=True, timeout=20).stdout.strip()
        except Exception:
            tok = ""
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def api_json(url: str, tries: int = 5) -> dict:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=_headers("application/vnd.github+json")),
                    timeout=180) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            code = getattr(exc, "code", None)
            if code in (403, 429) or code in (500, 502, 503, 504) or code is None:
                time.sleep(min(60, 3 * 2 ** attempt))
                continue
            raise
    raise RuntimeError(f"GET failed after {tries} tries: {url}")


def _token() -> str:
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not tok:  # the sandbox exposes a repo-scoped token through the gh CLI
        try:
            tok = subprocess.run(["gh", "auth", "token"], capture_output=True,
                                 text=True, timeout=20).stdout.strip()
        except Exception:
            tok = ""
    return tok


def stream_blob(repo: str, sha: str, dest: Path, expect_bytes: int, tries: int = 4) -> None:
    """Fetch one blob to ``dest`` with curl (streaming, no Python-side memory use).

    urllib was tried first and truncated large ``application/vnd.github.raw`` responses
    (chunked transfer + a 94 MB body), so the transport is curl with explicit retries; the
    byte count and SHA-256 are still checked by the caller, so a truncated file can never pass.
    """
    url = f"{API}/repos/{repo}/git/blobs/{sha}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".download")
    tok = _token()
    for attempt in range(tries):
        cmd = ["curl", "-sS", "-L", "--fail", "--retry", "3", "--retry-delay", "3", "-m", "1800",
                "-H", "Accept: application/vnd.github.raw", "-H", "User-Agent: " + UA]
        if tok:
            cmd += ["-H", f"Authorization: Bearer {tok}"]
        cmd += ["-o", str(tmp), url]
        rc = subprocess.run(cmd, capture_output=True, text=True, timeout=1900)
        if tmp.exists():
            n = tmp.stat().st_size
            if expect_bytes and n != expect_bytes:
                print(f"    short read ({n} != {expect_bytes}); retry {attempt + 1}", flush=True)
                tmp.unlink(missing_ok=True)
                time.sleep(3 * (attempt + 1))
                continue
            tmp.replace(dest)
            return
        print(f"    curl rc={rc.returncode} {rc.stderr.strip()[:160]}; retry {attempt + 1}", flush=True)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"could not download blob {sha} of {repo} after {tries} tries")


def sha256_of(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


class TreeCache:
    def __init__(self) -> None:
        self.trees: dict[tuple[str, str], dict[str, str]] = {}

    def sha_for(self, repo: str, ref: str, path: str) -> str:
        key = (repo, ref)
        if key not in self.trees:
            cache = Path(f"/tmp/tree_{repo.replace('/', '_')}_{ref[:8]}.json")
            d = json.loads(cache.read_text()) if cache.exists() else None
            if d is None:
                d = api_json(f"{API}/repos/{repo}/git/trees/{ref}?recursive=1")
                if d.get("truncated"):
                    raise RuntimeError(f"tree {repo}@{ref[:8]} truncated; cannot resolve paths")
                cache.write_text(json.dumps(d))
            self.trees[key] = {e["path"]: e["sha"] for e in d["tree"] if e["type"] == "blob"}
        tr = self.trees[key]
        if path not in tr:
            raise KeyError(f"{path} not present in {repo}@{ref[:8]}")
        return tr[path]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="registry/data_manifest.json")
    ap.add_argument("--target-dir", default="data")
    ap.add_argument("--only", default="", help="comma list of ids")
    ap.add_argument("--skip-large", action="store_true", help="skip entries > 60 MB")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    root = Path.cwd()
    manifest = json.loads((root / args.manifest).read_text())
    tdir = Path(args.target_dir)
    tdir.mkdir(parents=True, exist_ok=True)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    tc = TreeCache()

    receipt_path = tdir / "restore_receipt.json"
    receipt = json.loads(receipt_path.read_text())["files"] if receipt_path.exists() else []
    by_id = {r["id"]: r for r in receipt}
    ok_all = True

    for f in manifest["files"]:
        fid = f["id"]
        if only and fid not in only:
            continue
        if args.skip_large and f["bytes"] > 60_000_000:
            print(f"[skip-large] {fid}")
            continue
        dest, parts = tdir / f["dest"], f.get("parts")
        if dest.exists() and not args.force:
            dig, n = sha256_of(dest)
            if dig == f["sha256"] and n == f["bytes"]:
                print(f"[present] {fid} ({n} bytes, sha OK)")
                by_id[fid] = {"id": fid, "dest": str(dest), "bytes": n, "sha256": dig,
                              "matches_pin": True, "source_repo": f["repo"], "source_ref": f["ref"],
                              "source_path": f.get("path") or parts,
                              "provenance": f.get("provenance", "")}
                continue
            print(f"[stale] {fid}: sha mismatch -> re-fetching")

        if parts:
            pdir = tdir / "raw_parts" / fid
            pdir.mkdir(parents=True, exist_ok=True)
            local = []
            for p in parts:
                lp = pdir / Path(p).name
                blob_sha = tc.sha_for(f["repo"], f["ref"], p)
                if lp.exists():
                    d, n = sha256_of(lp)
                    if n > 0:
                        print(f"[part present] {Path(p).name} ({n} bytes)")
                        local.append(lp)
                        continue
                print(f"[part fetch] {Path(p).name} <- {f['repo']}:{p}", flush=True)
                stream_blob(f["repo"], blob_sha, lp, 0)
                local.append(lp)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as out:
                for lp in local:
                    with lp.open("rb") as inp:
                        for chunk in iter(lambda: inp.read(1 << 22), b""):
                            out.write(chunk)
        else:
            blob_sha = tc.sha_for(f["repo"], f["ref"], f["path"])
            print(f"[fetch] {fid} <- {f['repo']}:{f['path']}", flush=True)
            stream_blob(f["repo"], blob_sha, dest, f["bytes"])

        dig, n = sha256_of(dest)
        good = dig == f["sha256"] and n == f["bytes"]
        ok_all &= good
        print(f"[{'OK ' if good else 'BAD'}] {fid}: {n} bytes sha={dig[:16]}… "
              f"(pin {f['sha256'][:16]}…, {f['bytes']} bytes)")
        by_id[fid] = {"id": fid, "dest": str(dest), "bytes": n, "sha256": dig, "matches_pin": good,
                      "source_repo": f["repo"], "source_ref": f["ref"],
                      "source_path": f.get("path") or parts, "provenance": f.get("provenance", "")}
        receipt_path.write_text(json.dumps(
            {"verified_against": args.manifest, "all_ok": bool(ok_all),
             "files": [by_id[k] for k in by_id]}, indent=1))

    receipt_path.write_text(json.dumps(
        {"verified_against": args.manifest, "all_ok": bool(ok_all),
         "files": [by_id[k] for k in by_id]}, indent=1))
    print("ALL_VERIFIED=" + str(bool(ok_all)))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
