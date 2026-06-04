"""Integration tests for the (view, period) two-axis toggle bar.

The toggle bar exposes two independent dimensions:

  * `data-view`   ∈ {team, member}
  * `data-period` ∈ {total, weekly}

So four combined states: team/total, team/weekly, member/total,
member/weekly. Each `<section>` is tagged with at most one class per
axis (`team-only`/`member-only`, `total-only`/`weekly-only`); sections
that span an axis omit the class.

These tests pin:

  * markup: 2 buttons per axis with the correct `data-*` attrs
  * CSS:    each `data-view`/`data-period` value has a hide rule for
            the opposite class
  * defaults: body starts at team / total
  * each axis is independent (changing one doesn't affect the other)
  * key sections are tagged for the right combination
"""

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


def _render() -> str:
    return render_html(_MINIMAL_DATA)


class TestToggleBarMarkup:
    def test_has_view_axis_buttons(self):
        html = _render()
        for v in ("team", "member", "queue", "recent"):
            assert re.search(rf'<button[^>]*data-view="{v}"', html), (
                f'expected a "{v}" view button'
            )

    def test_has_period_axis_buttons(self):
        html = _render()
        assert re.search(r'<button[^>]*data-period="total"', html), (
            'expected a "total" (6-month) period button'
        )
        assert re.search(r'<button[^>]*data-period="weekly"', html), (
            'expected a "weekly" period button'
        )

    def test_button_count_per_axis(self):
        html = _render()
        m = re.search(r'class="toggle-bar"(.*?)</nav>', html, re.DOTALL)
        assert m is not None, "toggle-bar nav missing"
        bar = m.group(1)
        view_buttons = re.findall(r'<button[^>]*data-view=', bar)
        period_buttons = re.findall(r'<button[^>]*data-period=', bar)
        assert len(view_buttons) == 4, (
            f"expected exactly 4 view buttons, found {len(view_buttons)}"
        )
        # Period axis: 6-Month (data-period="total") / 3-Month / 1-Month
        # / Per-Week. 1m and 3m were added alongside the windowed
        # `team_views` data so the user can drill in tighter than 6m.
        assert len(period_buttons) == 4, (
            f"expected exactly 4 period buttons, found {len(period_buttons)}"
        )
        for v in ("1m", "3m", "total", "weekly"):
            assert re.search(rf'<button[^>]*data-period="{v}"', bar), (
                f'expected a "{v}" period button'
            )

    def test_period_buttons_ordered_by_descending_span(self):
        """Period buttons read longest-window-first so the time axis is
        monotonic: 6-Month → 3-Month → 1-Month → Per-Week (per-week, the
        finest slice, sits last). Adding Per-Week after an ascending
        1/3/6 run read backwards."""
        html = _render()
        m = re.search(r'class="toggle-bar"(.*?)</nav>', html, re.DOTALL)
        assert m is not None, "toggle-bar nav missing"
        bar = m.group(1)
        order = re.findall(r'<button[^>]*data-period="([^"]+)"', bar)
        assert order == ["total", "3m", "1m", "weekly"], (
            f"period buttons should be 6m→3m→1m→weekly, got {order}"
        )


class TestDefaultState:
    def test_body_starts_team_total(self):
        html = _render()
        m = re.search(r'<body[^>]*>', html)
        assert m is not None
        body_tag = m.group(0)
        assert 'data-view="team"' in body_tag, (
            'default view must be "team"'
        )
        assert 'data-period="total"' in body_tag, (
            'default period must be "total" (6-month)'
        )

    def test_initial_active_buttons_match_default(self):
        html = _render()
        # First view button (team) is active by default.
        assert re.search(
            r'<button[^>]*data-view="team"[^>]*class="active"', html
        ), 'team button should be marked active at load'
        assert re.search(
            r'<button[^>]*data-period="total"[^>]*class="active"', html
        ), 'total (6-month) button should be marked active at load'


