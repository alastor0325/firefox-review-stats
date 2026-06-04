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
    assert "<title>Team Dashboard</title>" in html
    # JS upgrades it to the team-specific form.
    assert "document.title = " in html


def test_h1_shows_group_only_paths_live_in_subtitle():
    """The H1 reads 'Team Dashboard — <group>' — short and stable
    across multi-path teams. The paths line lives in the meta
    subtitle below, so repeating them in the H1 would be redundant
    and hard to read when a team owns several roots."""
    html = render_html(_minimal_data(
        paths=["dom/media/webrtc", "dom/media/systemservices"],
        group="webrtc-reviewers",
    ))
    # No hardcoded path string in the H1 anywhere.
    assert "dom/media Team Dashboard" not in html
    # The group half is JS-populated; the paths half no longer
    # appears inside the H1.
    assert "id=\"header-group\"" in html
    assert "id=\"header-paths\"" not in html, (
        "Paths shouldn't appear in the H1 — they live in the "
        "subtitle (header-meta) only."
    )
    # The 'hdr-' prefix used to live here and is genuinely ambiguous
    # in a media/graphics dashboard (reads as 'High Dynamic Range').
    # Pin the rename so a future revert doesn't quietly bring back
    # the misleading abbreviation.
    assert "hdr-group" not in html
    assert "hdr-meta" not in html
    # The static H1 text leads with the team-agnostic 'Team Dashboard',
    # then a decorative separator, then the JS-populated group span.
    # The separator glyph is a presentation detail — pinning the literal
    # em-dash was too brittle when the editorial redesign swapped in a
    # serif middle-dot — so just assert order and ID presence.
    import re
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    assert h1_match is not None, "no <h1> in rendered page"
    h1 = h1_match.group(1)
    assert "Team Dashboard" in h1
    assert 'id="header-group"' in h1
    assert h1.index("Team Dashboard") < h1.index('id="header-group"')


def test_title_links_to_repo():
    """The 'Team Dashboard' title links to the GitHub repo (opens in a new
    tab), styled to still read as the heading rather than the back-arrow."""
    import re
    html = render_html(_minimal_data(paths=["dom/media"], group="g"))
    m = re.search(
        r'<a href="(https://github\.com/[^"]+)"[^>]*class="dash-title"[^>]*>Team Dashboard</a>',
        html,
    )
    assert m, "title should be an <a class=dash-title> pointing at the GitHub repo"
    assert 'target="_blank"' in m.group(0) and "noopener" in m.group(0)


def test_header_has_back_link_to_landing_picker():
    """The user navigated *into* the team page from the landing
    picker; give them a clear path back. A tiny `←` in the header
    is enough — the landing page is one folder up."""
    html = render_html(_minimal_data(paths=["dom/media"], group="g"))
    assert 'href="../index.html"' in html
    assert "Back to team picker" in html
