"""Tests for arrow-key navigation of the two-axis toggle bar.

The dashboard already switches state via `data-view` (team|member|queue)
and `data-period` (1m|3m|total|weekly) on `<body>`. This feature adds a
global `keydown` handler so the keyboard mirrors the click toggles:

  * Left / Right            → cycle the VIEW axis (team → member → queue)
  * Ctrl + Left / Right     → cycle the PERIOD axis, Team View only

Cycling wraps around (right past the last lands on the first), the
ordered values are read from the *visible* toggle buttons (so the
legacy-report case where 1m/3m are hidden is skipped automatically),
and the handler stays out of the way when the user is typing in a field
or holding a browser-reserved modifier (Cmd/Alt).

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

    def test_ctrl_selects_period_axis_plain_selects_view(self):
        html = _render()
        # Ctrl distinguishes the two axes.
        assert re.search(r"\bctrlKey\b", html), (
            "Ctrl must select the period axis vs the view axis"
        )
        assert re.search(r"setPeriod\(", html), "period nav must call setPeriod"
        assert re.search(r"setView\(", html), "view nav must call setView"

    def test_period_nav_gated_to_team_view(self):
        """Period only applies in Team View; Ctrl+arrow elsewhere is a
        no-op rather than silently mutating a hidden axis."""
        html = _render()
        assert re.search(
            r"dataset\.view\s*!==\s*'team'", html
        ), "period navigation should bail out unless data-view is 'team'"

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

    def test_ignores_browser_reserved_modifiers(self):
        """Cmd/Alt + Left/Right are browser back/forward & word motion —
        the handler must not swallow them."""
        html = _render()
        assert re.search(r"\bmetaKey\b", html), (
            "must ignore Cmd/Meta so browser back/forward still works"
        )
        assert re.search(r"\baltKey\b", html), (
            "must ignore Alt so word-motion / browser nav still works"
        )
