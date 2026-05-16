"""Tests for the sticky header + toggle-bar layout.

We can't run a real browser layout test from a Python unit test, but
we can verify the rendered HTML contains the CSS rules that make
those elements sticky. If anyone accidentally removes them, these
tests will fail.
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
    """Return the CSS declarations inside the first rule for `selector`."""
    pattern = re.compile(
        re.escape(selector) + r"\s*\{([^}]+)\}",
        re.DOTALL,
    )
    m = pattern.search(html)
    assert m is not None, f"CSS rule for {selector!r} not found"
    return m.group(1)


class TestStickyHeader:
    def test_header_is_position_sticky(self):
        html = render_html(_MINIMAL_DATA)
        rule = _extract_rule(html, "header")
        assert re.search(r"position:\s*sticky", rule), (
            "header must use position: sticky so it pins to the top on scroll"
        )

    def test_header_top_zero(self):
        html = render_html(_MINIMAL_DATA)
        rule = _extract_rule(html, "header")
        assert re.search(r"\btop:\s*0\b", rule), (
            "header must stick at top: 0"
        )

    def test_header_has_high_z_index(self):
        html = render_html(_MINIMAL_DATA)
        rule = _extract_rule(html, "header")
        m = re.search(r"z-index:\s*(\d+)", rule)
        assert m is not None, "header needs z-index so it floats above content"
        assert int(m.group(1)) >= 10, "header z-index should be well above default"


class TestStickyToggleBar:
    def test_toggle_bar_is_position_sticky(self):
        html = render_html(_MINIMAL_DATA)
        rule = _extract_rule(html, ".toggle-bar")
        assert re.search(r"position:\s*sticky", rule), (
            ".toggle-bar must use position: sticky so the view-switcher "
            "is always reachable"
        )

    def test_toggle_bar_top_below_header(self):
        html = render_html(_MINIMAL_DATA)
        rule = _extract_rule(html, ".toggle-bar")
        m = re.search(r"\btop:\s*(\d+)px", rule)
        assert m is not None, ".toggle-bar must specify a `top:` offset"
        # Must be > 0 so it sits below the header rather than overlapping.
        assert int(m.group(1)) > 0, (
            ".toggle-bar top must be > 0 to clear the sticky header"
        )

    def test_toggle_bar_has_background(self):
        """Without a background, the sections scrolling underneath would
        bleed through the gaps between the pills."""
        html = render_html(_MINIMAL_DATA)
        rule = _extract_rule(html, ".toggle-bar")
        assert "background:" in rule, (
            ".toggle-bar needs an explicit background or content "
            "scrolls visibly behind the pills"
        )

    def test_toggle_bar_z_index_below_header(self):
        html = render_html(_MINIMAL_DATA)
        header_rule = _extract_rule(html, "header")
        toggle_rule = _extract_rule(html, ".toggle-bar")
        header_z = int(re.search(r"z-index:\s*(\d+)", header_rule).group(1))
        toggle_z = int(re.search(r"z-index:\s*(\d+)", toggle_rule).group(1))
        assert toggle_z < header_z, (
            "toggle-bar z-index must be below header so the header always "
            "overlaps the toggle bar's top edge"
        )
