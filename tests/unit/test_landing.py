"""Tests for the root landing page.

Multi-team layout puts each team in `<slug>/index.html`. The site
root (`/index.html`) is a small picker that lists every registered
team as a card. Playback is marked as the default so a first-time
visitor knows where to land.
"""

from dataclasses import replace

from reviewstats.landing import render_landing_page
from reviewstats.teams import PLAYBACK_TEAM, TEAMS


def _hypothetical_team():
    """Build a second team value object on the fly for tests so we
    can verify multi-team rendering without depending on whatever's
    in `TEAMS` at the time the test runs."""
    return replace(
        PLAYBACK_TEAM,
        slug="example",
        display_name="example-reviewers",
        group="example-reviewers",
        paths=("dom/example",),
        members={"alice": "Alice A", "bob": "Bob B"},
    )


def test_landing_page_renders_for_single_team():
    html = render_landing_page([PLAYBACK_TEAM])
    # Each team renders as a clickable card linking to /<slug>/.
    assert 'href="playback/index.html"' in html
    assert ">media-playback-reviewers<" in html


def test_landing_page_renders_each_team_as_a_card():
    teams = [PLAYBACK_TEAM, _hypothetical_team()]
    html = render_landing_page(teams)
    assert 'href="playback/index.html"' in html
    assert 'href="example/index.html"' in html
    # Each team card shows the paths so the user can tell at a
    # glance which one they want.
    assert "dom/media" in html
    assert "dom/example" in html


def test_landing_page_marks_playback_as_default():
    """Playback gets a visible 'Default' badge so first-time visitors
    know which view they probably want."""
    html = render_landing_page([PLAYBACK_TEAM, _hypothetical_team()])
    # Roughly: the 'Default' badge appears near the playback card,
    # not near the other one.
    playback_card_idx = html.index('href="playback/index.html"')
    other_card_idx = html.index('href="example/index.html"')
    default_idx = html.index("Default")
    # The badge sits between the playback href and the next card.
    assert playback_card_idx < default_idx < other_card_idx


def test_landing_page_shows_roster_size_hint():
    """Each card includes a 'N listed reviewer(s)' hint so a reader
    can size up the team without clicking through."""
    html = render_landing_page([PLAYBACK_TEAM])
    n = len(PLAYBACK_TEAM.members)
    assert f"{n} listed reviewers" in html


def test_landing_page_carries_mozilla_favicon():
    """The landing page should match the per-team pages' branding —
    same red 'm' favicon."""
    html = render_landing_page([PLAYBACK_TEAM])
    assert "%23FF0039" in html  # Mozilla red, URL-encoded
    assert "text-anchor='middle'>m</text>" in html


def test_landing_page_includes_every_registered_team_when_called_from_main():
    """End-to-end: rendering from the actual TEAMS registry includes
    every entry. Picking this up here means a future commit that
    adds a team to TEAMS auto-extends the landing page without any
    landing-specific work."""
    html = render_landing_page(list(TEAMS.values()))
    for team in TEAMS.values():
        assert f'href="{team.slug}/index.html"' in html
