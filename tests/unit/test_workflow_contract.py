"""Tests for the weekly refresh GitHub Actions workflow contract.

The workflow at .github/workflows/refresh.yml is the only thing that
keeps the public site current. It's also the place where it's easiest
to silently regress (a missing step doesn't break CI — it just leaves
the data stale). These tests pin the contract:

* Playwright is installed (analyze_phab.py imports it at module load).
* analyze_phab.py is invoked, so wait-time data refreshes weekly.
* .phab_html_cache/ persists between runs via actions/cache.
* The commit step picks up data_phab.json and raw_data/ as well as
  the GitHub-derived outputs.
"""

from pathlib import Path

import pytest


_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "refresh.yml"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_workflow_file_exists():
    assert _WORKFLOW.is_file(), (
        f"Weekly refresh workflow is missing at {_WORKFLOW}"
    )


def test_installs_playwright(workflow_text):
    assert "playwright" in workflow_text, (
        "analyze_phab.py imports playwright at module load; CI must "
        "`pip install playwright` or the report step ImportErrors."
    )


def test_installs_chromium_browser(workflow_text):
    # Playwright's pip wheel does not include a browser binary —
    # without `playwright install chromium` the launch call fails
    # with "Executable doesn't exist".
    assert "playwright install" in workflow_text
    assert "chromium" in workflow_text


def test_caches_phab_html_cache(workflow_text):
    # The HTML cache holds 600+ pages; re-fetching every Monday would
    # be slow and almost certainly hit Varnish 429.
    assert "actions/cache" in workflow_text
    assert ".phab_html_cache" in workflow_text


def test_runs_analyze_phab(workflow_text):
    assert "analyze_phab.py" in workflow_text, (
        "Wait-time data (data_phab.json, raw_data/) only refreshes "
        "when analyze_phab.py runs."
    )


def test_commits_phab_outputs(workflow_text):
    """The commit step must stage data_phab.json and raw_data/, "
    otherwise wait-time updates never make it to GH Pages."""
    assert "data_phab.json" in workflow_text
    assert "raw_data" in workflow_text
