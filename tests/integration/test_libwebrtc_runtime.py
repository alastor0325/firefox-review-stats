"""Run the libwebrtc view in a real browser and check what it says.

The unit tests read the template as text, which cannot catch arithmetic in the
page's JavaScript: a lag that read "-17 days behind" passed all of them. Dates
here are relative to the real today, so countdowns can be asserted exactly.
Skipped without Playwright or a browser, like test_page_runtime.py.
"""

import contextlib
import json
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


_RUNS = {}


def _run(tmp_path, view):
    """Render and run `view` in a browser; identical views share one run."""
    key = json.dumps(view, sort_keys=True)
    if key not in _RUNS:
        _RUNS[key] = _run_uncached(tmp_path, view)
    return _RUNS[key]


@contextlib.contextmanager
def _page(tmp_path, view, width=1280):
    """Render `view`, open it in Chromium at #libwebrtc, and yield
    (page, errors) with both page errors and console errors collected."""
    pytest.importorskip("playwright", reason="playwright not installed")
    from playwright.sync_api import sync_playwright

    from reviewstats.render import render_html

    path = tmp_path / f"index-{width}.html"
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
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error"
                    and "Failed to load resource" not in m.text else None)
            page.goto(path.resolve().as_uri() + "#libwebrtc", wait_until="load")
            page.wait_for_selector("#libwebrtc-rows tr")
            yield page, errors
        finally:
            browser.close()


def _run_uncached(tmp_path, view):
    with _page(tmp_path, view) as (page, errors):
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
            "body": page.evaluate("() => document.getElementById('libwebrtc-section').innerText"),
            "chart": page.evaluate("() => !!Chart.getChart('chart-lw-stack')"),
            "plan_cells": page.evaluate(
                "() => [...document.querySelectorAll('#lw-plan-rows tr')]"
                ".map(t => [...t.cells].map(c => c.innerText.trim()))"),
            "headers": page.evaluate(
                "() => [...document.querySelectorAll('#libwebrtc-section thead tr')]"
                ".map(t => [...t.cells].map(c => c.textContent.trim()))"),
            "missing_summary": text("#lw-missing-summary")[0],
            "missing_col": page.evaluate(
                "() => [...document.querySelectorAll('#libwebrtc-rows tr')]"
                ".map(t => t.cells[7].textContent.trim())"),
            "fix_subjects": page.evaluate(
                "() => [...document.querySelectorAll('.lw-fix .lw-fix-subject')]"
                ".map(e => e.textContent)"),
            "fix_chips": page.evaluate(
                "() => [...document.querySelectorAll('.lw-fix')].map(d =>"
                " [...d.querySelectorAll('.lw-chip')].map(c => c.textContent).join(' '))"),
            "fix_open": page.evaluate(
                "() => [...document.querySelectorAll('.lw-fix')].map(d => d.open)"),
            "fix_bodies": page.evaluate(
                "() => [...document.querySelectorAll('.lw-fix .lw-fix-body')]"
                ".map(b => [...b.querySelectorAll('.lw-fix-line')]"
                ".map(l => l.textContent.replace(/\\s+/g, ' ').trim()).join(' '))"),
            "stack_summary": text("#lw-stack-summary")[0],
            "fold_marker": page.evaluate(
                "() => { const s = document.querySelector('.lw-fix summary');"
                " return s ? getComputedStyle(s, '::before').content : null; }"),
            "unvendored_links": page.evaluate(
                "() => [...document.querySelectorAll('.lw-fix-body a')].map(a => a.href)"),
            "branch_links": page.evaluate(
                "() => [...document.querySelectorAll('#libwebrtc-rows a')]"
                ".map(a => [a.textContent, a.href])"),
        }
    return state, errors


def test_the_view_runs_and_counts_from_today(tmp_path):
    state, errors = _run(tmp_path, _view())
    assert errors == []
    assert state["view"] == "libwebrtc"
    assert "149" in state["releases"][0] and "(3 wk ago)" in state["releases"][0]
    # Anchored: "-17 days" would also contain "17 days".
    assert state["lag"] == ("Nightly is 201 commits (17 days) behind upstream main; "
                            f"its newest vendored commit is from {_iso(-17)}.")
    assert "Vendoring · 3 days to Beta merge" in state["plan"][0]
    assert "Bug 2072400" in state["plan"][0]
    assert state["plan_cells"][1][3] == "160"
    assert "Branches in 7 days" in state["plan"][1]
    assert "misses its train" in state["plan"][2]
    assert state["chart"] is True
    assert state["branch_links"] == [[
        "branch-heads/8059",
        "https://webrtc.googlesource.com/src/+log/refs/heads/main..refs/branch-heads/8059"]]
    assert state["stale"] == ""


