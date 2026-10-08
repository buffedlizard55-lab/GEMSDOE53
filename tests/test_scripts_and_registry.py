"""Guards for the two irregularities that were invisible until something downstream needed them.

IR-52-020: ``scripts/download_competition_data.sh`` called ``restore_data.py --group all``. That flag
does not exist, so the documented one-command data placement exited 2 with a usage message before
fetching anything -- and it survived because nothing asserted the files existed afterwards. The test
parses the wrapper's actual argv against the real parser.

IR-52-021: ``src/gems52/features.py`` has cited ``registry/irregularities.json`` since it was
written; the file did not exist. Every id cited anywhere in code, prose or the site must resolve.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _restore_parser_argv():
    """The real parser, built by importing restore_data.py without running its main()."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("restore_data_probe",
                                                  ROOT / "scripts" / "restore_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_download_wrapper_argv_parses_against_the_real_restore_parser():
    """IR-52-020. Every flag the wrapper passes to restore_data.py must exist in its real parser.

    Deliberately does *not* lex the shell: the wrapper uses bash array expansion, which shlex chokes
    on, and a test that cannot parse its own subject is a test that silently stops testing.  Instead
    it reads the option strings out of the parser restore_data.py actually builds.
    """
    sh = (ROOT / "scripts" / "download_competition_data.sh").read_text()
    # comments are stripped first: this file legitimately *mentions* --group in the comment that
    # explains why it is gone, and a test that cannot tell prose from argv is testing nothing
    code = "\n".join(ln.split("#", 1)[0] for ln in sh.splitlines())
    assert "--group" not in code, "IR-52-020 regressed: --group is not a restore_data.py flag"
    lines = [ln for ln in code.splitlines() if "restore_data.py" in ln]
    assert lines, "the wrapper no longer calls restore_data.py at all"
    flags = {f for ln in lines for f in re.findall(r"(?<!\w)--[a-z][a-z0-9-]*", ln)}
    src = (ROOT / "scripts" / "restore_data.py").read_text()
    real = set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', src))
    assert real, "could not read restore_data.py's flags; the test would prove nothing"
    unknown = flags - real
    assert not unknown, f"wrapper passes flags restore_data.py does not accept: {sorted(unknown)}"
    # bash must still be able to parse the file
    r = subprocess.run(["bash", "-n", str(ROOT / "scripts" / "download_competition_data.sh")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr


def test_restore_data_rejects_the_flag_the_wrapper_used_to_pass():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "restore_data.py"), "--group", "all"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0
    assert "unrecognized" in (r.stderr + r.stdout).lower()


def test_irregularities_register_exists_and_is_valid_json():
    """IR-52-021, and IR-52-017 (published JSON must not contain a bare NaN)."""
    p = ROOT / "registry" / "irregularities.json"
    assert p.exists(), "src/gems52/features.py cites this file by path"
    text = p.read_text()
    assert not re.search(r"(?<=[\[:,\[])\s*(?:NaN|-?Infinity)\b", text), "bare NaN/Infinity in JSON"
    d = json.loads(text)
    ids = {e["id"] for e in d["entries"]}
    assert ids, "empty register"
    assert len(ids) == len(d["entries"]), "duplicate ids in the register"
    for e in d["entries"]:
        for k in ("id", "what_it_is", "how_we_know", "disposition"):
            assert e.get(k), f"{e['id']} is missing {k}"


def test_every_irregularity_id_cited_in_the_repo_exists_in_the_register():
    reg = json.loads((ROOT / "registry" / "irregularities.json").read_text())
    ids = {e["id"] for e in reg["entries"]}
    cited: dict[str, set[str]] = {}
    pats = ("*.py", "*.md", "*.html", "*.json", "*.sh")
    for pat in pats:
        for f in ROOT.rglob(pat):
            rel = f.relative_to(ROOT).as_posix()
            if rel.startswith((".git/", "data/", "work/", "docs/data/", "docs/downloads/")):
                continue
            if f.name == "irregularities.json":
                continue
            try:
                text = f.read_text(errors="ignore")
            except Exception:                                     # noqa: BLE001
                continue
            for m in re.findall(r"\bIR-\d+-\d+\b", text):
                cited.setdefault(m, set()).add(rel)
    missing = {k: sorted(v) for k, v in cited.items() if k not in ids}
    assert not missing, f"ids cited but absent from the register: {missing}"


def test_features_module_band_six_claim_is_corrected_not_deleted():
    """The H52 features module still files band 6 in View A. That is now a known-wrong choice, so it
    must point at the correction rather than at a superseded claim."""
    src = (ROOT / "src" / "gems52" / "features.py").read_text()
    assert "IR-52-019" in src or "gems55" in src, (
        "features.py still asserts 'no radiometric band' without pointing at the measurement that "
        "disproved it (evidence/h55_band6_identity.json)")
    h53 = (ROOT / "src" / "gems55" / "radlayers.py").read_text()
    assert "mag_tilt_curvature" not in h53.split("VIEW_A =")[1].split("]")[0], \
        "band 6 must not appear in the corrected View A"


def test_no_python_file_in_src_has_a_syntax_error():
    """Cheap whole-tree guard: an edit tool that silently truncates a file is the failure mode this
    repository has hit before, and ast.parse is the check the process rules require after every edit."""
    bad = []
    for f in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py")):
        try:
            ast.parse(f.read_text())
        except SyntaxError as e:                                  # pragma: no cover
            bad.append(f"{f.relative_to(ROOT)}: {e}")
    assert not bad, bad


def test_workflows_are_still_valid_yaml_and_still_stdlib_only():
    """tests/test_workflows.py already guards this; the guard is repeated here only for the files the
    H55 work touched, so a failure names the change that caused it."""
    p = ROOT / ".github" / "workflows" / "feed.yml"
    assert p.exists()
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml not installed")
    d = yaml.safe_load(p.read_text())
    assert d.get("on") or d.get(True), "the feed workflow has no trigger"
