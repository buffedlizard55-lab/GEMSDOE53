"""The CI that publishes the site must itself be checked, not assumed.

`feed.yml` shipped in a state where it failed in 0 seconds with no log — an inline Python block inside a
`run: |` scalar had lost its indentation, which ends the block scalar and makes the whole file invalid
YAML. Nothing in the repo noticed, because nothing parsed it. That is the failure mode this test exists
for: a scheduled publisher that dies silently means the site goes stale and *looks* fine.

PyYAML is a dev-only import here; if it is absent the test skips rather than failing, so the analysis
environment (which has no network) still runs the suite.
"""
from __future__ import annotations

import pathlib
import re

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml not installed in this environment")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def workflow_files():
    return sorted(WF.glob("*.yml")) + sorted(WF.glob("*.yaml"))


def test_workflows_exist_and_parse():
    files = workflow_files()
    assert files, "no workflow files: the scheduled feed refresh the site depends on does not exist"
    # yaml.safe_load is the authority here. An earlier version of this test also tried to re-derive the
    # block-scalar indentation rule by regex; it misfired on valid YAML, which is exactly how a lint
    # becomes noise, so it is gone and the parser does the job.
    for f in files:
        doc = yaml.safe_load(f.read_text())
        assert isinstance(doc, dict), f"{f.name}: parsed to {type(doc).__name__}, not a mapping"
        assert doc, f"{f.name}: empty"
        assert "jobs" in doc, f"{f.name}: no jobs key (parsed keys: {list(doc)})"


def test_feed_workflow_declares_the_steps_the_site_relies_on():
    doc = yaml.safe_load((WF / "feed.yml").read_text())
    steps = [s.get("name", s.get("uses", "")) for s in doc["jobs"]["refresh"]["steps"]]
    assert any("checkout" in s for s in steps), steps
    assert any("Refresh the feed" in s for s in steps), steps
    assert any("Commit the refreshed feed" in s for s in steps), steps
    assert any("Fail loudly" in s for s in steps), \
        "a scheduled fetch that fails must fail visibly, or the site silently freezes"
    # publishing a raster is a human act: the workflow must not touch downloads/ or submission/
    add_cmds = [s for s in doc["jobs"]["refresh"]["steps"] if "Commit" in s.get("name", "")]
    assert add_cmds and "docs/data/" in add_cmds[0]["run"]
    assert "docs/downloads" not in add_cmds[0]["run"].replace("docs/data/", "")
    trig = doc.get("on") or doc.get(True)
    assert "schedule" in trig and "workflow_dispatch" in trig


def test_feed_workflow_is_dependency_free():
    """The fetcher is stdlib-only so a package index outage cannot freeze the leaderboard feed."""
    text = (WF / "feed.yml").read_text()
    assert "pip install" not in text, "installing packages makes the schedule fail on PyPI, not on the site"
    src = (ROOT / "scripts" / "refresh_feed.py").read_text()
    mods = set(re.findall(r"^(?:import|from) (\w+)", src, re.M))
    allowed = {"argparse", "json", "re", "sys", "time", "urllib", "pathlib", "hashlib", "__future__",
               "csv", "html"}
    assert mods <= allowed, f"refresh_feed.py imports non-stdlib/odd modules: {sorted(mods - allowed)}"
