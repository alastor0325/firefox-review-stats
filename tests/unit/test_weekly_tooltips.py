"""Tests for the ISO-week tooltip enhancement.

Weekly charts show ISO week labels like `2026-W20` on the x-axis,
which alone don't tell you what calendar dates the week covers. The
template adds an `isoWeekToDateRange` helper + a shared
`weeklyTooltip` config that prepends e.g. "May 11 – May 17, 2026"
to the tooltip title. These tests verify the JS is present and
that every weekly chart uses the shared config.
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


class TestHelpers:
    def test_iso_week_to_date_range_helper_present(self):
        html = _render()
        assert "function isoWeekToDateRange(" in html, (
            "Template needs the isoWeekToDateRange helper to convert "
            "'2026-W20' into a calendar range for weekly tooltips."
        )

    def test_helper_uses_iso_8601_week_definition(self):
        """ISO 8601: week 1 is the week containing January 4th. The
        helper must use that anchor or weekly labels will drift on
        years where Jan 1 falls late in the week."""
        html = _render()
        assert "Date.UTC(year, 0, 4)" in html, (
            "isoWeekToDateRange should anchor on January 4th per ISO 8601"
        )

    def test_shared_weekly_tooltip_config_exists(self):
        html = _render()
        assert "const weeklyTooltip" in html, (
            "A shared `weeklyTooltip` config keeps all weekly charts "
            "in lockstep — when the tooltip format changes, every "
            "chart picks it up at once."
        )

    def test_tooltip_title_combines_week_label_and_range(self):
        html = _render()
        # The title callback should reference both the label (week
        # string) and the date range so users see both.
        assert "isoWeekToDateRange(label)" in html


class TestChartsUseSharedTooltip:
    """Every weekly chart must opt into the shared `weeklyTooltip` so
    the date-range hover is consistent across the page."""

    def test_all_members_trend_chart_uses_weekly_tooltip(self):
        html = _render()
        m = re.search(
            r"chart-trend-all.*?maintainAspectRatio",
            html, re.DOTALL,
        )
        assert m is not None
        assert "weeklyTooltip" in m.group(0), (
            "Weekly trend (all members) chart must use shared weeklyTooltip"
        )

    def test_team_wait_weekly_median_uses_weekly_tooltip(self):
        html = _render()
        m = re.search(
            r"chart-wait-weekly.*?maintainAspectRatio",
            html, re.DOTALL,
        )
        assert m is not None
        assert "weeklyTooltip" in m.group(0), (
            "Median wait by week chart must use shared weeklyTooltip"
        )

    def test_member_profile_weekly_chart_uses_weekly_tooltip(self):
        html = _render()
        m = re.search(
            r"chart-profile-weekly.*?maintainAspectRatio",
            html, re.DOTALL,
        )
        assert m is not None
        assert "weeklyTooltip" in m.group(0), (
            "Member Profile weekly activity chart must use shared weeklyTooltip"
        )
