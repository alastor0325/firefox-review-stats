"""Tests for the sticky title + view-switcher layout.

Header and the 6-Month / Per-Week / Member Profile toggle live inside
one shared `.top-bar` element. That single element is sticky, so the
two children move as one unit and never jitter on scroll. The toggle's
top and bottom padding must be equal so the row of pills looks
balanced. These tests pin the rules so a future stylesheet edit can't
silently regress them.
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


def _extract_rule(html: str, selector: str) -> str:
    pattern = re.compile(re.escape(selector) + r"\s*\{([^}]+)\}", re.DOTALL)
    m = pattern.search(html)
    assert m is not None, f"CSS rule for {selector!r} not found"
    return m.group(1)


def _padding_top_bottom(rule: str) -> tuple[int, int]:
    """Return (top, bottom) from a `padding:` declaration in px.

    Handles 1-/2-/3-/4-value shorthand.
    """
    m = re.search(r"\bpadding:\s*([^;]+);", rule)
    assert m is not None, "no `padding:` declaration in rule"
    parts = [p.strip() for p in m.group(1).split()]
    nums = []
    for p in parts:
        n = re.match(r"(\d+)px", p)
        assert n is not None, f"non-px padding value {p!r}"
        nums.append(int(n.group(1)))
    if len(nums) == 1:
        return nums[0], nums[0]
    if len(nums) == 2:
        return nums[0], nums[0]
    if len(nums) == 3:
        return nums[0], nums[2]
    return nums[0], nums[2]


class TestStickyTopBar:
    """Header + toggle move as one unit, pinned from the first
    scroll pixel (no scroll-and-snap jump)."""

    def test_top_bar_exists_in_markup(self):
        html = render_html(_MINIMAL_DATA)
        assert 'class="top-bar"' in html, (
            "Header + toggle must be wrapped in a single .top-bar "
            "element so they pin together without independent jitter."
        )

    def test_top_bar_is_position_sticky(self):
        rule = _extract_rule(render_html(_MINIMAL_DATA), ".top-bar")
        assert re.search(r"position:\s*sticky", rule)

    def test_top_bar_pinned_at_top_zero(self):
        rule = _extract_rule(render_html(_MINIMAL_DATA), ".top-bar")
        assert re.search(r"\btop:\s*0\b", rule), (
            "top must be 0 so there is no gap-then-snap behaviour on scroll"
        )

    def test_top_bar_has_high_z_index(self):
        rule = _extract_rule(render_html(_MINIMAL_DATA), ".top-bar")
        m = re.search(r"z-index:\s*(\d+)", rule)
        assert m is not None
        assert int(m.group(1)) >= 10

    def test_top_bar_has_opaque_background(self):
        """Otherwise content scrolling underneath shows through the
        gaps between toggle pills."""
        rule = _extract_rule(render_html(_MINIMAL_DATA), ".top-bar")
        assert "background:" in rule


class TestToggleBarLayout:
    def test_toggle_bar_is_inside_top_bar(self):
        html = render_html(_MINIMAL_DATA)
        # Find the .top-bar block and assert the toggle is inside it.
        m = re.search(r'<div class="top-bar">(.*?)</div>\s*<main>',
                      html, re.DOTALL)
        assert m is not None, ".top-bar must wrap header + toggle, before <main>"
        assert 'class="toggle-bar"' in m.group(1), (
            ".toggle-bar must live inside .top-bar so the two stick together"
        )

    def test_toggle_bar_padding_top_equals_bottom(self):
        """The user can see when this is off — top and bottom space
        around the row of pills must match."""
        rule = _extract_rule(render_html(_MINIMAL_DATA), ".toggle-bar")
        top, bottom = _padding_top_bottom(rule)
        assert top == bottom, (
            f".toggle-bar padding asymmetric: top={top}px, bottom={bottom}px"
        )

    def test_toggle_bar_does_not_set_its_own_sticky(self):
        """If the toggle had its own `position: sticky`, it would
        compete with the wrapper and re-introduce the jitter."""
        rule = _extract_rule(render_html(_MINIMAL_DATA), ".toggle-bar")
        assert "position:" not in rule, (
            ".toggle-bar must inherit positioning from .top-bar; "
            "setting its own `position` re-introduces the scroll jump"
        )
