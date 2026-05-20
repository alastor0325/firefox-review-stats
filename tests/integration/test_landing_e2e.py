"""End-to-end integration test for the landing page.

`test_landing.py` (unit) checks markup structure with synthesised
teams. This test renders the actual `TEAMS` registry through
`render_landing_page` and verifies every registered team gets a
working card with the right href, paths, and roster size — picking
up future additions to the registry automatically.
"""

import re

from reviewstats.landing import render_landing_page
from reviewstats.teams import PLAYBACK_TEAM, TEAMS


def test_landing_renders_card_for_every_registered_team():
    html = render_landing_page(list(TEAMS.values()))
    for slug in TEAMS:
        assert f'href="{slug}/index.html"' in html, (
            f"Landing page has no card for {slug!r}"
        )


def test_each_card_shows_correct_paths():
    html = render_landing_page(list(TEAMS.values()))
    for team in TEAMS.values():
        # Each card displays the team's paths as a comma-separated
        # monospace line — the user can size-up scope at a glance.
        assert ", ".join(team.paths) in html or team.paths[0] in html, (
            f"Landing page didn't render paths for {team.slug!r}"
        )


def test_each_card_shows_roster_size():
    html = render_landing_page(list(TEAMS.values()))
    for team in TEAMS.values():
        n = len(team.members)
        plural = "s" if n != 1 else ""
        assert f"{n} listed reviewer{plural}" in html, (
            f"Landing page didn't render roster size for {team.slug!r} "
            f"(expected {n})"
        )


def test_playback_card_carries_default_badge_and_others_do_not():
    """Only the playback card gets the 'Default' badge — verified by
    confirming the badge sits inside the playback card and outside
    every other card."""
    html = render_landing_page(list(TEAMS.values()))
    # Build a rough index of where each card lives in the page.
    card_re = re.compile(r'<a class="team-card" href="([^"]+)".*?</a>',
                          re.DOTALL)
    card_spans: list[tuple[str, int, int]] = []
    for m in card_re.finditer(html):
        card_spans.append((m.group(1), m.start(), m.end()))
    for href, start, end in card_spans:
        chunk = html[start:end]
        if href.startswith(f"{PLAYBACK_TEAM.slug}/"):
            assert "Default" in chunk, "Playback card missing Default badge"
        else:
            assert "Default" not in chunk, (
                f"Card for {href!r} should not carry the Default badge"
            )


def test_cards_link_resolves_to_real_per_team_index_html():
    """Each landing href points to '<slug>/index.html' which is the
    file analyze_git.py actually emits. Confirms the two halves of
    the layout agree on naming."""
    html = render_landing_page(list(TEAMS.values()))
    # We can't actually fetch the per-team index here (it lives on
    # disk), but the href shape must match the per-team output path
    # convention. analyze_git writes to <out>/<slug>/index.html, so
    # the relative href used in the landing must be '<slug>/index.html'.
    for team in TEAMS.values():
        assert f'href="{team.slug}/index.html"' in html
