"""Tests for arrow-key navigation of the two-axis toggle bar.

The dashboard already switches state via `data-view` (team|member|queue)
and `data-period` (1m|3m|total|weekly) on `<body>`. This feature adds a
global `keydown` handler so the keyboard mirrors the click toggles:

  * Left / Right            → cycle the VIEW axis (team → member → queue)
  * Shift + Left / Right    → cycle the PERIOD axis, Team View only

Shift (not Ctrl) is the period modifier: Ctrl+Arrow is the macOS Spaces
shortcut, so the OS swallows it before the page sees it. Cycling wraps
around (right past the last lands on the first), the ordered values are
read from the *visible* toggle buttons (so the legacy-report case where
1m/3m are hidden is skipped automatically), and the handler stays out of
the way when the user is typing in a field or holding an OS/browser
reserved modifier (Cmd / Alt / Ctrl).

As with the other JS-behaviour tests in this directory, we can't run the
JS here, so we pin the structural pieces of the emitted handler.
"""

import re

from reviewstats.render import render_html

from tests.unit.render.test_two_axis_toggle import _MINIMAL_DATA


def _render() -> str:
    return render_html(_MINIMAL_DATA)


class TestSettersAreReusable:
    def test_bindtoggle_returns_setter_captured_per_axis(self):
        """The keyboard handler reuses the same `set` the click handler
        uses, so `bindToggle` must return it and both axes capture it."""
        html = _render()
        assert re.search(r"return set\b", html), (
            "bindToggle should return its `set` so the keyboard handler "
            "can drive the same state transitions as a click"
        )
        assert re.search(r"setView\s*=\s*bindToggle\('view'\)", html)
        assert re.search(r"setPeriod\s*=\s*bindToggle\('period'\)", html)


class TestKeydownHandler:
    def test_global_keydown_listener_registered(self):
        html = _render()
        assert re.search(r"document\.addEventListener\(\s*'keydown'", html), (
            "expected a document-level keydown listener for arrow nav"
        )

    def test_handles_left_and_right_arrows(self):
        html = _render()
        assert "ArrowLeft" in html and "ArrowRight" in html, (
            "handler must react to ArrowLeft / ArrowRight"
        )

    def test_shift_selects_period_axis_plain_selects_view(self):
        html = _render()
        # Shift distinguishes the two axes (Ctrl+Arrow is the macOS
        # Spaces shortcut, so it can't drive the period).
        assert re.search(r"if\s*\(\s*e\.shiftKey\s*\)", html), (
            "period nav must branch on e.shiftKey"
        )
        assert re.search(r"setPeriod\(", html), "period nav must call setPeriod"
        assert re.search(r"setView\(", html), "view nav must call setView"

    def test_shift_nav_drives_secondary_axis_per_view(self):
        """Shift+arrow drives the current view's secondary axis: the period
        in Team View, the week/month window in Recent Changes. In other
        views it's a no-op rather than mutating a hidden axis."""
        html = _render()
        assert re.search(
            r"dataset\.view\s*===\s*'team'", html
        ), "Shift nav should drive the period axis when data-view is 'team'"
        assert re.search(
            r"dataset\.view\s*===\s*'recent'", html
        ), "Shift nav should drive the recent-window axis when data-view is 'recent'"
        assert re.search(r"setRecent\(", html), "recent nav must call setRecent"

    def test_prevent_default_when_handled(self):
        html = _render()
        assert "preventDefault" in html, (
            "handled arrow keys must preventDefault so the page doesn't scroll"
        )


class TestCycleHelper:
    def test_cycle_helper_present_and_wraps(self):
        """`cycleValue(values, current, dir)` is the pure piece — index of
        current, step by dir, wrap with modulo."""
        html = _render()
        assert re.search(r"function cycleValue\(", html), (
            "expected a cycleValue helper"
        )
        assert re.search(r"%\s*values\.length", html), (
            "cycling must wrap using modulo of the value count"
        )

    def test_values_derived_from_visible_buttons(self):
        """Hidden period buttons (1m/3m on legacy reports) must be skipped,
        so the value list comes from buttons that are actually visible."""
        html = _render()
        assert re.search(r"function visibleAxisValues\(", html)
        assert "offsetParent" in html, (
            "visibility of toggle buttons should be detected via offsetParent"
        )


class TestDoesNotHijackTyping:
    def test_ignores_input_select_textarea_and_contenteditable(self):
        html = _render()
        for tok in ("INPUT", "SELECT", "TEXTAREA", "isContentEditable"):
            assert tok in html, (
                f"arrow nav must not fire while focused in a {tok} field"
            )

    def test_modifier_guard_ignores_os_combos_but_not_shift(self):
        """Cmd+Arrow (browser back/forward), Alt+Arrow (word motion) and
        Ctrl+Arrow (macOS Spaces) must pass through untouched. Shift is
        the period modifier, so it must NOT be in the ignore guard."""
        html = _render()
        guards = re.findall(
            r"if \(([^)]*(?:metaKey|altKey|ctrlKey|shiftKey)[^)]*)\)\s*return;",
            html,
        )
        assert guards, "expected a modifier early-return guard"
        guard = guards[0]
        for mod in ("metaKey", "altKey", "ctrlKey"):
            assert mod in guard, f"{mod} must be in the ignore guard: {guard!r}"
        assert "shiftKey" not in guard, (
            "Shift is the period modifier — it must not be ignored"
        )
