"""Tests for the config switch that hides a view on every team page.

Recent Changes and Media Health hide themselves when their payload is
absent. This gate is different: it turns a view off for all teams whatever
data exists, it is meant to be temporary, and the whole switch is
`render.DISABLED_VIEWS`.

These tests assert the *mechanism*, parametrised over whatever the constant
currently holds, rather than hard-coding "queue" — otherwise re-enabling the
tab would turn the suite red, which is the opposite of the one-constant flip
the README promises. The runtime half of the contract (the tab is actually
invisible, the table is not built, `#queue` is refused) is behavioural and
lives in tests/integration/test_page_runtime.py.
"""

import json
import re

import pytest

from reviewstats import render
from reviewstats.render import DISABLED_VIEWS, render_html, strip_disabled_payloads

from tests.unit.render.test_two_axis_toggle import _MINIMAL_DATA


_PHAB = {
    "n": 2,
    "median_days": 1.0,
    "patch_list": [
        {"d": "D1", "title": "one", "author": "a", "wait_days": 1.0},
        {"d": "D2", "title": "two", "author": "b", "wait_days": 2.0},
    ],
}


def _render(**kw) -> str:
    return render_html(_MINIMAL_DATA, **kw)


class TestStripDisabledPayloads:
    """`patch_list` is 13-20% of a rendered page and its only reader is the
    Wait Queue table, so it should not ship while that view is off."""

    def test_drops_patch_list_when_queue_is_disabled(self):
        out = strip_disabled_payloads(_PHAB, disabled=("queue",))
        assert "patch_list" not in out
        assert out["n"] == 2, "unrelated keys must survive"

    def test_keeps_patch_list_when_nothing_is_disabled(self):
        assert strip_disabled_payloads(_PHAB, disabled=())["patch_list"] == (
            _PHAB["patch_list"]
        )

    def test_does_not_mutate_the_caller(self):
        """The same dict is written to disk as data_phab.json — dropping the
        key there would make re-enabling need a re-scrape, not a flag flip."""
        strip_disabled_payloads(_PHAB, disabled=("queue",))
        assert "patch_list" in _PHAB

    def test_returns_none_unchanged(self):
        assert strip_disabled_payloads(None, disabled=("queue",)) is None

    def test_unknown_disabled_view_drops_nothing(self):
        assert strip_disabled_payloads(_PHAB, disabled=("member",)) == _PHAB


class TestRenderedPayload:
    def test_disabled_views_constant_is_injected(self):
        m = re.search(r"const DISABLED_VIEWS = (\[.*?\]);", _render())
        assert m is not None, "DISABLED_VIEWS payload not injected"
        assert json.loads(m.group(1)) == list(DISABLED_VIEWS)

    def test_every_disabled_id_matches_a_real_view_button(self):
        """A typo ('queeu') would render happily and hide nothing — the
        forEach over zero matched buttons is a silent no-op."""
        html = _render()
        for view in DISABLED_VIEWS:
            assert f'data-view="{view}"' in html, (
                f"{view!r} matches no view button, so it disables nothing"
            )

    def test_disabled_view_buttons_stay_in_the_markup(self):
        """Hidden at runtime, not deleted — that is what keeps re-enabling a
        config flip instead of a code restore."""
        html = _render()
        for view in DISABLED_VIEWS:
            assert f'<button data-view="{view}"' in html

    def test_patch_list_is_absent_from_the_rendered_page(self):
        html = _render(phab_data=_PHAB)
        if "queue" in DISABLED_VIEWS:
            assert '"patch_list"' not in html
        else:
            assert '"patch_list"' in html


class TestReEnabling:
    """The README promises removing the id is all it takes. Verified end to
    end through render_html rather than through the helper alone."""

    def test_emptying_the_constant_ships_no_disabled_views(self, monkeypatch):
        monkeypatch.setattr(render, "DISABLED_VIEWS", ())
        assert "const DISABLED_VIEWS = [];" in _render()

    def test_emptying_the_constant_restores_the_patch_list(self, monkeypatch):
        monkeypatch.setattr(render, "DISABLED_VIEWS", ())
        assert '"patch_list"' in _render(phab_data=_PHAB)


class TestDefaultViewIsReachable:
    def test_body_default_view_is_not_disabled(self):
        """A page whose default view is hidden would open on a tab the user
        cannot see. The runtime fallback covers it, but the default should
        not need the fallback in the first place."""
        m = re.search(r'<body data-view="(\w+)"', _render())
        assert m is not None
        assert m.group(1) not in DISABLED_VIEWS


@pytest.mark.parametrize("view", ["team", "member", "queue", "recent", "health"])
def test_disabling_any_view_renders_without_error(view, monkeypatch):
    """Including the default — the page must still render, and the runtime
    fallback is what keeps it usable."""
    monkeypatch.setattr(render, "DISABLED_VIEWS", (view,))
    html = _render(phab_data=_PHAB)
    assert f'data-view="{view}"' in html
    assert json.loads(
        re.search(r"const DISABLED_VIEWS = (\[.*?\]);", html).group(1)
    ) == [view]
