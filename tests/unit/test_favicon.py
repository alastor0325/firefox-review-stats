"""Tests for the page favicon.

We embed the favicon as an inline SVG data URL so there's no
separate binary file to ship or cache in the workflow. The icon is
a rounded accent-blue square with a white play triangle — picked up
by the browser tab and by GitHub Pages' default page-preview crawl.
"""

from reviewstats.render import render_html


_MINIMAL_DATA = {
    "meta": {"path": "x", "group": "g", "excludes": [],
             "window_start": "2026-05-01", "window_end": "2026-05-15",
             "generated_at": "2026-05-15T00:00:00Z"},
    "summary": {"total_patches": 0, "group_tagged_patches": 0,
                "group_tagged_pct": 0,
                "landed_without_team_review": 0,
                "landed_without_team_review_pct": 0,
                "landed_without_team_review_by_subdir": {},
                "unique_individuals": 0, "avg_per_week": 0},
    "concentration": {"top1_share": 0, "top3_share": 0, "top5_share": 0,
                       "gini": 0, "bus_factor": 0},
    "within_group_total": [], "sole_reviewer": [],
    "total_reviews_per_member": [],
    "weekly_trend": {"weeks": [], "top_reviewers": [],
                      "all_members": {}, "authored_per_member": {}},
    "members": {}, "authors": {"top_total": [], "reviewer_matrix": {}},
    "per_member_authors": {}, "member_authored_counts": {},
}


def test_head_declares_inline_svg_favicon():
    html = render_html(_MINIMAL_DATA)
    assert '<link rel="icon" type="image/svg+xml"' in html, (
        "Page needs a favicon `<link>` in <head>; inline SVG avoids "
        "shipping a separate binary."
    )
    # data URL with the SVG payload — no external file fetch.
    assert "href=\"data:image/svg+xml;utf8," in html


def test_favicon_uses_mozilla_red():
    """The favicon should read as Mozilla-branded in a tab strip —
    pin to Mozilla's primary red (#FF0039)."""
    html = render_html(_MINIMAL_DATA)
    # %23FF0039 is `#FF0039` URL-encoded.
    assert "%23FF0039" in html


def test_favicon_carries_m_letterform():
    """A lowercase `m` inside the icon ties it back to the Mozilla
    wordmark style. Lock the letter so a future cosmetic tweak can't
    silently turn it back into a generic shape."""
    html = render_html(_MINIMAL_DATA)
    assert "text-anchor='middle'>m</text>" in html
