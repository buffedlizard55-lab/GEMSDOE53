#!/usr/bin/env python3
"""Snapshot the supplied sites and official sources; inventory accessible prediction TIFFs.

No login, upload or score inference. HTML and downloaded learning-only priors stay in
ignored data/review/. Every published statement is an excerpt or a separately labelled
interpretation, with a URL, HTTP status, retrieval time and content hash. Network
failures remain failures. Re-run to refresh, not to create an unverified 'live' claim.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/review"
SITE_PATHS = [
    ("GEMSDOE", "docs/index.html"), ("6GEMSDOE", ""), ("GEMSDOE3", "docs/index.html"),
    ("GEMSDOE2", "docs/index.html"), ("GEMSDOE4", ""), ("5GEMSDOE", "docs/index.html"),
    ("7GEMSDOE", ""), ("8GEMSDOE", ""), ("GEMSDOE9", "docs/index.html"),
    ("11GEMSDOE", "docs/index.html"), ("12GEMSDOE", "docs/index.html"),
    ("15GEMSDOE", "docs/index.html"), ("14GEMSDOE", "docs/index.html"), ("17GEMSDOE", ""),
    ("18GEMSDOE", ""), ("19GEMSDOE", "docs/index.html"), ("GEMSDOE10", ""),
    ("13GEMSDOE", ""), ("16GEMSDOE", "docs/index.html"), ("GEMSDOE21", ""),
    ("20GEMSDOE", "docs/index.html"), ("GEMSDOE22", "docs/index.html"), ("GEMSDOE23", ""),
    ("GEMSDOE24", ""), ("GEMSDOE25", ""), ("GEMSDOE26", ""), ("GEMSDOE27", ""),
    ("GEMSDOE28", ""), ("GEMSDOE29", "docs/index.html"), ("GEMSDOE30", ""),
    ("GEMSDOE31", "docs/"), ("GEMSDOE32", "docs/index.html"), ("GEMSDOE33", ""),
    ("GEMSDOE34", "docs/index.html"), ("GEMSDOE35", "docs/index.html"), ("GEMSDOE36", "docs/"),
    ("GEMSDOE37", ""), ("GEMSDOE38", "docs/index.html"), ("GEMSDOE39", ""),
    ("GEMSDOE40", "docs/index.html"), ("GEMSDOE41", "docs/index.html"),
    ("GEMSDOE42", "docs/index.html"), ("GEMSDOE43", "docs/index.html"), ("GEMSDOE44", "docs/"),
    ("GEMSDOE45", ""), ("GEMSDOE46", ""), ("GEMSDOE47", ""),
    ("GEMSDOE48", "docs/index.html"), ("GEMSDOE49", ""), ("GEMSDOE50", ""),
    ("GEMSDOE51", ""), ("GEMSDOE52", ""),
]
OFFICIAL = {
    "problem": "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
    "about": "https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/",
    "leaderboard": "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/",
    "data_access": "https://www.drivendata.org/competitions/306/competition-doe-gems/data/",
    "rules": "https://www.drivendata.org/competitions/306/competition-doe-gems/rules/",
    "rules_pdf": "https://docs.nlr.gov/docs/fy26osti/96647.pdf",
    "mask_clarification": "https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4",
    "test_source_discussion": "https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7",
    "geodawn": "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and",
    "blind_systems": "https://www.usgs.gov/publications/discovering-blind-geothermal-systems-great-basin-region-integrated-geologic-and",
    "ingenious": "https://gdr.openei.org/submissions/1391",
    "cotrain_primary": "https://www.cs.cmu.edu/~avrim/Papers/cotrain.pdf",
    "hermant_2025": "https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf",
    "reference_solution": "https://github.com/drivendataorg/gems-prize-reference-solution",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.parts, self.ignored = [], [], 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.ignored += 1
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in ("p", "tr", "h1", "h2", "h3", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.ignored = max(0, self.ignored - 1)

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


# GitHub Pages and official hosts can be denied by the sandbox's network policy.
# GitHub source blobs are an auditable fallback for OWNER pages only. They are
# explicitly not represented as verified deployed Pages responses.
from restore_data import TreeCache, stream_blob, api_json
TREES = TreeCache()


def get(url, limit=55_000_000):
    host = urllib.parse.urlparse(url).hostname or ''
    if host.endswith('drivendata.org'):
        policy = json.loads((ROOT / 'registry/source_policy.json').read_text())['drivendata']
        if not (policy.get('automated_fetch_allowed') and policy.get('written_permission_reference')):
            raise PermissionError('Automatic DrivenData access disabled by source policy; see dated verified_claims_r2.json')
    req = urllib.request.Request(url, headers={"User-Agent": "GEMSDOE52-source-audit/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            body = response.read(limit + 1)
            if len(body) > limit:
                raise ValueError(f"body exceeds {limit} byte audit limit")
            return response.geturl(), response.status, dict(response.headers), body
    except (urllib.error.URLError, OSError) as direct_error:
        parsed = urllib.parse.urlparse(url)
        ref = 'main'
        if parsed.hostname == "buffedlizard55-lab.github.io":
            pieces = parsed.path.strip("/").split("/", 1)
            repo = "buffedlizard55-lab/" + pieces[0]
            path = pieces[1] if len(pieces) > 1 else "index.html"
            if not path or path.endswith("/"):
                path += "index.html"
            elif '.' not in Path(path).name:
                path += '/index.html'
            try:
                sha = TREES.sha_for(repo, ref, urllib.parse.unquote(path))
            except KeyError:
                # Pages can publish /docs as its root. Resolve that mapping from
                # GitHub configuration, never invent a 'working' deployed URL.
                source = api_json(f'https://api.github.com/repos/{repo}/pages').get('source', {})
                prefix = source.get('path', '/').strip('/')
                mapped = '/'.join(x for x in (prefix, path) if x)
                if '.' not in Path(mapped).name:
                    mapped += '/index.html'
                sha = TREES.sha_for(repo, source.get('branch', ref), urllib.parse.unquote(mapped))
        elif parsed.hostname == 'github.com':
            parts = parsed.path.strip('/').split('/')
            if len(parts) < 5 or parts[0] != 'buffedlizard55-lab' or parts[2] != 'raw':
                raise
            repo, ref, path = '/'.join(parts[:2]), parts[3], '/'.join(parts[4:])
            sha = TREES.sha_for(repo, ref, urllib.parse.unquote(path))
        else:
            raise
        dest = CACHE / "blobs" / sha
        if not dest.exists():
            stream_blob(repo, sha, dest, 0)
        body = dest.read_bytes()
        if len(body) > limit:
            raise ValueError(f"mirror blob exceeds {limit} byte audit limit")
        return url, 200, {"Content-Type": "application/pdf" if path.endswith(".pdf") else "text/html",
                         "X-Audit-Transport": "GitHub immutable source blob " + sha,
                         "X-Direct-Failure": str(direct_error)[:200]}, body


def inspect_page(pair):
    key, url = pair
    row = dict(id=key, url=url, retrieved_utc=now(), source_class="owner site" if key.startswith("site:") else "primary source")
    try:
        final, status, headers, body = get(url)
        row.update(final_url=final, http_status=status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                   transport=headers.get("X-Audit-Transport", "direct HTTP"), direct_failure=headers.get("X-Direct-Failure"))
        if headers.get("X-Audit-Transport"):
            row["deployed_http_verified"] = False
        ext = ".pdf" if "pdf" in headers.get("Content-Type", "") else ".html"
        dest = CACHE / "pages" / (key.replace(":", "_") + ext)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        row["snapshot"] = str(dest.relative_to(ROOT))
        if ext == ".html":
            parser = Extract()
            parser.feed(body.decode("utf-8", "replace"))
            text = re.sub(r"[\t ]+", " ", "".join(parser.parts))
            lines = [x.strip() for x in text.splitlines() if x.strip()]
            row["title"] = html.unescape(re.search(r"<title[^>]*>(.*?)</title>", body.decode("utf-8", "replace"), re.S | re.I).group(1)).strip() if b"<title" in body else key
            row["opening_excerpt"] = "\n".join(lines[:22])[:3200]
            row["score_excerpts"] = [x[:450] for x in lines if re.search(r"0\.\d{4}\b", x)][:16]
            row["tif_urls"] = sorted({urllib.parse.urljoin(final, h) for h in parser.links if urllib.parse.urlparse(h).path.lower().endswith(".tif")})
            row["related_download_indexes"] = sorted({urllib.parse.urljoin(final, h) for h in parser.links if "download" in h.lower() and urllib.parse.urlparse(h).path.endswith(("index.html", "/"))})
            row["access"] = "login redirect" if "/login" in final else "public"
        else:
            row["tif_urls"] = []
            row["access"] = "public"
    except Exception as exc:
        row.update(http_status=getattr(exc, "code", None), access="failed", error=f"{type(exc).__name__}: {exc}")
        row["tif_urls"] = []
    return row


def inspect_tif(url):
    import numpy as np
    import rasterio
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    dest = CACHE / "priors" / (key + ".tif")
    row = dict(url=url, retrieved_utc=now(), local_path=str(dest.relative_to(ROOT)), purpose="learning and uniqueness comparison only; never a generated prediction input")
    try:
        if dest.exists():
            body = dest.read_bytes()
            row["transport"] = "cached"
        else:
            final, status, _, body = get(url)
            row.update(final_url=final, http_status=status, transport="downloaded")
            if not body[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
                raise ValueError("not a TIFF byte signature")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
        row.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        with rasterio.open(dest) as src:
            row.update(shape=[src.height, src.width], crs=str(src.crs), transform=list(src.transform)[:6], bands=src.count)
            if (src.count != 1 or (src.height, src.width) != (3730, 3292)
                    or src.crs is None or src.crs.to_epsg() != 32611
                    or tuple(src.transform)[:6] != (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)):
                row["eligible_prior"] = False
                row["reason"] = "not a single-band competition-shape prediction"
                return row
            a = src.read(1)
            a = np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype("<f4")
            row.update(decoded_sha256=hashlib.sha256(a.tobytes()).hexdigest(), eligible_prior=True,
                       positive_px=int((a > 0).sum()), half_threshold_px=int((a >= 0.5).sum()),
                       binary=bool(np.isin(a, [0, 1]).all()))
    except Exception as exc:
        row.update(eligible_prior=False, error=f"{type(exc).__name__}: {str(exc)[:300]}")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download-priors", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    pairs = [(f"site:{repo}", f"https://buffedlizard55-lab.github.io/{repo}/{path}") for repo, path in SITE_PATHS]
    pairs += list(OFFICIAL.items())
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(inspect_page, pairs))
    # Only follow indexes actually linked from supplied pages, never guess a missing site's URL.
    extras = sorted({u for row in rows if row["id"].startswith("site:") for u in row.get("related_download_indexes", [])})
    if extras:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            extra_rows = list(pool.map(inspect_page, [("index:" + hashlib.sha256(u.encode()).hexdigest()[:16], u) for u in extras]))
        rows.extend(extra_rows)
    tifs = {u for row in rows for u in row.get("tif_urls", [])}
    # Enumerate every download/submission TIFF actually present in successfully
    # resolved owner repository trees. Collapse identical immutable Git blobs,
    # while keeping all aliases; this is wider than just comparing primary links.
    blobs = {}
    for (repo, ref), tree in list(TREES.trees.items()):
        for path, sha in tree.items():
            if path.lower().endswith(('.tif', '.tiff')) and (
                path.startswith(('docs/', 'submission/', 'artifacts/', 'outputs/', 'predictions/', 'downloads/', 'results/', 'releases/', 'deliverables/'))
                or ('/' not in path and re.search(r'gems|submission|prediction|candidate|ensemble', path, re.I))
            ):
                u = "https://buffedlizard55-lab.github.io/" + repo.split("/")[1] + "/" + urllib.parse.quote(path)
                blobs.setdefault(sha, []).append(u)
    for urls in blobs.values():
        tifs.add(sorted(urls)[0])
    aliases = {u for urls in blobs.values() for u in sorted(urls)[1:]}
    tifs = sorted(tifs - aliases)
    out = dict(generated_utc=now(), entries=rows, supplied_sites=len(SITE_PATHS),
               tree_prediction_aliases=blobs, tree_repositories_checked=len(TREES.trees),
               public_pages=sum(r.get("access") == "public" for r in rows),
               urls_without_supplied_link=["53GEMSDOE", "54GEMSDOE"],
               evidence_limit="Owner-site scores are claims, not authenticated file-to-score mappings. Unlinked, inaccessible, external-storage and private rasters are outside this inventory.",
               linked_tif_urls=tifs)
    (ROOT / "evidence/source_review_r2.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"{len(rows)} pages, {out['public_pages']} public, {len(tifs)} distinct linked TIFF URLs", flush=True)
    if args.download_priors:
        with ThreadPoolExecutor(max_workers=min(args.workers, 4)) as pool:
            priors = list(pool.map(inspect_tif, tifs))
        (ROOT / "evidence/prior_inventory_r2.json").write_text(json.dumps(dict(generated_utc=now(), scope=out["evidence_limit"], entries=priors), indent=2) + "\n")
        print(f"{len(priors)} linked TIFFs checked; {sum(r.get('eligible_prior', False) for r in priors)} aligned single-band priors", flush=True)
    for row in rows:
        print(row["id"], row.get("http_status"), row["access"], row.get("error", "")[:100], flush=True)


if __name__ == "__main__":
    main()
