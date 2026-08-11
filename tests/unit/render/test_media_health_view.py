"""Tests for the Media Health view — a 5th view, playback only.

The view sits after Recent Changes on the `data-view` axis and carries its own
secondary axis, `data-health` ∈ {roadmap, metrics}, in the same top-bar
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
    "aspects": [{
        "name": "Playing ordinary video", "rating": "good", "text": "t",
        "rests_on": ["mkv-missing-formats"], "item_count": 1,
        "subs_withheld": 0,
        "sub": [
            {"name": "Format and codec coverage", "rating": "mixed",
             "text": "two kinds of hole", "depth": 1, "has_children": True,
             "rests_on": ["mkv-missing-formats"], "item_count": 1,
             "sub": [
                 {"name": "Container gaps", "rating": "mixed",
                  "text": "MKV refuses some codecs", "depth": 2,
                  "has_children": False,
                  "rests_on": ["mkv-missing-formats"], "item_count": 1,
                  "sub": []},
             ]},
            {"name": "Streaming protocols", "rating": "mixed", "depth": 1,
             "has_children": False, "text": "HLS is Android-only",
             "rests_on": [], "item_count": 0, "sub": []},
        ],
    }],
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


def _joined(html: str) -> str:
    """Collapse JS string concatenation so assertions can match logical text.

    The renderer builds prose with `'weaker ' + 'evidence'`, so a literal
    substring search for "weaker evidence" fails on working code. Several
    assertions in this file were written that way and failed for that reason
    alone; matching the outcome rather than the line-wrapping is the fix.
    """
    return re.sub(r"'\s*\+\s*'", "", html)


def _visible(html: str) -> str:
    """`_joined`, minus the JS comment lines.

    Assertions that a phrase is *absent* kept matching the comment explaining why
    it was removed -- the source says "removed the How to read this list", so
    searching for "How to read this" found it. Comments are not rendered, so an
    absence check has to ignore them.
    """
    return _joined("\n".join(
        ln for ln in html.splitlines() if not ln.strip().startswith("//")))


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
        for v in ("roadmap", "metrics"):
            assert re.search(rf'<button[^>]*data-health="{v}"', html), v

    def test_metrics_is_the_default_subview(self):
        """Metrics leads the Media Health tabs, so it is what `#health` opens."""
        m = re.search(r"<body[^>]*>", _render(_ROADMAP))
        assert 'data-health="metrics"' in m.group(0)

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

    def test_roadmap_panel_hidden_when_metrics_selected(self):
        assert re.search(
            r'body\[data-health="metrics"\][^{]*\.roadmap-only'
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

    def test_both_subviews_are_reachable(self):
        """Media Health has two subviews and both must be selectable. Neither
        is gated: Roadmap renders the items and Performance renders the
        metrics, and both come from the one roadmap payload."""
        html = _render(_ROADMAP)
        assert not re.search(r'if\s*\(\s*!PERF\s*\)', html), (
            "the Performance button must not be hidden — it has content"
        )
        assert "const PERF" not in html, (
            "no PERF gate: Performance is populated whenever ROADMAP is"
        )


class TestSubviewContentSplit:
    """Roadmap holds the item list; Performance holds the metrics. The metrics
    are the seam with the Raptor work, so they belong on the Performance side
    rather than buried at the bottom of the roadmap."""

    def _panel(self, html, cls):
        m = re.search(
            rf'<div class="health-only {cls}-only">(.*?)\n</div>',
            html, re.DOTALL,
        )
        assert m is not None, f"{cls} panel not found"
        return m.group(1)

    def test_metrics_panel_holds_the_cross_browser_charts(self):
        """The roadmap's TBD-target table used to live here and contradicted the
        measured coverage matrix on the same page — it claimed Safari on suites
        Safari has never run. Real Perfherder numbers replaced it."""
        panel = self._panel(_render(_ROADMAP), "metrics")
        assert 'id="pm-cards"' in panel
        assert 'id="roadmap-metrics"' not in panel

    def test_metrics_table_is_not_in_the_roadmap_panel(self):
        panel = self._panel(_render(_ROADMAP), "roadmap")
        assert 'id="roadmap-metrics"' not in panel

    def test_the_item_table_is_in_the_roadmap_panel(self):
        panel = self._panel(_render(_ROADMAP), "roadmap")
        assert 'id="roadmap-ranked"' in panel

    def test_item_tables_are_not_in_the_metrics_panel(self):
        panel = self._panel(_render(_ROADMAP), "metrics")
        assert 'id="roadmap-ranked"' not in panel

    def test_metrics_panel_has_no_placeholder_text(self):
        panel = self._panel(_render(_ROADMAP), "metrics")
        assert "Not built yet" not in panel


class TestHashRouting:
    def test_health_view_is_deep_linkable_with_its_subview(self):
        html = _render(_ROADMAP)
        assert re.search(r"setHealth", html), "health axis must be bound"
        assert "bindToggle('health')" in html


class TestRoadmapRendering:
    def test_renders_one_section_not_three(self):
        """`Continuous` is gone and `Need measuring first` is merged in. Three
        buckets asked a reader to hold three orderings at once, and the split
        leaked "can we rank this?" -- a fact about our evidence -- into a product
        view."""
        html = _visible(_render(_ROADMAP))
        assert "Ordered" in html
        for gone in ("Need measuring first", "<h2>Continuous</h2>"):
            assert gone not in html, f"{gone!r} is back"

    def _columns(self, html) -> list[str]:
        """The header is generated from one column definition in JS rather than
        written into the markup."""
        m = re.search(r"const RM_COLS = \[(.*?)\];", html, re.DOTALL)
        assert m is not None, "RM_COLS column definition missing"
        return re.findall(r"\['([^']+)'", m.group(1))

    def test_the_one_table_has_a_generated_head(self):
        html = _render(_ROADMAP)
        assert re.search(r'<table id="roadmap-ranked">\s*<thead></thead>', html)
        # The other two tables went with their sections. A table nobody fills is
        # the orphaned-container bug the runtime test exists to catch.
        for gone in ("roadmap-measure", "roadmap-continuous"):
            assert gone not in html, f"{gone} markup is back but nothing fills it"

    def test_reach_is_not_a_column(self):
        """Removed. It was a guess presented beside measured numbers, and it was
        what forced the bucket split: an unknown reach made an item unrankable.
        Every metric it fed is still TBD, so it was paying no rent."""
        assert "Reach" not in self._columns(_render(_ROADMAP))

    def test_an_unrankable_row_is_flagged_in_place(self):
        """The reader still needs to know where the order stops being
        evidence-backed."""
        html = _joined(_render(_ROADMAP))
        assert "needs measuring" in html
        assert "it.needs_measuring" in html

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


class TestAuthoredMatrixIsGone:
    """The roadmap's hand-authored container/codec grid used to render here. It is
    superseded by the measured probe (see TestMeasuredCaps): reading Chromium's
    codec list said Chrome plays PCM and AC-3 in Matroska, and shipping Chrome
    answers no to both.

    The `kind: matrix` support in the MODEL is still exercised in
    tests/unit/roadmap/test_roadmap.py — only the rendering was removed. Deleting
    the markup while leaving the JS that wrote to it is what caused the blank-page
    regression, so this asserts both halves are gone together.
    """

    def test_no_renderer_writes_to_the_removed_container(self):
        html = _render(_ROADMAP)
        assert "roadmap-matrices" not in html, (
            "the container and its renderer must be removed together"
        )

    def test_measured_caps_container_is_there_instead(self):
        assert 'id="pm-caps"' in _render(_ROADMAP)


class TestConditionTree:
    """The condition section is a single-column tree, not a card grid: three
    levels of nesting need horizontal room, and in a grid expanding one card
    resizes its row and shifts the unrelated card beside it."""

    def test_container_is_a_single_column_not_a_grid(self):
        html = _render(_ROADMAP)
        assert 'class="rm-aspects" id="roadmap-aspects"' in html, (
            "the aspect container must not ride on .summary-grid any more"
        )
        m = re.search(r"\.rm-aspects \{(.*?)\}", html, re.DOTALL)
        assert m is not None
        assert "display: block" in m.group(1), (
            "condition tree should be a single column"
        )

    def test_aspects_are_expandable_rows(self):
        html = _render(_ROADMAP)
        assert re.search(r"'<details class=\"rm-aspect ", html)

    def test_one_recursive_renderer_for_every_level_below_the_aspect(self):
        html = _render(_ROADMAP)
        assert "function renderNode(n)" in html
        assert re.search(r"n\.sub\.map\(renderNode\)", html), (
            "renderNode must recurse into its own children"
        )
        assert re.search(r"subs\.map\(renderNode\)", html), (
            "aspects must render their children through the same function"
        )

    def test_nodes_with_children_expand_leaves_do_not(self):
        html = _render(_ROADMAP)
        m = re.search(r"function renderNode\(n\) \{(.*?)\n  \}", html, re.DOTALL)
        assert m is not None
        body = m.group(1)
        assert "if (n.has_children)" in body
        assert "'<details class=\"rm-node " in body, "grouping nodes expand"
        assert "'<div class=\"rm-node " in body, "leaves are plain blocks"

    def test_indent_compounds_per_level(self):
        """Levels are DOM-nested, so a single margin rule produces the
        cumulative indent rather than one rule per depth."""
        html = _render(_ROADMAP)
        m = re.search(r"\.rm-node \{(.*?)\}", html, re.DOTALL)
        assert m is not None
        assert re.search(r"margin-left:\s*\d", m.group(1))
        assert "border-left" in m.group(1), "expected a spine per level"

    def test_elbow_and_rating_dot_are_separate_affordances(self):
        """The left border carries hierarchy, so the rating cannot also live
        there — it moves to a dot on the spine."""
        html = _render(_ROADMAP)
        assert re.search(r"\.rm-node::before \{", html), "elbow connector"
        assert re.search(r"\.rm-node::after \{", html), "rating dot"
        for rating in ("weak", "good"):
            assert re.search(rf"\.rm-node\.{rating}::after", html), rating

    def test_deeper_levels_are_visually_subordinate(self):
        html = _render(_ROADMAP)
        assert re.search(
            r"\.rm-node \.rm-node \.rm-node-h \{", html
        ), "level 3 headings should not read as peers of level 2"

    def test_items_render_with_their_severity(self):
        html = _render(_ROADMAP)
        assert "function itemChips(ids)" in html
        assert "it.impact" in html
        assert "itemById" in html

    def test_leaf_with_no_items_says_so(self):
        assert "nothing on the roadmap for this" in _render(_ROADMAP)

    def test_expandable_nodes_advertise_what_is_inside(self):
        html = _render(_ROADMAP)
        assert "rm-expand" in html
        assert "function insideLabel(n)" in html


class TestRatingColours:
    """A rating is shown in three places — the aspect's left stripe, the chip at
    every level, and the dot on the spine. All four states must be visually
    distinct in all three. The single-column rewrite silently dropped the stripe
    and left only `weak` coloured on the chip, so this is pinned."""

    RATINGS = ("good", "mixed", "weak", "unknown")

    def test_every_rating_has_a_token(self):
        html = _render(_ROADMAP)
        for r in self.RATINGS:
            assert re.search(rf"--rate-{r}:\s*#[0-9A-Fa-f]{{6}}", html), r

    def test_aspect_stripe_is_coloured_for_every_rating(self):
        html = _render(_ROADMAP)
        for r in self.RATINGS:
            assert re.search(
                rf"\.rm-aspect\.{r}\s*\{{[^}}]*border-left-color:\s*var\(--rate-{r}\)",
                html,
            ), f"aspect stripe missing colour for {r}"

    def test_rating_chip_is_coloured_for_every_rating(self):
        html = _render(_ROADMAP)
        for r in self.RATINGS:
            assert re.search(rf"\.{r}[^{{]*\.rm-rating[^{{]*\{{[^}}]*var\(--rate-{r}\)",
                             html), f"rating chip missing colour for {r}"

    def test_node_dot_is_coloured_for_every_rating(self):
        html = _render(_ROADMAP)
        for r in self.RATINGS:
            assert re.search(
                rf"\.rm-node\.{r}::after\s*\{{[^}}]*var\(--rate-{r}\)", html
            ), f"spine dot missing colour for {r}"

    def test_unknown_is_not_the_same_colour_as_mixed(self):
        """"We cannot answer this" is a different statement from "partly fine";
        colouring them identically hid the distinction."""
        html = _render(_ROADMAP)
        mixed = re.search(r"--rate-mixed:\s*(#[0-9A-Fa-f]{6})", html).group(1)
        unknown = re.search(r"--rate-unknown:\s*(#[0-9A-Fa-f]{6})", html).group(1)
        assert mixed.lower() != unknown.lower()

    def test_colours_are_not_duplicated_as_literals(self):
        """They were hardcoded in two places each, which is how the aspect level
        drifted out of sync in the first place."""
        html = _render(_ROADMAP)
        body = html.split(":root {", 1)[1]
        for literal in ("#C4890A", "#2E7D4F"):
            # Allowed once, in the token declaration block itself.
            assert body.count(literal) <= 1, f"{literal} duplicated"


class TestExpandAffordance:
    """A row that opens and a row that does not must never look alike. Two
    signals on expandable rows only — a chevron in the header and a line saying
    what is inside — and neither on a leaf, which shows its items instead."""

    def test_chevron_only_rendered_when_there_is_something_to_open(self):
        html = _render(_ROADMAP)
        assert "expandable ? ' <span class=\"rm-chev\">" in html, (
            "the chevron must be conditional on having children"
        )

    def test_chevron_rotates_when_open(self):
        html = _render(_ROADMAP)
        assert re.search(
            r"details\[open\] > summary \.rm-chev\s*\{[^}]*rotate", html
        ), "open state must be visible in the chevron"

    def test_chevron_responds_to_hover(self):
        assert re.search(r"summary:hover \.rm-chev\s*\{", _render(_ROADMAP)), (
            "hover should signal that the row is interactive"
        )

    def test_leaf_nodes_get_no_chevron(self):
        html = _render(_ROADMAP)
        assert "nodeHead(n, false)" in html, "leaves must be rendered non-expandable"

    def test_an_aspect_with_no_children_is_not_a_details(self):
        """Otherwise it would show a disclosure triangle that opens nothing."""
        html = _render(_ROADMAP)
        assert "if (!expandable)" in html
        assert "'<div class=\"rm-aspect '" in html

    def test_inside_label_pluralises(self):
        html = _render(_ROADMAP)
        assert "' sub-category'" in html and "' sub-categories'" in html
        assert "' item'" in html and "' items'" in html


class TestParityTailTags:
    _P = dict(
        _ROADMAP,
        aspects=[dict(_ROADMAP["aspects"][0], parity=["chrome", "safari"])],
    )

    def test_parity_tags_render_on_a_card(self):
        html = render_html(_MINIMAL_DATA, roadmap_data=self._P)
        assert "function parityTags(list, url)" in html
        assert "'parity-' + esc(e)" in html

    def test_no_tags_when_nothing_is_verified(self):
        """Absent parity means unverified, so rendering nothing is correct —
        an empty pill would read as a claim."""
        html = render_html(_MINIMAL_DATA, roadmap_data=self._P)
        assert "if (!list || !list.length) return '';" in html

    def test_tag_explains_itself_on_hover(self):
        html = render_html(_MINIMAL_DATA, roadmap_data=self._P)
        assert "ship this and we do not" in html

    def test_parity_tag_links_to_its_proof(self):
        html = render_html(_MINIMAL_DATA, roadmap_data=dict(
            _ROADMAP,
            aspects=[dict(_ROADMAP["aspects"][0], parity=["chrome"],
                          parity_url="https://webstatus.dev/features/x")],
        ))
        assert "a class=\"rm-parity\" href=" in html
        assert "target=\"_blank\"" in html and 'rel="noopener"' in html

    def test_clicking_the_link_does_not_toggle_the_card(self):
        """The tag sits inside a <summary>, so the click must not bubble into
        the disclosure or following a citation would collapse the card."""
        html = _render(_ROADMAP)
        assert "event.stopPropagation()" in html

    def test_parity_url_is_threaded_from_the_payload(self):
        html = _render(_ROADMAP)
        assert "parityTags(n.parity, n.parity_url)" in html

    def test_category_cards_never_render_a_parity_tag(self):
        """A category card covers several children but can only link to one
        proof, so a tag there would cite evidence for claims it does not
        support. Tags belong on the node that names the item."""
        html = _render(_ROADMAP)
        assert "parityTags(a.parity" not in html, (
            "the aspect header must not render parity tags"
        )


class TestMetricCards:
    """"Where Firefox stands" is a set of expandable cards grouped by category.
    Collapsed answers the comparison question; expanded shows the per-browser
    breakdown, the exact window and a link to the source series — so no number on
    the page has to be taken on trust."""

    def _js(self, html):
        m = re.search(r"function renderMetrics\(\) \{(.*?)\nrenderMetrics\(\);",
                      html, re.DOTALL)
        assert m is not None
        return m.group(1)

    def test_each_metric_is_an_expandable_card(self):
        js = self._js(_render(_ROADMAP))
        assert "function metricCard(m)" in js
        assert "'<details class=\"pm-card" in js

    def test_metrics_are_grouped_into_categories(self):
        js = self._js(_render(_ROADMAP))
        assert "pm-cat-h" in js
        assert "g.metrics.map(metricCard)" in js, (
            "a category renders its own metrics, keeping a family together"
        )

    def test_every_metric_links_to_its_source_series(self):
        js = self._js(_render(_ROADMAP))
        assert "m.graph_url" in js
        assert "open these exact series in Perfherder" in js

    def test_a_metric_with_no_signature_says_so_rather_than_linking(self):
        """A dead 'see the data' link is worse than none."""
        js = self._js(_render(_ROADMAP))
        assert "cannot link" in js

    def test_source_link_does_not_toggle_the_card(self):
        js = self._js(_render(_ROADMAP))
        assert "event.stopPropagation()" in js

    def test_warning_is_an_icon_with_detail_in_the_expansion(self):
        js = self._js(_render(_ROADMAP))
        assert "function warnIcon(m)" in js
        assert "expand for detail" in js
        assert "pm-facts" in js, "the window and staleness detail live in the body"

    def test_window_detail_is_in_the_expansion_not_the_row(self):
        js = self._js(_render(_ROADMAP))
        m = re.search(r"function metricCard\(m\) \{(.*?)\n  \}", js, re.DOTALL)
        assert m is not None
        body = m.group(1)
        assert "window'" in body or "-day window" in body
        assert "m.window_end" in body

    def test_categories_are_ordered_worst_first(self):
        js = self._js(_render(_ROADMAP))
        assert re.search(r"\.sort\(\(a, b\) => a\.worst - b\.worst\)", js)


class TestDirectionIsUnmissable:
    """Whether lower or higher is better must be readable without hunting. It was
    a clause in a small grey comma-list and a 0.05-opacity tint, which is how a
    reader ends up misreading a latency plot as a score plot."""

    def _js(self, html):
        m = re.search(r"function renderMetrics\(\) \{(.*?)\nrenderMetrics\(\);",
                      html, re.DOTALL)
        return m.group(1)

    def test_direction_is_stated_once_not_three_times(self):
        """It was in a category pill, on the axis label, and in the band inside
        the plot. One statement is clearer than three, and the band is the right
        one because it sits next to the marks it applies to."""
        js = self._js(_render(_ROADMAP))
        assert "pm-dir-pill" not in js, "the category pill was redundant"
        assert "better this way" in js, "the band is the single statement"

    def test_axis_label_still_carries_the_unit(self):
        """Dropping the direction phrase must not take the unit with it."""
        js = self._js(_render(_ROADMAP))
        assert "esc(m.unit)" in js

    def test_category_header_states_platform_and_unit(self):
        js = self._js(_render(_ROADMAP))
        assert "plat(g.platform)" in js
        assert "esc(g.unit)" in js

    def test_favourable_side_is_labelled_not_only_tinted(self):
        js = self._js(_render(_ROADMAP))
        assert "better this way" in js, (
            "the tinted half needs a label; a faint tint alone is inferable at "
            "best and invisible at worst"
        )
        assert "pm-band-in" in js

    def test_tint_is_actually_visible(self):
        html = _render(_ROADMAP)
        m = re.search(r"\.pm-track\.better-left::before[^}]*?opacity:\s*([\d.]+)",
                      html, re.DOTALL)
        assert m is not None, "favourable-half tint rule missing"
        assert float(m.group(1)) >= 0.08, (
            f"tint at {m.group(1)} is too faint to read"
        )

    def test_axis_unit_and_direction_are_not_muted(self):
        html = _render(_ROADMAP)
        js = self._js(html)
        assert 'pm-axis-dir strong' in js, "direction text must not be recessive"
        assert re.search(r"\.pm-axis-dir\.strong[^}]*color:\s*var\(--ink\)", html)

    def test_ruler_still_ascends_in_every_group(self):
        """Direction is annotated, never encoded by reversing the axis."""
        js = self._js(_render(_ROADMAP))
        assert re.search(r"\[0, 0\.25, 0\.5, 0\.75, 1\]\.map", js)
        assert "reverse()" not in js.split("const axis")[-1]


class TestMeasuredCaps:
    """Container-first: one card per container, three surface chips in the header,
    expanding to per-codec rows. Grouped by container because a container has a
    measured header (the probe asks the bare MIME type) and because disagreements
    are container-shaped -- WebKit implements no Matroska at all, which is one
    fact rather than twelve."""

    # Built by the real builder from probe-shaped input, not hand-written. The
    # hand-written version drifted the moment the surface keys were renamed --
    # every assertion still passed against a payload the generator could no
    # longer produce.
    @staticmethod
    def _caps_payload():
        from reviewstats.mediacaps import (
            SURFACES, build_api_table, build_conformance, build_container_view)

        def cmb(container, codec, kind, ff, cr, wk):
            """One probe combo per engine answer."""
            return (container, codec, kind, {"firefox-playwright": ff,
                                             "chrome": cr, "webkit": wk})

        spec = [
            # Matroska: a real gap, plus a row nobody supports.
            cmb("Matroska", "FLAC", "audio", "no", "yes", "no"),
            cmb("Matroska", "AC-3", "audio", "no", "no", "no"),
            cmb("Matroska", "VP9", "video", "yes", "yes", "no"),
            # WebM: verified parity, and both kinds so the split is exercised.
            cmb("WebM", "Opus", "audio", "yes", "yes", "yes"),
            cmb("WebM", "VP8", "video", "yes", "yes", "yes"),
        ]
        engines = [("firefox-playwright", "Firefox (Gecko build)", "153.0",
                    False, True),
                   ("chrome", "Chrome", "151", False, False),
                   ("webkit", "WebKit", "26.5", True, False)]
        results = []
        for target, label, version, proxy, nonship in engines:
            combos = []
            for container, codec, kind, answers in spec:
                v = answers[target]
                combos.append({
                    "container": container, "kind": kind, "codec": codec,
                    "codecString": codec.lower(),
                    "canPlayType": "probably" if v == "yes" else v,
                    "mse": v, "recorder": v,
                    "decodeFile": "yes+smooth+hw" if v == "yes" else v,
                    "decodeMse": v,
                })
            results.append({
                "target": target, "label": label, "browser_version": version,
                "is_proxy_for_safari": proxy, "is_nonshipping_build": nonship,
                "probedAt": "2026-08-10T12:00:00Z",
                "combos": combos,
                # HLS is container-level only -- no codec combinations exist.
                "bare": {"video/x-matroska": {"canPlayType": "maybe", "mse": v,
                                              "recorder": "no"},
                         "application/vnd.apple.mpegurl": {
                             "canPlayType": "no" if target.startswith("firefox")
                                            else "maybe",
                             "mse": "no", "recorder": "no"}},
                "conformance": [{
                    "type": 'audio/flac; codecs="ac-3"',
                    "canPlayType": "probably" if target.startswith("firefox")
                                   else "no"}],
                "apis": {"MediaSource in Worker": target != "webkit"},
            })
        return {
            "probed_at": "2026-08-10T12:00:00Z",
            "browsers": [{"target": t, "label": lb, "version": v,
                          "is_proxy_for_safari": p, "is_nonshipping_build": n}
                         for t, lb, v, p, n in engines],
            "surfaces": {},
            "by_container": build_container_view(results),
            "conformance": build_conformance(results),
            "apis": build_api_table(results),
        }

    def _render_caps(self):
        caps = dict(_ROADMAP, caps=self._caps_payload())
        return render_html(_MINIMAL_DATA, roadmap_data=caps)

    def test_grouped_by_container(self):
        html = self._render_caps()
        assert "pm-cont-h" in html
        assert "cv.containers.map" in html

    def test_every_probed_container_appears_even_at_full_support(self):
        """WebM used to vanish because all engines agree, which read as
        'forgotten' rather than 'measured and fine'."""
        html = self._render_caps()
        assert "LEVEL" in html
        assert "full support" in html

    def test_a_container_level_only_probe_says_so(self):
        """HLS has no codec combinations. Invisible is worse than labelled."""
        assert "container-level probe only" in self._render_caps()

    def test_three_surfaces_are_chips_not_separate_pages(self):
        html = self._render_caps()
        assert "pm-chips" in html and "function chips(c)" in html

    def test_chip_shows_a_ratio_not_a_bare_count(self):
        """0 of 5 is verified parity; 0 of 0 is nobody supports it. A bare zero
        merges two different facts."""
        html = self._render_caps()
        assert "st.counts.supported" in html
        assert "'/' + sup" in html

    def test_we_alone_accept_is_still_distinguishable_on_a_row(self):
        """It left the card badge -- which now reports coverage, a different
        question -- but it is still its own row colour, because it is not a gap
        and the fix is different: we are answering yes where nobody else does."""
        html = _joined(self._render_caps())
        assert "we accept it and no other engine does" in html
        assert "tr.pm-v-overclaim td:first-child" in html

    def test_the_conformance_section_is_not_rendered(self):
        """Removed from the dashboard on request. The check itself still runs in
        `tools/media-caps` and on the probe page, so the finding it produced --
        Firefox alone accepting three impossible type strings, because
        FlacDecoder::IsSupportedType never reads the codecs parameter -- is not
        lost, just no longer shown here."""
        html = _joined(self._render_caps())
        assert "combinations that cannot exist" not in html
        assert "Type that cannot exist" not in html

    def test_the_preamble_is_one_line_and_names_the_surfaces(self):
        """The "How to read this" list was removed a bullet at a time until only
        the surface names were left -- the one part a reader cannot infer from the
        cards. The heading went with the list rather than standing over one item.
        """
        html = _visible(self._render_caps())
        assert "How to read this" not in html
        assert "Three surfaces per container" in html
        for surface in ("Playback", "Streaming", "Recording"):
            assert surface in html, surface

    def test_the_badge_and_chip_are_no_longer_explained_in_prose(self):
        """Removed on request. They stay legible through the words themselves
        ("full support", "partial") and the cell tooltips."""
        html = _joined(self._render_caps())
        assert "what we support / what any engine supports" not in html
        assert "we match every engine" not in html

    def test_the_probe_date_is_stated_without_repeating_the_versions(self):
        html = _joined(self._render_caps())
        assert "Measured on" in html
        # The engine list sits immediately below; naming versions here said it
        # twice.
        assert "Measured on ' + esc((caps.probed_at || '').slice(0, 10)) + ' in" \
            not in html

    def test_surface_names_are_spelled_out(self):
        """"Play" and "Stream" were too terse to guess. The explanations are now
        one short line each on the column headers, so they name the API without
        spelling out "Media Source Extensions" in full."""
        html = _joined(self._render_caps())
        assert "MediaRecorder.isTypeSupported" in html
        assert "decodingInfo" in html
        assert "media-source" in html

    def test_rows_nobody_supports_are_not_listed_at_all(self):
        """Replaces an earlier rule that kept them in a collapsed table.

        A combination no browser supports is not a gap, not an overclaim and not
        a win, so there is nothing to act on, and the probe generates many of them
        because it asks every codec a container could plausibly carry. The count
        is still stated so the shorter table cannot be mistaken for full coverage.
        """
        html = _joined(self._render_caps())
        assert 'class="pm-none"' not in html, (
            "the collapsed no-engine-support table is back"
        )
        # No count line either: it was removed deliberately, so nothing on the
        # page should reintroduce a running tally of skipped rows.
        assert "not listed" not in html

    def test_video_and_audio_are_rendered_as_separate_groups(self):
        html = _joined(self._render_caps())
        assert "Video codecs" in html and "Audio codecs" in html

    def test_the_codec_index_is_not_rendered(self):
        """Removed on request. It restated the container tables codec-first --
        thirteen lines of "behind in 1 container: X" -- above the tables that
        already showed it. `build_container_view` still computes `codec_gaps`, so
        the codec-first question is still answerable from the data.
        """
        html = _joined(self._render_caps())
        assert "Codecs we lack, across containers" not in html
        assert "behind in " not in html

    def test_links_to_the_public_probe_page(self):
        html = self._render_caps()
        assert "media-capabilities/index.html" in html
        assert "Run the probe yourself" in html

    def test_evidence_strength_is_stated_per_engine(self):
        html = _joined(self._render_caps())
        assert "not Safari" in html and "weaker evidence" in html
        assert "not a shipping Firefox" in html

    def test_the_reason_for_measuring_is_stated(self):
        """So nobody reverts to reading source and repeats the mistake."""
        assert "PCM and AC-3" in self._render_caps()


class TestSupportAnswersAreWords:
    """Support answers are words, not a filled/half/empty glyph ramp.

    The glyph set needed a legend to decode and read as a severity ramp, which
    `maybe` is not: for a bare MIME type with no codecs parameter, `maybe` is the
    spec-correct answer — the browser cannot be certain without codec information.
    A half-full circle implied partial or degraded support instead.
    """

    def _caps_html(self):
        return _joined(render_html(_MINIMAL_DATA,
                                  roadmap_data=dict(
            _ROADMAP, caps=TestMeasuredCaps._caps_payload())))

    def test_no_partial_circle_glyph_anywhere(self):
        assert "◐" not in self._caps_html()

    def test_answers_render_as_words(self):
        html = self._caps_html()
        for word in ("'yes'", "'maybe'", "'no'"):
            assert word in html, word

    def test_the_answer_legend_is_not_rendered(self):
        """The yes/maybe/no/? legend was removed. The words are plain English and
        each cell keeps a tooltip, so `maybe` is still explained where it appears
        rather than in a standing paragraph under every card."""
        html = self._caps_html()
        assert "not partial support" not in html
        assert "the probe could not answer</p>" not in html

    def test_maybe_is_still_explained_on_the_cell_itself(self):
        html = self._caps_html()
        assert "no codecs parameter" in html, (
            "removing the legend must not remove the explanation entirely — "
            "`maybe` is the one answer a reader cannot guess"
        )


from tests.unit.roadmap.test_mediacaps import combo, result  # noqa: E402


class TestPerDeviceFactsAreNotPublished:
    """`powerEfficient` and `smooth` were rendered, then removed on purpose.

    Two reasons, either sufficient. It is not a hardware-decode flag -- Firefox
    and Chrome both report it for MP3, FLAC, Vorbis and AAC, and neither ships a
    hardware decoder for any of them. And it is **per device**: the answer comes
    from whatever machine ran the probe, so publishing it in a general
    cross-browser table invites reading "Firefox has hardware AV1 decode" off a
    fact about one laptop's GPU.

    The probe page still reports it, which is the right place for it -- a reader
    running it locally gets an answer about their own hardware. The dashboard is
    not that, so `hw-decode-matrix` still needs a real, per-configuration answer.
    """

    def _html(self):
        from reviewstats.render import render_html
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP))

    def test_no_efficiency_chip_is_rendered(self):
        html = self._html()
        assert 'class="pm-hw"' not in html
        assert ">efficient<" not in html

    def test_the_legend_does_not_mention_powerefficient(self):
        """Comment lines are stripped first: the source still explains *why* the
        flag is not shown, which is the opposite of showing it."""
        assert "powerEfficient" not in _visible(self._html())

    def test_the_page_makes_no_hardware_acceleration_claim(self):
        html = self._html()
        for phrase in ("hardware accelerated", "hardware-accelerated",
                       "hardware decode"):
            assert phrase not in html, (
                f'"{phrase}" appears — no measurement here supports it, and it '
                "would be a per-device claim in a general table"
            )

    def test_the_view_data_carries_no_per_device_fields(self):
        """Removed from the payload too, not just hidden in the template — a
        field in the JSON is a field someone renders later."""
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF",
                    [combo("MP4", "AV1", kind="video", canPlayType="probably",
                           decodeFile="yes+smooth+hw")])
        v = build_container_view([ff])
        rows = v["containers"][0]["surfaces"]["playback"]["rows"]
        assert rows, "fixture produced no rows"
        for r in rows:
            assert "eff" not in r and "smooth" not in r




class TestContainerHeaderAlignment:
    """Badge and chip columns line up down the list.

    Each card is its own `<details>`, so its header was its own CSS grid -- and
    `auto` columns only size against content *within* one grid. Every card
    therefore resolved different widths and the badges and chips came out ragged,
    which is most of the noise in a nine-card column.

    Fixed track widths are what makes independent grids agree, so these assert the
    tracks are fixed rather than content-sized.
    """

    def _css(self):
        import pathlib
        return pathlib.Path("templates/index.html.tmpl").read_text(
            encoding="utf-8")

    def _rule(self, selector):
        import re
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self._css())
        assert m, f"no rule for {selector}"
        return m.group(1)

    def test_the_header_grid_uses_fixed_tracks_not_auto(self):
        cols = self._rule(".pm-cont-h")
        assert "grid-template-columns" in cols
        line = [l for l in cols.split(";") if "grid-template-columns" in l][0]
        assert "auto" not in line, (
            "auto tracks size per-card, so nothing aligns between cards: " + line
        )
        assert "px" in line

    def test_the_chips_share_equal_columns(self):
        """One column per surface, equal width, or the chips drift by label and
        number width. Asserted against SURFACES so adding a surface without
        widening the grid fails here rather than on screen."""
        from reviewstats.mediacaps import SURFACES
        chips = self._rule(".pm-chips")
        assert f"repeat({len(SURFACES)}," in chips, (
            f"{len(SURFACES)} surfaces but the chip grid is: {chips.strip()}"
        )

    def test_the_badge_column_has_a_consistent_edge(self):
        assert "justify-self" in self._rule(".pm-badge-cell")


class TestCombinationCountReadsCorrectly:
    def test_a_single_combination_is_not_plural(self):
        """MP3 and WAV each have one, and both read "1 combinations".

        Asserted against the raw HTML, not `_joined`: that helper collapses string
        concatenation, which made an earlier version of this test pass against the
        unconditional `' combinations'` it was meant to catch.
        """
        html = render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP)
        assert "c.combos === 1" in html, (
            "the combination count is pluralised unconditionally"
        )
        assert "' combinations'" not in html, (
            "an unconditional plural is still in the template"
        )


class TestMetricsComesBeforeRoadmap:
    """Metrics is the first Media Health subview and the default.

    Order matters here beyond taste: the first tab is what a reader lands on, so
    the default (`data-health` on <body>, and the hash fallback) has to move with
    the button order or the page opens on a tab that is not the active one.
    """

    def _html(self):
        return render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP)

    def test_the_metrics_button_precedes_the_roadmap_button(self):
        """Scoped to the buttons: `data-health` also appears in CSS selectors
        earlier in the document, so a document-wide index comparison passed while
        Roadmap was still the first tab."""
        import re
        html = self._html()
        buttons = re.findall(r'<button data-health="(\w+)"', html)
        assert buttons[:2] == ["metrics", "roadmap"], buttons

    def test_metrics_is_the_button_marked_active(self):
        import re
        html = self._html()
        m = re.search(r'<button data-health="(\w+)" class="active"', html)
        assert m and m.group(1) == "metrics", (
            "the active class is on a tab that is no longer first"
        )

    def test_the_body_default_axis_is_metrics(self):
        assert 'data-health="metrics"' in self._html().split("<body")[1][:200]

    def test_the_hash_default_is_metrics(self):
        """`#health` with no subview must resolve to the tab that is shown."""
        html = self._html()
        assert "def: 'metrics'" in html, (
            "the deep-link default still points at Roadmap, so #health opens a "
            "different tab than the one highlighted"
        )


class TestSectionsRenderAsNestedColumns:
    """Two sections, browser-major, surfaces nested -- rendered, not just built."""

    def _html(self):
        caps = dict(_ROADMAP, caps=TestMeasuredCaps._caps_payload())
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=caps))

    def test_the_card_body_renders_sections_not_per_surface_tables(self):
        html = self._html()
        assert "sectionTable" in html
        assert "surfaceTable" not in html, "the old per-surface renderer is back"

    def test_the_browser_header_spans_its_surfaces(self):
        """A two-level header is the whole point: without colspan the browser
        names would sit above one column each and mislabel the rest."""
        assert 'colspan="' in self._html()

    def test_a_surface_with_no_engine_support_renders_a_dash(self):
        html = self._html()
        assert "no engine supports this" in html

    def test_the_surface_description_is_attached_to_its_column(self):
        html = self._html()
        assert "escA(sf.full)" in html

    def test_no_orphaned_surface_description_table_remains(self):
        """SURF_FULL described three surfaces and was left defined-but-unused when
        the sections took over; five surfaces meant it was also incomplete."""
        assert "SURF_FULL" not in self._html()


class TestOnlyThreeAnswersAreEverShown:
    """Cells read `yes`, `no`, or an em-dash. Never a question mark.

    A `?` appeared for FLAC and Vorbis under Chrome's WebCodecs, and it was not a
    fact about the codec: `AudioDecoder.isConfigSupported` throws
    "description is required" for those, so the probe recorded an error. The root
    cause is fixed by supplying a description -- with which all three engines
    answer yes, while `ac-3` and an invalid codec still answer no -- and this is
    the belt: even an unanswerable cell renders as a dash.
    """

    def _html(self):
        caps = dict(_ROADMAP, caps=TestMeasuredCaps._caps_payload())
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=caps))

    def test_no_question_mark_is_used_as_an_answer(self):
        html = self._html()
        assert "['?'," not in html and '"?",' not in html, (
            "a question mark is still a renderable answer"
        )

    def test_an_unanswerable_cell_renders_a_dash(self):
        """The template writes the dash as a JS escape, so match either form
        rather than only the literal glyph."""
        html = self._html()
        i = html.index("unknown: [")
        window = html[i:i + 60]
        assert ("\\u2013" in window or "–" in window), window

    def test_the_two_dash_cases_stay_distinguishable_in_the_tooltip(self):
        """Same glyph, different reasons: nobody supports it, versus we could not
        find out. Collapsing the words too would lose a real distinction."""
        html = self._html()
        assert "the probe could not answer" in html
        assert "no engine supports this" in html


class TestColumnHeadersExplainThemselves:
    """File / MSE / WC / Rec carry a hover explanation, on the page's own tooltip.

    They previously used a native `title`, which has a roughly one-second delay
    and no affordance -- easy to miss that an explanation exists at all. The
    dashboard already has a floating tooltip bound to `[data-tip]`; it was scoped
    to `.info` badges only, and a column header cannot become a badge because it
    has to keep its own text. So the binding is generalised rather than the header
    special-cased.
    """

    def _html(self):
        caps = dict(_ROADMAP, caps=TestMeasuredCaps._caps_payload())
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=caps))

    def test_the_tooltip_binding_is_not_limited_to_info_badges(self):
        assert "querySelectorAll('[data-tip]')" in self._html(), (
            "only .info elements get tooltips, so a header explanation never shows"
        )

    def test_sub_headers_use_the_page_tooltip_not_a_native_title(self):
        html = self._html()
        assert 'class="pm-sub" data-tip=' in html

    def test_a_hoverable_non_badge_shows_it_is_hoverable(self):
        assert "cursor: help" in self._html()

    def test_each_surface_explanation_is_one_short_line(self):
        from reviewstats.mediacaps import SECTIONS
        for spec in SECTIONS:
            for _key, label, full in spec["surfaces"]:
                assert full and len(full) <= 80, f"{label}: {len(full)} chars"
                assert "\\n" not in full


class TestProvenanceIsOnThePage:
    """The platform and any run warnings are visible, not just in the build log.

    Codec answers are platform-specific -- HEVC comes from VideoToolbox on macOS --
    so a matrix without its platform is unfalsifiable. And a matrix assembled from
    two runs or two machines is not a matrix; if that ever ships, the page has to
    say so rather than leaving it in a generator log nobody reads.
    """

    def _html(self):
        caps = dict(_ROADMAP, caps=TestMeasuredCaps._caps_payload())
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=caps))

    def test_the_platform_is_shown_next_to_the_date(self):
        assert "caps.platform" in self._html()

    def test_warnings_are_rendered_when_present(self):
        assert "caps.warnings" in self._html()

    def test_warnings_are_not_styled_as_ordinary_prose(self):
        """They mean the numbers are suspect; recessive grey would undersell it."""
        html = self._html()
        i = html.index("caps.warnings")
        assert "--rate-weak" in html[max(0, i - 300):i + 300]


class TestTheRatingIsShownWithItsReasoning:
    """Churn and Value replace Owner and Conf, and the reasoning travels with them.

    Measured across the items: Owner was empty on 30 of 39 rows and Conf read
    "high" on 32, so both were columns of one repeated value taking width from the
    only fields that vary. And since the rating is a judgement rather than a
    measurement, a column of levels with no reasoning behind it is just an
    assertion -- so each row's `rating_note` renders in the expansion.
    """

    def _html(self):
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP))

    def test_columns_are_churn_item_cost(self):
        import re
        html = render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP)
        m = re.search(r"const RM_COLS = \[(.*?)\];", html, re.DOTALL)
        cols = re.findall(r"\['([^']+)'", m.group(1))
        assert cols == ["Churn", "Item", "Cost"], cols

    def test_value_is_in_the_expansion_not_a_column(self):
        html = self._html()
        assert "value ' + esc(it.user_value)" in html

    def test_owner_and_conf_are_not_columns_any_more(self):
        import re
        html = render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP)
        m = re.search(r"const RM_COLS = \[(.*?)\];", html, re.DOTALL)
        assert "Owner" not in m.group(1) and "Conf" not in m.group(1)

    def test_owner_survives_in_the_expansion(self):
        """Removed from the table, not from the data -- in a tag list a blank
        simply does not appear."""
        assert "owner ' + ownerCell(it)" in self._html()

    def test_the_reasoning_renders(self):
        html = self._html()
        assert "Why this rating" in html
        assert "it.rating_note" in html

    def test_churn_levels_are_explained_on_hover(self):
        html = self._html()
        assert "switches browser" in html
        assert "Only developers notice" in html

    def test_a_quick_win_marker_exists(self):
        assert "quick win" in self._html()

    def test_bugzilla_severity_is_not_presented_as_the_anchor(self):
        """Explicitly our own judgement: Bugzilla severity is one reporter's triage
        of one bug, and most of these items have no bug at all."""
        assert "deliberately not Bugzilla" in self._html()


class TestThePublicBuildHasNoAudienceBanner:
    """The banner element is hidden in the public build, not merely emptied.

    Setting innerHTML to '' left the styled container rendering: a beige bar with a
    red left rule and no content in it. Removing text is not removing a banner.
    """

    def _html(self):
        return _joined(render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP))

    def test_the_element_is_hidden_not_just_emptied(self):
        html = self._html()
        assert "audienceEl.hidden = true" in html, (
            "the public build empties the banner without hiding it, leaving a "
            "styled empty bar"
        )

    def test_a_display_rule_backs_the_hidden_attribute(self):
        """A class with `background` and `padding` overrides `hidden` unless a
        display rule says otherwise."""
        assert ".rm-audience[hidden] { display: none }" in self._html()

    def test_the_internal_build_still_warns(self):
        """There the banner is a warning, not a disclosure: do not publish this."""
        html = self._html()
        assert "This build is not for the public site" in html
        assert "audienceEl.hidden = false" in html
