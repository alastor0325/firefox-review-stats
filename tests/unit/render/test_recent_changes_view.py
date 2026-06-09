"""Render tests for the Recent Changes view (markup, CSS, JS wiring).

The data-driven content is built and tested in report/recent_changes
unit tests; here we pin the template scaffolding the JS depends on.
"""

import re

from reviewstats.render import render_html


_DATA = {
    "meta": {"path": "dom/media", "group": "g", "window_start": "2025-12-03",
             "window_end": "2026-06-03", "generated_at": "2026-06-03T00:00:00Z"},
    "summary": {
        "total_patches": 0, "group_tagged_patches": 0, "group_tagged_pct": 0,
        "unique_individuals": 0, "avg_per_week": 0,
        "landed_without_team_review": 0, "landed_without_team_review_pct": 0,
        "landed_without_team_review_by_subdir": {},
        "landed_without_team_review_list": [],
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
    "recent_changes": {
        "1w": {"window_start": "2026-05-27", "window_end": "2026-06-03",
               "total": 1, "features": [
                   {"feature": "eme", "label": "Encrypted Media (EME / DRM)",
                    "count": 1, "summary": "Reworked CDM shutdown handling.",
                    "patches": [
                        {"date": "2026-06-01", "author": "Tester",
                         "subject": "x.", "sha": "abc",
                         "short_sha": "abc", "differential_revision": "D5",
                         "bug": "1"}]}]},
        "1m": {"window_start": "2026-05-04", "window_end": "2026-06-03",
               "total": 1, "features": [
                   {"feature": "eme", "label": "Encrypted Media (EME / DRM)",
                    "count": 1, "patches": [
                        {"date": "2026-06-01", "author": "Tester",
                         "subject": "x.", "sha": "abc",
                         "short_sha": "abc", "differential_revision": "D5",
                         "bug": "1"}]}]},
    },
}


def _render(data=_DATA) -> str:
    return render_html(data)


class TestRecentMarkup:
    def test_view_button_present(self):
        assert re.search(r'<button[^>]*data-view="recent"', _render())

    def test_recent_only_section_present(self):
        assert re.search(r'class="recent-only"', _render())

    def test_container_present(self):
        assert 'id="recent-changes-container"' in _render()

    def test_window_toggle_buttons_in_top_bar(self):
        # The week/month switch is the top-bar `data-recent` group — the
        # same toggle component the Team-View period axis uses.
        html = _render()
        m = re.search(r'class="toggle-bar"(.*?)</nav>', html, re.DOTALL)
        assert m, "toggle-bar nav missing"
        bar = m.group(1)
        assert 'toggle-group-recent' in bar
        for w in ("1w", "1m"):
            assert re.search(rf'<button[^>]*data-recent="{w}"', bar), (
                f'expected a "{w}" recent-window button in the toggle bar'
            )

    def test_week_is_default_active(self):
        # This Week is the default selection when the tab opens.
        assert re.search(
            r'<button[^>]*data-recent="1w"[^>]*class="active"', _render()
        ), "This Week button should be active by default"
        assert re.search(r'<body[^>]*data-recent="1w"', _render()), (
            "body should default data-recent to 1w"
        )


class TestRecentCSS:
    def test_other_views_hidden_in_recent(self):
        html = _render()
        for cls in (".team-only", ".member-only", ".queue-only"):
            rule = re.search(
                rf'body\[data-view="recent"\][^{{]*{re.escape(cls)}[^{{]*\{{[^}}]*display:\s*none',
                html,
            )
            assert rule, f"missing rule hiding {cls} in recent view"

    def test_recent_only_hidden_outside_recent(self):
        html = _render()
        rule = re.search(
            r'body:not\(\[data-view="recent"\]\)[^{]*\.recent-only[^{]*\{[^}]*display:\s*none',
            html,
        )
        assert rule, "recent-only must be hidden when view != recent"

    def test_period_toggle_hidden_in_recent(self):
        html = _render()
        rule = re.search(
            r'body\[data-view="recent"\][^{]*\.toggle-group-period[^{]*\{[^}]*display:\s*none',
            html,
        )
        assert rule, "period toggle should be hidden in recent view"

    def test_recent_toggle_shown_only_in_recent(self):
        html = _render()
        # Hidden by default…
        assert re.search(r'\.toggle-group-recent[^{]*\{[^}]*display:\s*none', html), (
            "recent-window toggle should be hidden outside the recent view"
        )
        # …and shown in the recent view.
        assert re.search(
            r'body\[data-view="recent"\][^{]*\.toggle-group-recent[^{]*\{[^}]*display:\s*flex',
            html,
        ), "recent-window toggle should be shown in the recent view"


class TestRecentJS:
    def test_reads_recent_changes(self):
        assert "DATA.recent_changes" in _render()

    def test_legacy_guard_hides_button(self):
        # When a report lacks recent_changes, the button is hidden.
        html = _render()
        assert re.search(r'if \(!RECENT\)', html), (
            "expected a legacy guard hiding the recent button when no data"
        )

    def test_builds_phabricator_link(self):
        assert "phabricator.services.mozilla.com" in _render()

    def test_change_list_collapsed_by_default(self):
        # The detailed change list sits in a <details class="changes-toggle">
        # that is NOT opened by JS — collapsed by default.
        html = _render()
        assert "changes-toggle" in html
        assert "createElement('details')" in html
        assert "block.open = true" not in html, (
            "the change list should be collapsed by default"
        )
        assert "`Show ${group.count} patch" in html, (
            "expected a 'Show N patches' toggle"
        )

    def test_count_shows_fraction_and_percent(self):
        html = _render()
        assert "group.count}/${win.total}" in html, (
            "count badge should show this-area / window-total"
        )
        assert "Math.round(group.count / win.total * 100)" in html, (
            "count badge should include a percentage of the window total"
        )

    def test_renders_feature_overview_when_present(self):
        html = _render()
        assert "group.summary" in html, (
            "JS should render each feature area's plain-language overview"
        )

    def test_overview_supports_emphasis_markup(self):
        # Overview text is escaped first, then `code` / **bold** / _italic_ markup
        # is converted to <code>/<strong>/<em> — so the summary can carry emphasis
        # (and code spans) without allowing raw HTML injection.
        html = _render()
        assert "renderEmphasis" in html
        assert r"<strong>$1</strong>" in html
        # code spans are split out and wrapped so identifiers like `MOZ_LOG_FMT`
        # render verbatim (and are never emphasized internally).
        assert "(`[^`]+`)" in html, "overview must handle inline `code` spans"
        assert "<code>" in html
        # underscore-italic must be intraword-safe: the rule requires a non-alnum
        # boundary around the underscores, so MOZ_LOG_FMT is NOT italicized.
        assert "[^A-Za-z0-9])_" in html, (
            "underscore-italic must be boundary-anchored, not bare /_(.+?)_/"
        )
        assert r"<em>$2</em>" in html
        assert "renderEmphasis(group.summary)" in html, (
            "overview should be rendered through the emphasis converter"
        )

    def test_defaults_to_week(self):
        # Initial render reads the body's default window (This Week).
        assert "render(document.body.dataset.recent || '1w')" in _render()

    def test_recent_toggle_driven_by_bindtoggle(self):
        # The week/month switch reuses the shared toggle component, not a
        # bespoke handler: bindToggle('recent') wires it.
        html = _render()
        assert "bindToggle('recent')" in html
        assert "renderRecentWindow" in html

    def test_change_toggle_css_is_foldable(self):
        html = _render()
        assert re.search(r'\.changes-toggle\[open\]', html), (
            "expected open-state CSS for the collapsible change list"
        )

    def test_render_with_missing_recent_changes_is_safe(self):
        # No recent_changes key → RECENT is null, setup bails, no crash
        # in render (smoke: HTML still produced).
        data = {k: v for k, v in _DATA.items() if k != "recent_changes"}
        html = _render(data)
        assert "const RECENT = DATA.recent_changes || null;" in html
