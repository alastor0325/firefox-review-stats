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
        assert ".focus(" in html
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

    def test_highlight_is_a_single_js_toggled_selection_class(self):
        """One row at a time is highlighted via an `is-selected` class
        that JS toggles — not a CSS `:hover`/`:focus` rule. This is what
        keeps exactly one row lit and lets the keyboard stay in control."""
        html = render_landing_page([PLAYBACK_TEAM])
        assert ".team-row.is-selected" in html, (
            "the highlight should be a single `.is-selected` CSS rule"
        )
        assert "classList.toggle('is-selected'" in html, (
            "JS should drive the highlight by toggling `is-selected`"
        )

    def test_hover_sets_the_single_selection(self):
        """Hovering a row makes it the one highlighted row (mouseenter
        sets the shared selection), so a hovered row and a keyboard-
        selected row can never both light up."""
        html = render_landing_page([PLAYBACK_TEAM])
        assert "addEventListener('mouseenter'" in html, (
            "hovering a row should set the selection"
        )

    def test_keyboard_highlight_not_suppressed_by_hover(self):
        """Regression: a previous fix suppressed the focus highlight
        whenever any row was hovered (`:has(.team-row:hover)`), which hid
        keyboard movement while the cursor rested over the list — Up/Down
        looked dead. The highlight is now a JS-toggled class, independent
        of hover state, so the keyboard stays visibly in control."""
        html = render_landing_page([PLAYBACK_TEAM])
        assert ":has(.team-row:hover)" not in html, (
            "hover must not gate the highlight's visibility"
        )


def test_landing_page_includes_every_registered_team_when_called_from_main():
    """End-to-end: rendering from the actual TEAMS registry includes
    every entry. Picking this up here means a future commit that
    adds a team to TEAMS auto-extends the landing page without any
    landing-specific work."""
    html = render_landing_page(list(TEAMS.values()))
    for team in TEAMS.values():
        assert f'href="{team.slug}/index.html"' in html
