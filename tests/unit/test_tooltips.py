"""Tests for the info-icon tooltip feature in the rendered HTML template.

We can't fully test the JS-side positioning logic from Python, but we
can verify:
  1. The template emits info icons with `data-tip` attributes for every
     chart section heading we expect.
  2. The floating-tooltip container element + CSS class exist.
  3. The JS that attaches handlers (`attachTooltips`) is present.
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
}


def test_floating_tooltip_container_exists_in_template():
    html = render_html(_MINIMAL_DATA)
    assert "tip-floating" in html
    assert "attachTooltips" in html


def test_info_icons_on_section_headings():
    html = render_html(_MINIMAL_DATA)
    # Section headings that should have an info icon.
    expected_heading_substrings = [
        "Within-group distribution",
        "Sole-reviewer patches",
        "Total reviews per member",
        "Top patch authors",
        "Author &rarr; reviewer mapping",
        "Weekly trend",
    ]
    for snippet in expected_heading_substrings:
        # Find the line containing the heading; assert an info icon sits
        # near it (within the same heading element).
        pattern = re.compile(
            re.escape(snippet) + r".*?<span class=\"info\" data-tip=\"[^\"]+\"",
            re.DOTALL,
        )
        assert pattern.search(html), f"missing info icon for: {snippet}"


def test_info_icon_renders_with_data_tip_attribute():
    html = render_html(_MINIMAL_DATA)
    matches = re.findall(r'<span class="info" data-tip="([^"]+)"', html)
    # Expect at least a handful (section headings populate at template
    # parse time even when DATA is empty).
    assert len(matches) >= 6
    # Every data-tip should have non-trivial content.
    for tip in matches:
        assert len(tip) >= 10, f"trivial tip: {tip!r}"


def test_tip_floating_is_initially_hidden():
    html = render_html(_MINIMAL_DATA)
    # CSS rule for the floating tooltip should set display:none.
    assert re.search(r"\.tip-floating\b[^}]*display:\s*none", html)
