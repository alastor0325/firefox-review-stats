"""Tests for the Team / Per-Week wait-time view markup + JS contract.

The previous Per-Week view rendered the same 6-month rollup as the
6-Month view (~214 patches over the window). Users expected per-week
data instead. The fix:

* The existing wait-time block is scoped to `total-only` so it shows
  only in Team / 6-Month.
* A new `phab-section-week` block is `weekly-only` and reads from
  `PHAB_DATA.last_week`.
* The trend chart (`chart-wait-weekly`) is left in the 6-month block;
  it has no meaning on a single-week slice.
"""

import re

from reviewstats.render import render_html


_MINIMAL_DATA = {
    "meta": {"path": "x", "group": "g",
             "window_start": "2026-05-01", "window_end": "2026-05-15",
             "generated_at": "2026-05-15T00:00:00Z"},
    "summary": {"total_patches": 0, "group_tagged_patches": 0,
                "group_tagged_pct": 0, "with_individual_named": 0,
                "with_individual_pct": 0, "group_only": 0,
                "group_only_pct": 0, "unique_individuals": 0,
                "avg_per_week": 0},
    "concentration": {"top1_share": 0, "top3_share": 0, "top5_share": 0,
                       "gini": 0, "bus_factor": 0},
    "within_group_total": [], "sole_reviewer": [],
    "total_reviews_per_member": [],
    "weekly_trend": {"weeks": [], "top_reviewers": [],
                      "all_members": {}, "authored_per_member": {}},
    "members": {}, "authors": {"top_total": [], "reviewer_matrix": {}},
    "per_member_authors": {}, "member_authored_counts": {},
}


def _render() -> str:
    return render_html(_MINIMAL_DATA)


def test_6month_wait_block_scoped_to_total_only():
    """The existing wait-time block must opt into `total-only` so it
    no longer shows in the Per-Week view (where the data is wrong)."""
    html = _render()
    m = re.search(
        r'<div id="phab-section"([^>]*)>',
        html,
    )
    assert m is not None, "phab-section block missing"
    attrs = m.group(1)
    assert "team-only" in attrs
    assert "total-only" in attrs, (
        "phab-section must be tagged total-only so the 6-month rollup "
        "hides when the user switches to Per-Week."
    )


def test_per_week_wait_block_exists_and_is_weekly_only():
    html = _render()
    m = re.search(
        r'<div id="phab-section-week"([^>]*)>',
        html,
    )
    assert m is not None, (
        "Per-Week view needs its own #phab-section-week block."
    )
    attrs = m.group(1)
    assert "team-only" in attrs
    assert "weekly-only" in attrs


def test_per_week_block_renders_summary_and_histogram():
    html = _render()
    block_re = re.compile(
        r'<div id="phab-section-week".*?(?=</main>|<!-- ====)',
        re.DOTALL,
    )
    block = block_re.search(html)
    assert block is not None
    chunk = block.group(0)
    assert 'id="phab-week-summary-grid"' in chunk
    assert 'id="chart-wait-hist-week"' in chunk


def test_per_week_block_omits_trend_chart():
    """A one-week slice has no trend; the chart-wait-weekly canvas
    must stay in the 6-month block only."""
    html = _render()
    block = re.search(
        r'<div id="phab-section-week".*?(?=</main>|<!-- ====)',
        html, re.DOTALL,
    ).group(0)
    assert "chart-wait-weekly" not in block, (
        "chart-wait-weekly is a 6-month trend; the per-week block "
        "must not include it."
    )


def test_js_renders_last_week_slice():
    """The JS body must read PHAB_DATA.last_week and bind it to the
    new histogram canvas. Without this the new HTML stays empty."""
    html = _render()
    assert "PHAB_DATA.last_week" in html
    assert "chart-wait-hist-week" in html
    assert "phab-week-summary-grid" in html


def test_js_short_circuits_when_no_last_week_data():
    """If PHAB_DATA.last_week is missing / empty the per-week block
    should not be revealed — guard with a truthy-and-n>0 check."""
    html = _render()
    # Look for the conditional that gates display of the new block.
    m = re.search(
        r"const lw = PHAB_DATA\.last_week;\s*if \(lw && lw\.n > 0\)",
        html,
    )
    assert m is not None, (
        "JS should guard the per-week render on `lw && lw.n > 0` so "
        "weeks with no samples don't reveal an empty section."
    )
