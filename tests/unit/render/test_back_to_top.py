"""Tests for the back-to-top button.

The button sits fixed bottom-right of the viewport and is shown
only when the user has scrolled past the top of <main>. It works
on every view (Team / Member / Wait Queue) because it lives
outside the view-switched containers.
"""

from reviewstats.render import render_html


_MINIMAL_DATA = {
    "meta": {"path": "dom/media", "group": "g", "excludes": [],
             "window_start": "2026-05-01", "window_end": "2026-05-15",
             "generated_at": "2026-05-15T00:00:00Z"},
    "summary": {"total_patches": 0, "group_tagged_patches": 0,
                "group_tagged_pct": 0,
                "landed_without_team_review": 0,
                "landed_without_team_review_pct": 0,
                "landed_without_team_review_by_subdir": {},
                "landed_without_team_review_list": [],
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


def test_button_lives_outside_view_switched_containers():
    """Putting the button after </main> guarantees it isn't hidden
    by any of the view-specific containers (team-only / member-only
    / queue-only)."""
    html = render_html(_MINIMAL_DATA)
    main_close = html.index("</main>")
    btn_index = html.index('id="back-to-top"')
    assert btn_index > main_close, (
        "Back-to-top button must be placed after </main> so it "
        "doesn't get hidden by any of the .*-only view containers."
    )


def test_top_sentinel_present_at_top_of_main():
    """An IntersectionObserver sentinel sits right after <main>'s
    open tag — when it leaves the viewport the button reveals."""
    html = render_html(_MINIMAL_DATA)
    main_open = html.index("<main>")
    sentinel_index = html.index('id="top-sentinel"')
    next_section = html.index("<!-- ============= TEAM /")
    assert main_open < sentinel_index < next_section, (
        "Sentinel must sit between <main>'s open tag and the first "
        "view section so visibility tracks scroll past <main>'s top."
    )


def test_button_uses_intersection_observer_for_visibility():
    """A scroll-event listener fires on every pixel of scroll;
    IntersectionObserver only fires on the threshold crossing. Pin
    the choice so a future cosmetic edit can't regress to the worse
    approach."""
    html = render_html(_MINIMAL_DATA)
    assert "new IntersectionObserver" in html
    assert "obs.observe(sentinel)" in html
    # And the visibility toggle uses the entry's `isIntersecting`.
    assert "!e.isIntersecting" in html


def test_button_is_hidden_by_default():
    """CSS must hide the button at first paint — the observer's
    initial callback will flip it on if needed. Without this, the
    button flashes in for a frame on every load."""
    html = render_html(_MINIMAL_DATA)
    # `visibility: hidden` + opacity 0 is the off-state pair.
    assert "#back-to-top {" in html
    assert "opacity: 0;" in html
    assert "visibility: hidden;" in html
    # The visible state is class-driven, not selector-cascade-driven.
    assert "#back-to-top.is-visible" in html


def test_button_smooth_scrolls_to_top_on_click():
    html = render_html(_MINIMAL_DATA)
    assert "window.scrollTo({ top: 0, behavior: 'smooth' });" in html
