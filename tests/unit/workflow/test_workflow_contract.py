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


# Test now lives at tests/unit/workflow/, so .parents[3] is repo root.
_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "refresh.yml"


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


def test_caches_commit_files_cache(workflow_text):
    """The per-subdir pie chart needs file paths for each
    'without team review' commit (~100 SHAs). Caching avoids paying
    that many GitHub round-trips on every weekly run."""
    assert ".commit_files_cache" in workflow_text


def test_runs_analyze_phab(workflow_text):
    assert "analyze_phab.py" in workflow_text, (
        "Wait-time data (data_phab.json, raw_data/) only refreshes "
        "when analyze_phab.py runs."
    )


def test_commits_phab_outputs(workflow_text):
    """The commit step must stage raw_data/ so wait-time updates make
    it to GH Pages. analyze_phab.py is still referenced even though
    per-team data_phab.json files live under each <slug>/ — covered
    by `test_commits_per_team_subfolders`."""
    assert "analyze_phab.py" in workflow_text
    assert "raw_data" in workflow_text


def test_commits_per_team_subfolders(workflow_text):
    """The commit step must stage every registered team's subfolder
    so their data_git.json / data_phab.json / index.html land in
    the auto-publish push. A future team added to TEAMS that's
    missing here will silently never appear on the live site."""
    from reviewstats.teams import TEAMS
    for slug in TEAMS:
        assert f"{slug}/" in workflow_text, (
            f"workflow doesn't commit the {slug}/ subfolder — its "
            "data will never make it to GH Pages."
        )


def test_commits_landing_index_at_root(workflow_text):
    """The root index.html (landing picker) needs to be committed
    too — it's regenerated each run by analyze_git.py."""
    # `index.html` shows up in the cache-key comments too; pin the
    # specific git add line by matching the surrounding shape.
    assert "git add" in workflow_text
    assert "index.html" in workflow_text


def test_runs_integration_tests(workflow_text):
    """tests/integration/ contains the end-to-end value-side checks
    (build_report → render_html assertions). A workflow that only
    runs tests/unit/ would silently skip them. Pin the broader
    `pytest tests/` invocation so adding more integration tests
    in the future doesn't require a workflow edit."""
    assert "pytest tests/" in workflow_text, (
        "Workflow must run `pytest tests/` (not just tests/unit/) "
        "so the integration suite runs in CI."
    )


def test_installs_copilot_cli(workflow_text):
    """The summary backend shells out to the `copilot` binary, which is not
    preinstalled on the runner — without this step every area 404s on a
    missing executable and the overviews silently go blank."""
    assert "@github/copilot" in workflow_text


def test_grants_copilot_requests_permission(workflow_text):
    """Copilot CLI authenticates with the workflow's built-in GITHUB_TOKEN,
    but only if the job requests `copilot-requests: write`."""
    assert "copilot-requests: write" in workflow_text


def test_does_not_use_retired_github_models(workflow_text):
    """GitHub Models was retired 2026-07-30 — its endpoint returns 410 and
    `models: read` grants nothing. Guard against a revert."""
    assert "models: read" not in workflow_text
    assert "REVIEW_STATS_SUMMARY_BACKEND: github" not in workflow_text


def test_selects_the_copilot_summary_backend(workflow_text):
    assert "REVIEW_STATS_SUMMARY_BACKEND: copilot" in workflow_text


def test_git_add_line_does_not_stage_root_author_patches(workflow_text):
    """dump_author_patches.py now writes per-team
    `<slug>/author_patches.txt`. The old root-level path no longer
    exists — staging it in `git add` would be a no-op and a
    maintenance trap. The per-team files are covered by `<slug>/`."""
    git_add_lines = [
        line for line in workflow_text.splitlines()
        if line.lstrip().startswith("git add")
    ]
    assert git_add_lines, "Workflow has no git-add line at all?"
    for line in git_add_lines:
        assert "author_patches.txt" not in line, (
            "git add still references root author_patches.txt — "
            "per-team files are picked up by `<slug>/`."
        )


class TestTheAddMetricSkillStaysWiredToReality:
    """A skill that documents things that no longer exist is worse than none.

    These pin only the load-bearing references — the guard names it tells you to read
    the output of, and the warning strings it tells you to look for. If a guard is
    renamed or a warning reworded, the skill goes stale silently and the next person
    follows instructions that cannot be followed.
    """

    _ROOT = Path(__file__).resolve().parents[3]

    @property
    def _skill(self) -> str:
        p = self._ROOT / ".claude" / "skills" / "add-media-metric" / "skill.md"
        assert p.is_file(), f"skill missing at {p}"
        return p.read_text(encoding="utf-8")

    def test_the_project_rules_point_at_it(self):
        """Otherwise nothing routes a METRICS change through it."""
        rules = (self._ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "add-media-metric" in rules

    def test_the_guards_it_names_exist(self):
        src = (self._ROOT / "reviewstats" / "perfmetrics.py").read_text(
            encoding="utf-8")
        for fn in ("ambiguous_matches", "unresolved_metrics", "is_safe_to_write",
                   "pick_signature", "matches_test"):
            assert f"def {fn}" in src, f"{fn} is documented but does not exist"
            assert fn in self._skill, f"{fn} exists but the skill does not mention it"

    def test_the_warning_text_it_tells_you_to_look_for_is_the_text_emitted(self):
        """The skill quotes both stderr warnings. If the wording drifts, a reader
        greps for a string that is never printed and concludes all is well."""
        fetcher = (self._ROOT / "fetch_perf_metrics.py").read_text(encoding="utf-8")
        for phrase in ("expected 1", "produced no Firefox data"):
            assert phrase in fetcher, f"{phrase!r} is not what the fetcher prints"
            assert phrase in self._skill, f"{phrase!r} missing from the skill"

    def test_the_config_keys_it_documents_are_the_keys_read(self):
        fetcher = (self._ROOT / "fetch_perf_metrics.py").read_text(encoding="utf-8")
        for key in ("test_suffix", "lower_is_better", "platform"):
            assert key in fetcher, key
            assert key in self._skill, key
        assert "test_contains" not in fetcher, (
            "removed field is back; the skill says there is no substring match")

    def test_it_documents_that_a_new_group_needs_no_template_work(self):
        """The claim is only safe while the template derives groups from data, which
        a render test pins. Asserted together so the pair cannot drift apart."""
        tmpl = (self._ROOT / "templates" / "index.html.tmpl").read_text(
            encoding="utf-8")
        assert "METRICS.groups" in tmpl
        assert "METRICS.groups" in self._skill