def test_old_data_is_named_as_stale(tmp_path):
    state, errors = _run(tmp_path, _view(as_of_days=-30))
    assert errors == []
    assert "the releases table" in state["stale"] and "the milestone plan" in state["stale"]


def test_a_stale_not_vendored_list_is_named(tmp_path):
    view = _view()
    view["rows"][0]["unvendored"] = {"as_of": _iso(-30), "commits": []}
    state, errors = _run(tmp_path, view)
    assert errors == [] and state["stale"].startswith("Out of date: Nightly's missing fixes")


def _commit(c, subject, fix, role="landed"):
    """A commit as fetch_libwebrtc_status.py writes it: Python's
    fix_identity sets `fix` and `role`."""
    return {"sha": c * 40, "subject": subject, "fix": fix, "role": role}


def _with_lists(view):
    """One fix on three trains (Beta and Release share M154), one on two, a
    land/revert/reland chain on ESR 115, a clear ESR 140, no data for ESR 153."""
    base = view["rows"][0]
    stopped, harden = "Ensure stopped transceivers do not hold a channel", "Harden payload capacity checks"
    jsep = "JsepTransportController: Remove raw pointers to description objects"
    m154 = [_commit("b", f"[M154] {stopped}", stopped), _commit("c", f"[M154] {harden}", harden)]
    view["rows"] = [
        {**base, "label": "Nightly", "unvendored": {"as_of": _iso(0), "commits": [
            _commit("a", f"[M155] {stopped}", stopped)]}},
        {**base, "label": "Beta", "milestone": 154, "unvendored": {"as_of": _iso(0), "commits": m154}},
        {**base, "label": "Release", "milestone": 154, "unvendored": {"as_of": _iso(0), "commits": m154}},
        {**base, "label": "ESR 153", "milestone": 149, "unvendored": None},
        {**base, "label": "ESR 140", "milestone": 135, "unvendored": {"as_of": _iso(0), "commits": []}},
        {**base, "label": "ESR 115", "milestone": 120, "unvendored": {"as_of": _iso(-30), "commits": [
            _commit("g", f'Revert^2 "[M120] {jsep}"', jsep, "relanded"),
            _commit("f", f'Revert "[M120] {jsep}"', jsep, "reverted"),
            _commit("e", f"[M120] {jsep}", jsep)]}},
    ]
    return view


def test_missing_fixes_are_one_foldable_list(tmp_path):
    state, errors = _run(tmp_path, _with_lists(_view()))
    assert errors == []
    # Each fix once: the same upstream fix on several trains, and a revert
    # chain, are one row each.
    assert state["fix_subjects"] == [
        "Ensure stopped transceivers do not hold a channel",
        "Harden payload capacity checks",
        "JsepTransportController: Remove raw pointers to description objects"]
    # Only the releases missing the fix, in table order.
    assert state["fix_chips"] == ["Nightly Beta Release", "Beta Release", "ESR 115"]
    assert state["fix_open"] == [False, False, False]
    assert state["missing_summary"] == ("3 fixes missing from 4 of 5 releases. "
                                        "ESR 153 wasn't checked this week.")


def test_an_expanded_fix_shows_each_release_and_commit(tmp_path):
    state, _ = _run(tmp_path, _with_lists(_view()))
    first, _, jsep = state["fix_bodies"]
    # Releases on one milestone branch share a line.
    assert first == f"Nightly · M155 {'a' * 10} Beta, Release · M154 {'b' * 10}"
    assert jsep == (f"ESR 115 · M120 {'e' * 10} landed {'f' * 10} reverted "
                    f"{'g' * 10} relanded · as of {_iso(-30)}")
    assert state["unvendored_links"][0] == "https://webrtc.googlesource.com/src/+/" + "a" * 40


def test_releases_table_counts_missing_fixes_per_release(tmp_path):
    state, _ = _run(tmp_path, _with_lists(_view()))
    assert state["missing_col"] == ["1", "2", "2", "—", "0", "1"]


def test_without_lists_the_section_says_so(tmp_path):
    state, errors = _run(tmp_path, _view())
    assert errors == [] and state["missing_summary"] == (
        "No data yet; the next weekly refresh fills this in.")


