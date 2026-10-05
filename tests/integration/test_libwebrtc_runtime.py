"""Run the libwebrtc view in a real browser and check what it says.

The unit tests read the template as text, which cannot catch arithmetic in the
page's JavaScript: a lag that read "-17 days behind" passed all of them. Dates
here are relative to the real today, so countdowns can be asserted exactly.
Skipped without Playwright or a browser, like test_page_runtime.py.
"""

import pathlib
from datetime import date, timedelta

import pytest

from tests.integration.test_page_runtime import CHROME
from tests.unit.render.test_sticky_layout import _MINIMAL_DATA


def _iso(days):
    return (date.today() + timedelta(days=days)).isoformat()


def _view(as_of_days=0):
    row = {"label": "Nightly", "firefox": "159.0a1", "milestone": 155,
           "branch_head": "branch-heads/8059", "branched": _iso(-21),
           "vs_chrome": "1 ahead", "patches": 149,
           "last_change": {"date": _iso(-10), "kind": "vendor"}}
    plan_row = {"chrome_stable": None, "nightly_start": None}
    return {
        "chrome_stable": 154, "as_of": _iso(as_of_days), "rows": [row],
        "plan": {"as_of": _iso(as_of_days), "lag": {
            "last_vendored": _iso(-17), "upstream_head": _iso(0), "behind": 201},
            "rows": [
                {**plan_row, "milestone": 155, "firefox": 159, "chrome_branch": _iso(-21),
                 "merge_day": _iso(3), "vendoring": True, "fastforward_bug": 2072400,
                 "in_progress": True},
                {**plan_row, "milestone": 156, "firefox": 160, "chrome_branch": _iso(7),
                 "merge_day": _iso(17), "vendoring": False, "fastforward_bug": None,
                 "in_progress": None},
                {**plan_row, "milestone": 157, "firefox": None, "chrome_branch": _iso(30),
                 "merge_day": None, "vendoring": False, "fastforward_bug": None,
                 "in_progress": None},
            ]},
        "patch_stack": {"as_of": _iso(as_of_days), "history": [
            {"month": "2026-09", "count": 145, "sampled": "2026-09-30"},
            {"month": "2026-10", "count": 149, "sampled": "2026-10-05"}]},
    }


def _run(tmp_path, view):
    pytest.importorskip("playwright", reason="playwright not installed")
    from playwright.sync_api import sync_playwright

    from reviewstats.render import render_html

    path = tmp_path / "index.html"
    path.write_text(render_html(_MINIMAL_DATA, libwebrtc_data=view), encoding="utf-8")
    errors = []
    with sync_playwright() as pw:
        launch = {"headless": True}
        if pathlib.Path(CHROME).exists():
            launch["executable_path"] = CHROME
        try:
            browser = pw.chromium.launch(**launch)
        except Exception as exc:
            pytest.skip(f"no Chromium available to execute the page: {exc}")
        try:
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error"
                    and "Failed to load resource" not in m.text else None)
            page.goto(path.resolve().as_uri() + "#libwebrtc", wait_until="load")
            page.wait_for_timeout(500)
            text = lambda sel: page.evaluate(
                "(s) => [...document.querySelectorAll(s)].map(e => e.innerText"
                ".replace(/\\s+/g, ' ').trim())", sel)
            state = {
                "view": page.evaluate("() => document.body.dataset.view"),
                "releases": text("#libwebrtc-rows tr"),
                "plan": text("#lw-plan-rows tr"),
                "lag": text("#lw-lag")[0],
                "stale": page.evaluate(
                    "() => { const e = document.getElementById('libwebrtc-stale');"
                    " return e.offsetParent ? e.innerText : ''; }"),
                "chart": page.evaluate("() => !!Chart.getChart('chart-lw-stack')"),
            }
        finally:
            browser.close()
    return state, errors


def test_the_view_runs_and_counts_from_today(tmp_path):
    state, errors = _run(tmp_path, _view())
    assert errors == []
    assert state["view"] == "libwebrtc"
    assert "149" in state["releases"][0] and "(3 wk)" in state["releases"][0]
    # Anchored on the colon: "-17 days" also contains "17 days".
    assert ": 17 days and 201 commits behind" in state["lag"]
    assert "in progress, 3 days to Beta merge" in state["plan"][0]
    assert "Bug 2072400" in state["plan"][0]
    assert "Firefox 160 (projected)" in state["plan"][1]
    assert "Branches in 7 days" in state["plan"][1]
    assert "branches too late for its train" in state["plan"][2]
    assert state["chart"] is True
    assert state["stale"] == ""


def test_old_data_is_named_as_stale(tmp_path):
    state, errors = _run(tmp_path, _view(as_of_days=-30))
    assert errors == []
    assert "Release data" in state["stale"] and "the milestone plan" in state["stale"]
