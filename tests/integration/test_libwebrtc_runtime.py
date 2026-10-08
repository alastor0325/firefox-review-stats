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


_UP = lambda s, absorbed=False: {"subject": s, "absorbed": absorbed}
_DROP = lambda s, update, absorbed=False: {"subject": s, "absorbed": absorbed, "update": update}
# Shaped like real Aug-Oct 2026: two updates in September dropped five
# patches (four absorbed upstream) and added four.
_STACK = [
    {"month": "2026-08", "count": 150, "sampled": "2026-08-31", "sha": "a" * 40,
     "added": [_UP("Bug 2054622 - WebRTC backport: PipeWire mmap improvements")],
     "dropped": [], "updates": [{"milestone": 153, "bug": 2064200, "date": "2026-08-28"}]},
    {"month": "2026-09", "count": 149, "sampled": "2026-09-30", "sha": "b" * 40,
     "added": [_UP("Bug 2069067 - (fix-44d3a8877e) support AudioReceiveStreamInterface"),
               _UP("Bug 1996020 - use I420Buffer::CreateOrNull"),
               _UP("Bug 1996020 - use I420Buffer::CreateOrNull"),
               _UP("Bug 1996020 - Cleanup remaining usages")],
     "dropped": [_DROP("Bug 1654112 - Don't check the calling thread in GetSources", 155),
                 _DROP("Bug 2054622 - WebRTC backport: PipeWire mmap improvements", 154, True),
                 _DROP("Bug 2055703 - WebRTC backport: Screen capture: reject negative", 154, True),
                 _DROP("Bug 2058627 - WebRTC backport: Screen capture: check n_datas", 154, True),
                 _DROP("Bug 2059127 - WebRTC backport: Screen capture: validate", 154, True)],
     "updates": [{"milestone": 154, "bug": 2069067, "date": "2026-09-14"},
                 {"milestone": 155, "bug": 2072400, "date": "2026-09-25"}]},
    {"month": "2026-10", "count": 147, "sampled": "2026-10-07", "sha": "c" * 40,
     "added": [], "dropped": [_DROP("Bug 9 - Something removed by hand", None)], "updates": []},
]


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
        "patch_stack": {"as_of": _iso(as_of_days), "history": _STACK},
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
            "chart": page.evaluate("() => !!Chart.getChart('chart-lw-stack-total') && !!Chart.getChart('chart-lw-stack-change')"),
            "plan_cells": page.evaluate(
                "() => [...document.querySelectorAll('#lw-plan-rows tr')]"
                ".map(t => [...t.cells].map(c => c.innerText.trim()))"),
            "headers": page.evaluate(
                "() => [...document.querySelectorAll('#libwebrtc-section thead tr')]"
                ".map(t => [...t.cells].map(c => c.textContent.trim()))"),
            "missing_summary": text("#lw-missing-summary .lw-summary-count")[0],
            "missing_branch": page.evaluate(
                "() => document.querySelector('#lw-missing-summary .lw-summary-branch')"
                "?.textContent.replace(/\\s+/g, ' ').trim() ?? ''"),
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
            "stack_title": page.evaluate(
                "() => document.querySelector('#lw-stack-section h2').firstChild.textContent.trim()"),
            "panel_tips": page.evaluate(
                "() => [...document.querySelectorAll('.lw-stack-panel-title')]"
                ".map(t => [t.firstChild.textContent.trim(), t.querySelector('.info')?.dataset.tip || ''])"),
            "stack_hero": text("#lw-stack-hero")[0],
            "stack_summary": text("#lw-stack-summary")[0],
            "stack_detail_head": text("#lw-stack-detail .lw-stack-detail-head")[0],
            "stack_detail": text("#lw-stack-detail")[0],
            # textContent: the table sits in a closed <details>.
            "stack_table": page.evaluate(
                "() => [...document.querySelectorAll('#lw-stack-table tbody tr')]"
                ".map(t => [...t.cells].map(c => c.textContent.trim()).join(' ').trim())"),
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


def _branch(n, last):
    return {"branch_commits": n, "last_merge": last}