class TestCSSMatrix:
    def test_member_only_hidden_when_view_team(self):
        rule = re.search(
            r'body\[data-view="team"\][^{]*\.member-only[^{]*\{[^}]*display:\s*none',
            _render(),
        )
        assert rule, (
            "missing rule: body[data-view=team] .member-only { display: none }"
        )

    def test_team_only_hidden_when_view_member(self):
        rule = re.search(
            r'body\[data-view="member"\][^{]*\.team-only[^{]*\{[^}]*display:\s*none',
            _render(),
        )
        assert rule, (
            "missing rule: body[data-view=member] .team-only { display: none }"
        )

    def test_period_rules_are_scoped_to_team_view(self):
        """Period axis must only apply when view=team. Otherwise
        Member View would hide half its sections when the user happens
        to have a period selected."""
        html = _render()
        # `weekly-only` hide rule must include `data-view="team"`.
        weekly_rule = re.search(
            r'(body[^{]*\.weekly-only[^{]*\{[^}]*display:\s*none[^}]*\})',
            html,
        )
        assert weekly_rule is not None
        assert 'data-view="team"' in weekly_rule.group(0), (
            "weekly-only hide rule must be scoped to data-view=team"
        )
        # Same for total-only.
        total_rule = re.search(
            r'(body[^{]*\.total-only[^{]*\{[^}]*display:\s*none[^}]*\})',
            html,
        )
        assert total_rule is not None
        assert 'data-view="team"' in total_rule.group(0), (
            "total-only hide rule must be scoped to data-view=team"
        )

    def test_period_toggle_hidden_in_non_team_views(self):
        """The period buttons only apply in Team View; in Member and
        Wait Queue views the group is hidden to avoid confusing users."""
        html = _render()
        for v in ("member", "queue"):
            rule = re.search(
                rf'body\[data-view="{v}"\][^{{]*\.toggle-group-period[^{{]*\{{[^}}]*display:\s*none',
                html,
            )
            assert rule, (
                f"missing rule: body[data-view={v}] .toggle-group-period "
                "{ display: none }"
            )

    def test_queue_only_hidden_in_other_views(self):
        html = _render()
        for v in ("team", "member"):
            rule = re.search(
                rf'body\[data-view="{v}"\][^{{]*\.queue-only[^{{]*\{{[^}}]*display:\s*none',
                html,
            )
            assert rule, (
                f"missing rule: body[data-view={v}] .queue-only { '{' } display: none { '}' }"
            )

    def test_team_and_member_only_hidden_in_queue_view(self):
        html = _render()
        for cls in (".team-only", ".member-only"):
            rule = re.search(
                rf'body\[data-view="queue"\][^{{]*{re.escape(cls)}[^{{]*\{{[^}}]*display:\s*none',
                html,
            )
            assert rule, (
                f"missing rule: body[data-view=queue] {cls} {{ display: none }}"
            )

    def test_period_toggle_group_marked_for_targeting(self):
        """The CSS hide rule relies on the period group having the
        `.toggle-group-period` class. Verify the markup carries it."""
        html = _render()
        assert 'class="toggle-group toggle-group-period"' in html or \
               'class="toggle-group-period toggle-group"' in html, (
            "Period <div class=toggle-group> must also have "
            "`toggle-group-period` so the CSS can hide it in Member View."
        )


class TestSectionTagging:
    def test_team_6month_sections_tagged(self):
        html = _render()
        # The 6-month team content (concentration, distribution, top authors, etc.)
        # should sit inside a `team-only total-only` container.
        assert re.search(
            r'class="team-only total-only"', html
        ), "expected a `.team-only.total-only` container for Team / 6-Month"

    def test_team_perweek_sections_tagged(self):
        html = _render()
        assert re.search(
            r'class="team-only weekly-only"', html
        ), "expected a `.team-only.weekly-only` container for Team / Per-Week"

    def test_member_6month_sections_tagged(self):
        html = _render()
        assert re.search(
            r'class="member-only total-only"', html
        ), "expected a `.member-only.total-only` container for Member / 6-Month"

    def test_member_perweek_sections_tagged(self):
        html = _render()
        assert re.search(
            r'class="member-only weekly-only"', html
        ), "expected a `.member-only.weekly-only` container for Member / Per-Week"

    def test_member_dropdown_only_in_member_view(self):
        """Shared across both Member sub-views (any period), so tagged
        `member-only` without a period qualifier."""
        html = _render()
        # The <select id="profile-member"> must sit inside a member-only
        # container that has NO total-only or weekly-only.
        m = re.search(
            r'<section[^>]*class="member-only"[^>]*>([^<]|<(?!/section>))*'
            r'<select[^>]*id="profile-member"',
            html, re.DOTALL,
        )
        assert m is not None, (
            "Member dropdown should be in a `.member-only` section "
            "(without a period qualifier) so it's visible across both "
            "Member sub-views."
        )


