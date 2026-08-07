"""Tests for the Media Health view — a 5th view, playback only.

The view sits after Recent Changes on the `data-view` axis and carries its own
secondary axis, `data-health` ∈ {roadmap, performance}, in the same top-bar
component the Period and Recent-window groups already use.

It is gated on data availability rather than on a team name: roadmap data is
only injected for the team that has a roadmap, so the tab disappears on the
other teams by itself. That mirrors how Recent Changes already hides itself
when `recent_changes` is absent, and it means `visibleAxisValues` keeps
keyboard navigation correct for free.
"""

import json
import re

from reviewstats.render import render_html


_MINIMAL_DATA = {
    "meta": {"path": "dom/media", "group": "g", "window_start": "2025-11-15",
             "window_end": "2026-05-15", "generated_at": "2026-05-15T00:00:00Z"},
    "summary": {
        "total_patches": 0, "group_tagged_patches": 0, "group_tagged_pct": 0,
        "with_individual_named": 0, "with_individual_pct": 0,
        "group_only": 0, "group_only_pct": 0,
        "unique_individuals": 0, "avg_per_week": 0,
    },
    "concentration": {"top1_share": 0, "top3_share": 0, "top5_share": 0,
                      "gini": 0, "bus_factor": 0},
    "within_group_total": [], "sole_reviewer": [],
    "total_reviews_per_member": [],
    "weekly_trend": {"weeks": [], "top_reviewers": [], "all_members": {}},
    "members": {},
    "authors": {"top_total": [], "reviewer_matrix": {}},
    "per_member_authors": {},
    "member_authored_counts": {},
}

_ROADMAP = {
    "updated": "2026-08-07",
    "audience": "public",
    "summary": "one honest paragraph",
    "aspects": [{"name": "Playing ordinary video", "rating": "good",
                 "text": "t", "rests_on": ["mkv-missing-formats"]}],
    "items": [{
        "bucket": "ranked", "withheld": [], "id": "remote-playback",
        "impact": "S2", "reach": "3", "type": "MISSING",
        "title": "Remote Playback API absent", "consequence": "cannot cast",
        "cost": "L", "confidence": "high", "tags": ["OS-FIT"],
    }],
    "scopes": [{"id": "compat-gaps", "title": "Compat & competitive gaps",
                "ends": True, "blurb": "b"}],
    "metrics": [{"id": "m", "title": "Time to first frame", "source": "Raptor",
                 "exists": True, "target": "TBD",
                 "cross_browser": ["firefox", "chrome"], "note": ""}],
    "metrics_without_target": 1,
    "questions": [{"q": "q", "why": "w"}],
    "closed": [{"what": "HDCP policy checks", "why": "implemented"}],
    "counts": {"total": 1, "ranked": 1, "measure": 0, "continuous": 0},
}


def _render(roadmap=None) -> str:
    return render_html(_MINIMAL_DATA, roadmap_data=roadmap)


class TestViewAxis:
    def test_health_button_present(self):
        assert re.search(r'<button[^>]*data-view="health"', _render(_ROADMAP)), (
            'expected a "health" view button'
        )

    def test_health_button_is_last_on_the_axis(self):
        """Reads as an addition to the existing four rather than a
        reshuffle of them."""
        html = _render(_ROADMAP)
        m = re.search(r'class="toggle-bar"(.*?)</nav>', html, re.DOTALL)
        order = re.findall(r'<button[^>]*data-view="([^"]+)"', m.group(1))
        assert order == ["team", "member", "queue", "recent", "health"], order

    def test_default_view_is_still_team(self):
        """Adding a view must not change where the page lands."""
        m = re.search(r"<body[^>]*>", _render(_ROADMAP))
        assert 'data-view="team"' in m.group(0)


class TestSecondaryAxis:
    def test_health_axis_buttons_present(self):
        html = _render(_ROADMAP)
        for v in ("roadmap", "performance"):
            assert re.search(rf'<button[^>]*data-health="{v}"', html), v

    def test_roadmap_is_the_default_subview(self):
        m = re.search(r"<body[^>]*>", _render(_ROADMAP))
        assert 'data-health="roadmap"' in m.group(0)

    def test_health_toggle_group_is_targetable(self):
        """The CSS hide rule needs the group to carry its own class, the
        same way the Period and Recent groups do."""
        assert "toggle-group-health" in _render(_ROADMAP)

    def test_health_toggle_is_default_off_and_shown_only_in_its_view(self):
        """Asserted as behaviour, not as a per-view rule matrix: the group is
        hidden by default and one rule re-shows it under its owning view. The
        earlier form asserted one selector per *other* view, so every new view
        cost a CSS line and a test assertion that changed nothing."""
        html = _render(_ROADMAP)
        assert re.search(
            r"\.toggle-group-health[^{]*\{[^}]*display:\s*none", html
        ), "toggle-group-health must be hidden by default"
        assert re.search(
            r'body\[data-view="health"\]\s*\.toggle-group-health'
            r'[^{]*\{[^}]*display:\s*flex',
            html,
        ), "toggle-group-health must be shown in the health view"

    def test_period_group_hidden_in_health_view(self):
        """Only one secondary group may be visible at a time. Period is the
        one group that is visible-by-default, so it still needs an explicit
        hide rule per view; the others are default-off."""
        assert re.search(
            r'body\[data-view="health"\][^{]*\.toggle-group-period'
            r'[^{]*\{[^}]*display:\s*none',
            _render(_ROADMAP),
        )


