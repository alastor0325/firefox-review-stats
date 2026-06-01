"""Tests for the root landing page.

Multi-team layout puts each team in `<slug>/index.html`. The site
root (`/index.html`) is a small picker that lists every registered
team as a card. Up/Down arrows move a focus highlight through the
teams (Enter follows the focused link).
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


def test_landing_page_has_no_default_badge():
    """The 'Default' badge was removed from the playback row — it
    didn't help anyone pick a team. Guard the removal so the badge
    (and its now-dead CSS class) can't creep back."""
    html = render_landing_page([PLAYBACK_TEAM, _hypothetical_team()])
    # Target the badge markup specifically — a bare "Default" substring
    # check would false-positive on JS like `preventDefault`.
    assert "default-badge" not in html
    assert ">Default</span>" not in html


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


class TestTeamKeyboardNav:
    """Up/Down arrows move a focus highlight through the team rows so
    the landing page is keyboard-drivable like the per-team dashboards.
    As with the other JS-behaviour tests we pin the emitted handler's
    structural pieces rather than running it."""

    def test_keydown_handler_navigates_team_rows(self):
        html = render_landing_page([PLAYBACK_TEAM, _hypothetical_team()])
        assert "addEventListener('keydown'" in html, (
            "landing page should register a keydown handler"
        )
        assert "ArrowDown" in html and "ArrowUp" in html, (
            "Up/Down should drive team navigation"
        )
        # Operates on the team-row anchors and moves focus between them.
        assert "a.team-row" in html
        assert ".focus()" in html
        assert "preventDefault" in html, (
            "handled arrows must preventDefault so the page doesn't scroll"
        )

    def test_navigation_wraps_around(self):
        html = render_landing_page([PLAYBACK_TEAM, _hypothetical_team()])
        assert "% rows.length" in html, (
            "Down past the last row should wrap to the first (modulo)"
        )

    def test_ignores_modifier_combos(self):
        """Cmd/Alt/Ctrl/Shift + arrow are reserved by the OS/browser —
        don't hijack them on the landing page either."""
        html = render_landing_page([PLAYBACK_TEAM])
        for mod in ("metaKey", "altKey", "ctrlKey", "shiftKey"):
            assert mod in html, f"{mod} must be left to the OS/browser"

    def test_focus_highlight_style_present(self):
        html = render_landing_page([PLAYBACK_TEAM])
        assert ".team-row:focus" in html, (
            "the selected team needs a visible focus style"
        )

    def test_hover_wins_over_focus_so_only_one_row_highlights(self):
        """If a row holds keyboard focus and the user hovers a *different*
        row, only the hovered row may light up. The focus highlight is
        gated behind 'no row hovered' so the two never co-highlight."""
        html = render_landing_page([PLAYBACK_TEAM])
        assert "main:not(:has(.team-row:hover)) .team-row:focus" in html, (
            "focus highlight must be suppressed while any row is hovered "
            "so hover and focus don't both show"
        )


def test_landing_page_includes_every_registered_team_when_called_from_main():
    """End-to-end: rendering from the actual TEAMS registry includes
    every entry. Picking this up here means a future commit that
    adds a team to TEAMS auto-extends the landing page without any
    landing-specific work."""
    html = render_landing_page(list(TEAMS.values()))
    for team in TEAMS.values():
        assert f'href="{team.slug}/index.html"' in html