class TestWaitQueueView:
    def test_queue_section_present(self):
        html = _render()
        assert re.search(r'class="queue-only"', html), (
            'expected a `.queue-only` section for the Wait Queue view'
        )

    def test_queue_table_columns_in_order(self):
        """No # column, no Revision column (title is the link now).
        Time-to-react and Time-to-accept come first."""
        html = _render()
        assert 'id="queue-table"' in html, "queue table id missing"
        # Extract the queue table specifically (not other tables on the page).
        m = re.search(
            r'<table id="queue-table".*?</thead>', html, re.DOTALL,
        )
        assert m is not None
        thead = m.group(0)
        # The columns in order:
        headers_in_order = re.findall(r'<th[^>]*>([^<]+)</th>', thead)
        # Strip whitespace, drop any blank captures.
        headers_in_order = [h.strip() for h in headers_in_order if h.strip()]
        assert headers_in_order[:5] == [
            "Time to react", "Time to accept", "Title", "Author", "Accepted by",
        ], f"unexpected column order: {headers_in_order}"

    def test_queue_table_omits_rank_and_revision_columns(self):
        html = _render()
        m = re.search(
            r'<table id="queue-table".*?</thead>', html, re.DOTALL,
        )
        assert m is not None
        thead = m.group(0)
        headers = re.findall(r'<th[^>]*>([^<]+)</th>', thead)
        text = " ".join(h.strip() for h in headers)
        assert "Revision" not in text, "Revision column should be gone"
        # The "#" rank header has been removed too.
        assert not re.search(r'>\s*#\s*<', thead), "# column should be gone"

    def test_queue_time_columns_are_sortable(self):
        html = _render()
        m = re.search(
            r'<table id="queue-table".*?</thead>', html, re.DOTALL,
        )
        assert m is not None
        thead = m.group(0)
        # Both time columns must carry `sortable` class + `data-sort` attr
        # pointing at the right field name.
        assert re.search(
            r'<th[^>]*class="sortable num"[^>]*data-sort="time_to_react_days"',
            thead,
        ), "Time-to-react header should be sortable"
        assert re.search(
            r'<th[^>]*class="sortable num"[^>]*data-sort="time_to_accept_days"',
            thead,
        ), "Time-to-accept header should be sortable"

    def test_queue_renderer_consumes_patch_list(self):
        html = _render()
        assert "PHAB_DATA.patch_list" in html, (
            "queue renderer should read from PHAB_DATA.patch_list"
        )

    def test_queue_renderer_supports_dynamic_sort(self):
        """The JS render function must accept a sort key argument so
        click handlers can re-sort without rebuilding from scratch."""
        html = _render()
        assert re.search(r"function render\(sortKey\)", html), (
            "queue render should be parameterised by sortKey"
        )

    def test_queue_table_layout_is_responsive(self):
        """Section box was bleeding because the table outgrew its
        container. Lock layout with `table-layout: fixed` AND wrap in
        a horizontal-scroll container so narrow viewports degrade
        gracefully."""
        html = _render()
        assert "table-layout: fixed" in html, (
            "tables should use fixed layout so columns honour widths"
        )
        assert "table-wrap" in html, (
            "queue table should be wrapped in a `.table-wrap` (overflow-x: auto) "
            "so narrow viewports scroll the table, not the section"
        )


class TestAxisIndependence:
    """The two axes change state independently; a `setMode` helper
    shouldn't reset the other axis when toggled. The toggle JS
    indexes by `data-axis` and never touches the other axis's state."""

    def test_toggle_js_handles_each_axis_independently(self):
        html = _render()
        # The bindToggle/setMode JS must reference both axes separately.
        assert "bindToggle('view')" in html
        assert "bindToggle('period')" in html

    def test_setmode_only_updates_one_axis(self):
        html = _render()
        # The handler `set(value)` only assigns `document.body.dataset[axis]`,
        # not both. Look for the dataset assignment pattern.
        assert re.search(
            r"document\.body\.dataset\[axis\]\s*=\s*value", html
        ), "toggle should update one axis at a time (dataset[axis] = value)"
