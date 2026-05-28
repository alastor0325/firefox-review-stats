"""Frontend contract for the 1-Month / 3-Month / 6-Month period toggle.

The template renders four period buttons (1m / 3m / total≡6m / weekly).
Team-view sections share one set of DOM nodes; the JS reads
`DATA.team_views[key]` on each period change and re-renders them.
"""

import re

from reviewstats.render import render_html


def _minimal_data(team_views=None) -> dict:
    base = {
        "meta": {
            "path": "dom/media", "paths": ["dom/media"],
            "group": "g", "excludes": [],
            "window_start": "2025-11-15", "window_end": "2026-05-15",
            "generated_at": "2026-05-15T00:00:00Z",
        },
        "summary": {
            "total_patches": 1, "group_tagged_patches": 1,
            "group_tagged_pct": 1.0,
            "landed_without_team_review": 0,
            "landed_without_team_review_pct": 0,
            "landed_without_team_review_by_subdir": {},
            "landed_without_team_review_list": [],
            "unique_individuals": 0, "avg_per_week": 0,
        },
        "concentration": {"top1_share": 0, "top3_share": 0, "top5_share": 0,
                          "gini": 0, "bus_factor": 0},
        "within_group_total": [], "sole_reviewer": [],
        "total_reviews_per_member": [],
        "weekly_trend": {"weeks": [], "top_reviewers": [],
                         "all_members": {}, "authored_per_member": {}},
        "members": {}, "authors": {"top_total": [], "reviewer_matrix": {}},
        "per_member_authors": {}, "member_authored_counts": {},
    }
    if team_views is not None:
        base["team_views"] = team_views
    return base


class TestPeriodButtons:
    def test_three_aggregate_buttons_plus_weekly(self):
        html = render_html(_minimal_data())
        for v in ("1m", "3m", "total", "weekly"):
            assert re.search(rf'<button[^>]*data-period="{v}"', html), (
                f'missing data-period="{v}" button'
            )

    def test_six_month_button_is_default_active(self):
        # The 6-Month slice keeps the legacy `data-period="total"`
        # value as the page's default, so existing bookmarks / tests
        # that pin the default state don't have to migrate.
        html = render_html(_minimal_data())
        assert re.search(
            r'<button[^>]*data-period="total"[^>]*class="active"', html
        ), "6-Month (data-period=total) button must start active"
        m = re.search(r'<body[^>]*>', html)
        assert m and 'data-period="total"' in m.group(0)

    def test_button_order_runs_short_to_long_then_weekly(self):
        # User intuition reads left-to-right; ordering the periods 1 → 3
        # → 6 (Total) before Per-Week makes the toggle scannable.
        html = render_html(_minimal_data())
        positions = {
            v: html.find(f'data-period="{v}"')
            for v in ("1m", "3m", "total", "weekly")
        }
        assert all(p > 0 for p in positions.values())
        assert positions["1m"] < positions["3m"] < positions["total"] < positions["weekly"]


class TestPeriodKeyMap:
    """The JS maps the toggle-bar's `data-period` values to
    `team_views` keys. Without that mapping the period-change handler
    cannot find a data slice to re-render with."""

    def test_period_to_key_map_is_present(self):
        html = render_html(_minimal_data())
        assert "PERIOD_TO_KEY" in html
        # All three aggregate slots must be mapped — `weekly` is
        # intentionally absent (it's a separate view, not a window).
        assert "'total'" in html and "'6m'" in html
        assert "'1m'" in html and "'3m'" in html

    def test_render_team_total_view_function_exists(self):
        html = render_html(_minimal_data())
        assert "function renderTeamTotalView(" in html
        # Period change handler calls it on every aggregate click.
        assert "renderTeamTotalView(key)" in html


class TestFallbackWhenTeamViewsMissing:
    """When `DATA.team_views` is absent (old data, pre-feature), the
    page must still render the 6m slice — but the 1m / 3m buttons
    should be hidden so the user doesn't think the new periods work."""

    def test_hide_buttons_block_present(self):
        # Static markup check — the JS itself hides them at runtime.
        html = render_html(_minimal_data())
        assert "if (!DATA.team_views)" in html
        assert 'data-period="1m"' in html
        assert 'data-period="3m"' in html
