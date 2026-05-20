"""Tests for the simplified team-view weekly trend chart.

Previously the Team / Per-Week view showed two charts side-by-side:
a top-5 trend plus an all-members trend. The user wanted just the
single all-members view, with the legend ordered by total review
count so the highest-volume reviewer's series gets the first colour
and the lowest-volume entries sit at the bottom of the legend.
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


def test_top_5_trend_chart_is_removed():
    """The top-5 weekly trend chart was folded into the all-members
    chart. Both the canvas and the Chart() constructor must be gone
    so we don't ship orphan markup or JS that fails to bind."""
    html = _render()
    assert 'id="chart-trend-top"' not in html
    assert "chart-trend-top" not in html


def test_all_members_trend_chart_sorts_by_total_reviews_desc():
    """The JS that builds `allMembers` must sort by descending sum of
    weekly counts so the highest-volume reviewer comes first in the
    legend and gets the first colour assignment."""
    html = _render()
    m = re.search(
        r"const allMembers = Object\.keys\(DATA\.weekly_trend\.all_members\)"
        r"\.sort\(\(a, b\) => \{"
        r".*?"
        r"return sumB - sumA;"
        r"\s*\}\);",
        html, re.DOTALL,
    )
    assert m is not None, (
        "allMembers must be sorted by descending review-count sum "
        "(sumB - sumA) so the top reviewer leads the legend."
    )


def test_all_members_chart_still_uses_weekly_tooltip():
    """Regression guard — the consolidated chart must keep the shared
    `weeklyTooltip` config so hovering still shows the date range."""
    html = _render()
    m = re.search(
        r"chart-trend-all.*?maintainAspectRatio",
        html, re.DOTALL,
    )
    assert m is not None
    assert "weeklyTooltip" in m.group(0)