def test_page_copy(tmp_path):
    """Every heading uses the page's terms (vendored / missing / fix);
    explanations live behind (i) icons, not in the labels."""
    state, _ = _run(tmp_path, _with_lists(_view()))
    assert state["headers"] == [
        ["Channel", "Version", "Milestone", "Branch", "Branched", "vs Chrome stable",
         "Mozilla patches", "Missing fixes", "Last libwebrtc change"],
        ["Milestone", "Branches", "Chrome stable", "Firefox", "Nightly starts",
         "Beta merge", "Status"]]
    assert "to triage" not in state["body"].lower()
    assert state["stack_summary"] == "149 patches, up 4 since Sep 2026."


def test_each_fix_row_shows_it_folds(tmp_path):
    """A flex <summary> loses the browser's disclosure triangle; the row
    must still show that it opens."""
    state, _ = _run(tmp_path, _with_lists(_view()))
    assert state["fold_marker"] == '"▸"'


_LIST_STATE = """() => ({
  summary: document.getElementById('lw-missing-summary').textContent,
  rows: [...document.querySelectorAll('.lw-fix')].filter(d => d.offsetParent)
          .map(d => d.querySelector('.lw-fix-subject').textContent),
  pressed: [...document.querySelectorAll('.lw-filter[aria-pressed="true"]')]
          .map(b => b.textContent),
  buttons: [...document.querySelectorAll('.lw-filter')].map(b => b.textContent),
  focused: document.activeElement && document.activeElement.textContent,
  matched: [...document.querySelectorAll('.lw-fix')].filter(d => d.offsetParent)
          .map(d => [...d.querySelectorAll('.lw-chip.is-match')].map(c => c.textContent).join()),
  // Left edge of every chip row vs its subject's left edge.
  misaligned: [...document.querySelectorAll('.lw-fix')].filter(d => d.offsetParent)
          .filter(d => Math.abs(d.querySelector('.lw-chip').getBoundingClientRect().left
                 - d.querySelector('.lw-fix-subject').getBoundingClientRect().left) > 1).length,
})"""


def _filter_button(label):
    """JS that clicks the filter pill whose label is `label` ("All" too)."""
    return ("() => [...document.querySelectorAll('.lw-filter')]"
            f".find(b => b.textContent.split(' ')[0] === {json.dumps(label.split(' ')[0])}"
            f" && b.textContent.startsWith({json.dumps(label)})).click()")


def _interact(tmp_path, view, width, steps):
    """The list's state on load, then after each JS step."""
    with _page(tmp_path, view, width) as (page, errors):
        states = [page.evaluate(_LIST_STATE)]
        for step in steps:
            page.evaluate(step)
            states.append(page.evaluate(_LIST_STATE))
    assert errors == []
    return states


@pytest.mark.parametrize("width", [730, 1280])
def test_chips_line_up_under_the_subject(tmp_path, width):
    (state,) = _interact(tmp_path, _with_lists(_view()), width, [])
    assert state["misaligned"] == 0


def test_a_release_filter_narrows_the_list(tmp_path):
    all_, release, clear, unchecked, back = _interact(tmp_path, _with_lists(_view()), 1280, [
        _filter_button("Release"), _filter_button("ESR 140"),
        _filter_button("ESR 153"), _filter_button("All")])
    assert all_["buttons"] == ["All", "Nightly 1", "Beta 2", "Release 2", "ESR 153 ?",
                               "ESR 140 0", "ESR 115 1"]
    assert all_["pressed"] == ["All"] and len(all_["rows"]) == 3
    assert release["pressed"] == ["Release 2"]
    assert release["rows"] == ["Ensure stopped transceivers do not hold a channel",
                               "Harden payload capacity checks"]
    # The filtered release is marked in each row; the other chips stay.
    assert release["matched"] == ["Release", "Release"]
    # The unchecked release stays mentioned whatever the filter.
    assert release["summary"] == ("2 fixes missing from Release. "
                                  "ESR 153 wasn't checked this week.")
    assert clear["rows"] == [] and clear["summary"].startswith(
        "✓ ESR 140 has every fix on its branch.")
    assert unchecked["rows"] == [] and unchecked["summary"] == "ESR 153 wasn't checked this week."
    assert back["pressed"] == ["All"] and len(back["rows"]) == 3 and back["matched"] == ["", "", ""]


def test_the_tables_missing_count_applies_the_filter_and_moves_focus(tmp_path):
    _, after = _interact(tmp_path, _with_lists(_view()), 1280, [
        "() => document.querySelectorAll('#libwebrtc-rows tr')[5].cells[7]"
        ".querySelector('button').click()"])
    assert after["pressed"] == ["ESR 115 1"]
    assert after["rows"] == ["JsepTransportController: Remove raw pointers to description objects"]
    assert after["focused"] == "ESR 115 1"
