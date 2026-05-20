"""Tests for the per-team page header / navigation.

After M4-M6 each team's `<slug>/index.html` is generated from the
same template. The header text and the in-page title must derive
from the team's data, not a hardcoded 'dom/media' string. A small
back-link in the header takes the user up to the landing picker.
"""

from reviewstats.render import render_html


def _minimal_data(*, paths: list[str], group: str) -> dict:
    return {
        "meta": {
            "path": paths[0],
            "paths": paths,
            "group": group,
            "excludes": [],
            "window_start": "2026-05-01",
            "window_end": "2026-05-15",
            "generated_at": "2026-05-15T00:00:00Z",
        },
        "summary": {
            "total_patches": 0, "group_tagged_patches": 0,
            "group_tagged_pct": 0,
            "landed_without_team_review": 0,
            "landed_without_team_review_pct": 0,
            "landed_without_team_review_by_subdir": {},
            "landed_without_team_review_list": [],
            "unique_individuals": 0, "avg_per_week": 0,
        },
        "concentration": {
            "top1_share": 0, "top3_share": 0, "top5_share": 0,
            "gini": 0, "bus_factor": 0,
        },
        "within_group_total": [], "sole_reviewer": [],
        "total_reviews_per_member": [],
        "weekly_trend": {
            "weeks": [], "top_reviewers": [],
            "all_members": {}, "authored_per_member": {},
        },
        "members": {}, "authors": {"top_total": [], "reviewer_matrix": {}},
        "per_member_authors": {}, "member_authored_counts": {},
    }


def test_template_title_is_generic_and_filled_in_via_js():
    """The static <title> can't be team-specific because the same
    template is used for every team's page; JS sets the runtime
    title from meta. The static string just needs to be sensible
    while JS hasn't run yet."""
    html = render_html(_minimal_data(paths=["dom/media"], group="g"))
    # Static title is generic.
    assert "<title>Reviewer Load Dashboard</title>" in html
    # JS upgrades it to the team-specific form.
    assert "document.title = " in html


def test_h1_is_built_from_meta_paths_and_meta_group():
    """The visible H1 must show what paths the dashboard is
    monitoring + the review group, both pulled from meta. No
    hardcoded 'dom/media' from when the dashboard was playback-
    only."""
    html = render_html(_minimal_data(
        paths=["dom/media/webrtc", "dom/media/systemservices"],
        group="webrtc-reviewers",
    ))
    # The hardcoded 'dom/media Reviewer Load' string is gone.
    assert "dom/media Reviewer Load" not in html
    # Both halves of the H1 are JS-populated.
    assert "id=\"hdr-paths\"" in html
    assert "id=\"hdr-group\"" in html
    assert "hdr-paths').textContent =" in html


def test_header_has_back_link_to_landing_picker():
    """The user navigated *into* the team page from the landing
    picker; give them a clear path back. A tiny `←` in the header
    is enough — the landing page is one folder up."""
    html = render_html(_minimal_data(paths=["dom/media"], group="g"))
    assert 'href="../index.html"' in html
    assert "Back to team picker" in html