def _with_lists(view):
    """One fix on three trains (Beta and Release share M154), one on two, a
    land/revert/reland chain on ESR 115, a clear ESR 140, no data for ESR 153."""
    base = view["rows"][0]
    stopped, harden = "Ensure stopped transceivers do not hold a channel", "Harden payload capacity checks"
    jsep = "JsepTransportController: Remove raw pointers to description objects"
    m154 = [_commit("b", f"[M154] {stopped}", stopped), _commit("c", f"[M154] {harden}", harden)]
    view["rows"] = [
        {**base, "label": "Nightly", "unvendored": {**_branch(4, _iso(-5)), "as_of": _iso(0), "commits": [
            _commit("a", f"[M155] {stopped}", stopped)]}},
        {**base, "label": "Beta", "milestone": 154, "branch_head": "branch-heads/8037",
         "unvendored": {**_branch(5, "2026-10-05"), "as_of": _iso(0), "commits": m154}},
        {**base, "label": "Release", "milestone": 154, "branch_head": "branch-heads/8037",
         "unvendored": {**_branch(5, "2026-10-05"), "as_of": _iso(0), "commits": m154}},
        {**base, "label": "ESR 153", "milestone": 149, "branch_head": "branch-heads/7827",
         "unvendored": None},
        {**base, "label": "ESR 140", "milestone": 135, "branch_head": "branch-heads/7049",
         "unvendored": {**_branch(3, "2025-04-07"), "as_of": _iso(0), "commits": []}},
        {**base, "label": "ESR 115", "milestone": 120, "branch_head": "branch-heads/6099",
         # Written before branch_commits existed.
         "unvendored": {"as_of": _iso(-30), "commits": [
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
    # Chrome stable is M154: M149 and older are no longer merged to.
    assert state["missing_branch"] == "ESR 153, ESR 140 and ESR 115 are on closed Chrome branches."


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
    assert state["missing_col"] == ["1", "2", "2", "—", "0 · branch closed", "1 · branch closed"]


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
         "Beta merge", "Status"],
        ["Month", "Total", "Added", "Dropped", "Upstream updates", ""]]
    assert "to triage" not in state["body"].lower()
    assert state["stack_title"] == "Mozilla's own patches on top of upstream libwebrtc"
    (total, total_tip), (change, change_tip) = state["panel_tips"]
    assert (total, change) == ("Total at month end", "Added and dropped each month")
    assert "month-end snapshot" in total_tip
    assert "Dropped: patches Firefox stopped carrying" in change_tip
    assert "backport" in change_tip and "backed out" in change_tip


def test_each_fix_row_shows_it_folds(tmp_path):
    """A flex <summary> loses the browser's disclosure triangle; the row
    must still show that it opens."""
    state, _ = _run(tmp_path, _with_lists(_view()))
    assert state["fold_marker"] == '"▸"'


_LIST_STATE = """() => ({
  summary: document.querySelector('#lw-missing-summary .lw-summary-count').textContent,
  branch: document.querySelector('#lw-missing-summary .lw-summary-branch')?.textContent
          .replace(/\s+/g, ' ').trim() ?? '',
  branchLink: document.querySelector('#lw-missing-summary .lw-summary-branch a')?.href ?? '',
  branchTip: document.querySelector('#lw-missing-summary .lw-summary-branch .info')?.dataset.tip ?? '',
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
    # Which Chrome branch the count is against, and whether Chrome still merges to it.
    assert release["branch"] == "Chrome branch: M154 · branch-heads/8037 · last fix 2026-10-05"
    assert release["branchLink"].endswith("+log/refs/heads/main..refs/branch-heads/8037")
    # A closed branch's 0 is not "fully patched": no ✓, and it says so.
    assert clear["rows"] == [] and clear["summary"].startswith(
        "ESR 140 has all 3 fixes on its Chrome branch.")
    assert clear["branch"] == ("Chrome branch: M135 · branch-heads/7049 · closed 2025-04-07. "
                               "Later fixes aren't counted.")
    assert "only while it supports that milestone" in clear["branchTip"]
    assert unchecked["rows"] == [] and unchecked["summary"] == "ESR 153 wasn't checked this week."
    assert unchecked["branch"] == "Chrome branch: M149 · branch-heads/7827 · closed"
    assert back["pressed"] == ["All"] and len(back["rows"]) == 3 and back["matched"] == ["", "", ""]


def test_the_tables_missing_count_applies_the_filter_and_moves_focus(tmp_path):
    _, after = _interact(tmp_path, _with_lists(_view()), 1280, [
        "() => document.querySelectorAll('#libwebrtc-rows tr')[5].cells[7]"
        ".querySelector('button').click()"])
    assert after["pressed"] == ["ESR 115 1"]
    assert after["rows"] == ["JsepTransportController: Remove raw pointers to description objects"]
    assert after["focused"] == "ESR 115 1"
    # Written before last_merge existed: no date, but still closed.
    assert after["branch"] == "Chrome branch: M120 · branch-heads/6099 · closed. Later fixes aren't counted."


def test_patch_stack_explains_itself(tmp_path):
    state, errors = _run(tmp_path, _view())
    assert errors == []
    # Headline: the total and its change, in words, not colour.
    assert state["stack_hero"].startswith("147") and "2 fewer than at the end of September" in state["stack_hero"]
    # The story of the latest month that had an upstream update.
    # Per update, from which push removed each patch.
    assert state["stack_summary"] == (
        "In September the M154 update dropped 4 (all now in upstream) and the "
        "M155 update dropped 1; 4 new ones were added.")


def test_month_detail_opens_on_the_latest_change(tmp_path):
    state, _ = _run(tmp_path, _view())
    # October has a drop no update push explains: the backout signal wins
    # over the summary's month.
    assert state["stack_detail_head"].startswith("October 2026")
    assert "1 dropped outside an upstream update: check whether it was backed out." in state["stack_detail"]
    assert "not explained by an update" in state["stack_detail"]


def test_selecting_a_month_lists_its_patches(tmp_path):
    with _page(tmp_path, _view()) as (page, errors):
        page.click("#lw-stack-section .lw-stack-table-wrap summary")  # open the table
        page.click("#lw-stack-table tbody tr:nth-child(2) button")
        head = page.inner_text("#lw-stack-detail .lw-stack-detail-head")
        detail = page.text_content("#lw-stack-detail")  # innerText would apply CSS uppercase
        links = page.eval_on_selector_all("#lw-stack-detail a", "as => as.map(a => a.href)")
    assert errors == []
    assert head.startswith("September 2026 · M154 update Sep 14 (Bug 2069067) · "
                           "M155 update Sep 25 (Bug 2072400) · see the change on GitHub")
    assert "Dropped (5)" in detail and "Added (4)" in detail
    assert detail.count("M154 · now in upstream") == 4 and detail.count("M155 · no longer needed") == 1
    assert "outside an upstream update" not in detail
    # Identical subjects collapse.
    assert "Bug 1996020 - use I420Buffer::CreateOrNull (×2)" in detail
    assert "https://bugzilla.mozilla.org/show_bug.cgi?id=2072400" in links
    assert any(l.endswith("a" * 40 + "..." + "b" * 40) for l in links), links


def test_patch_stack_table_twin(tmp_path):
    state, _ = _run(tmp_path, _view())
    assert [r.split(" ")[0:2] for r in state["stack_table"]] == [
        ["Aug", "2026"], ["Sep", "2026"], ["Oct", "2026"]]
    assert state["stack_table"][1].startswith("Sep 2026 149 +4 −5 M154, M155")


def test_detail_opens_on_the_summary_month_when_nothing_is_unexplained(tmp_path):
    view = _view()
    view["patch_stack"]["history"] = [dict(p) for p in _STACK]
    view["patch_stack"]["history"][-1] = {**_STACK[-1], "dropped": [],
                                          "added": [_UP("Bug 10 - New patch")]}
    state, _ = _run(tmp_path, view)
    assert state["stack_detail_head"].startswith("September 2026")