class TestCSSMatrix:
    def test_other_views_hidden_in_health(self):
        html = _render(_ROADMAP)
        for cls in ("team-only", "member-only", "queue-only", "recent-only"):
            assert re.search(
                rf'body\[data-view="health"\][^{{]*\.{cls}'
                rf'[^{{]*\{{[^}}]*display:\s*none',
                html,
            ), f".{cls} must be hidden in the health view"

    def test_health_only_hidden_everywhere_else(self):
        assert re.search(
            r'body:not\(\[data-view="health"\]\)\s*\.health-only'
            r'[^{]*\{[^}]*display:\s*none',
            _render(_ROADMAP),
        ), ".health-only must be hidden outside the health view"

    def test_roadmap_panel_hidden_when_performance_selected(self):
        assert re.search(
            r'body\[data-health="performance"\][^{]*\.roadmap-only'
            r'[^{]*\{[^}]*display:\s*none',
            _render(_ROADMAP),
        )


class TestGatingOnData:
    def test_button_hidden_when_no_roadmap_data(self):
        """gfx and webrtc get no roadmap payload, so the tab must remove
        itself rather than open an empty view."""
        html = _render(None)
        assert re.search(
            r'if\s*\(\s*!ROADMAP\s*\)', html
        ), "expected a `if (!ROADMAP)` guard hiding the health button"

    def test_roadmap_payload_is_null_without_data(self):
        assert re.search(r"const ROADMAP = null;", _render(None))

    def test_roadmap_payload_injected_when_present(self):
        html = _render(_ROADMAP)
        m = re.search(r"const ROADMAP = (\{.*?\});\n", html, re.DOTALL)
        assert m is not None, "ROADMAP payload not injected"
        assert json.loads(m.group(1).replace("\\u003c", "<"))["counts"]["total"] == 1

    def test_performance_button_hidden_until_that_data_exists(self):
        """The Performance subview is not built yet; its button hides on the
        same data-availability principle rather than shipping a dead tab."""
        assert re.search(r'if\s*\(\s*!PERF\s*\)', _render(_ROADMAP))


class TestHashRouting:
    def test_health_view_is_deep_linkable_with_its_subview(self):
        html = _render(_ROADMAP)
        assert re.search(r"setHealth", html), "health axis must be bound"
        assert "bindToggle('health')" in html


class TestRoadmapRendering:
    def test_renders_the_three_buckets(self):
        html = _render(_ROADMAP)
        for label in ("Ordered", "Need measuring", "Continuous"):
            assert label in html, f"missing bucket heading {label!r}"

    def _columns(self, html) -> list[str]:
        """The three bucket tables share one column definition in JS, so the
        header is generated rather than written three times in the markup."""
        m = re.search(r"const RM_COLS = \[(.*?)\];", html, re.DOTALL)
        assert m is not None, "RM_COLS column definition missing"
        return re.findall(r"\['([^']+)'", m.group(1))

    def test_all_three_tables_exist_with_a_generated_head(self):
        html = _render(_ROADMAP)
        for t in ("roadmap-ranked", "roadmap-measure", "roadmap-continuous"):
            assert re.search(rf'<table id="{t}">\s*<thead></thead>', html), (
                f"{t} should have its head generated from RM_COLS"
            )

    def test_reach_is_shown(self):
        """Reach is an input, not arithmetic. Score stays hidden; reach does
        not, because it is the most contested field and hiding it conceals
        which rows were ranked on a guess."""
        assert "Reach" in self._columns(_render(_ROADMAP))

    def test_score_is_not_shown(self):
        cols = self._columns(_render(_ROADMAP))
        assert "Score" not in cols and "Priority" not in cols, cols

    def test_expansion_colspan_is_derived_from_the_column_count(self):
        """Hardcoding it meant a 4th place to edit when a column changed."""
        assert "colspan=\"' + RM_COLS.length + '\"" in _render(_ROADMAP)

    def test_withheld_fields_are_marked_not_silently_dropped(self):
        html = _render(_ROADMAP)
        assert "withheld" in html, (
            "the public render must show that something was held back"
        )

    def test_audience_is_surfaced_on_the_page(self):
        """A reader should be able to tell whether they are looking at the
        public subset or the internal one."""
        assert "ROADMAP.audience" in _render(_ROADMAP)
