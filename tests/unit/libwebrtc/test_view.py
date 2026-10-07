"""The libwebrtc data has its own view (tab) on the WebRTC page. The generic
view wiring (hiding, period toggle, payload gate) is tested for every view
in tests/unit/render/test_two_axis_toggle.py; this covers what is specific
to this view."""

import re

from reviewstats.render import render_html
from tests.unit.render.test_sticky_layout import _MINIMAL_DATA

HTML = render_html(_MINIMAL_DATA)


def test_has_a_tab_button():
    assert re.search(r'<button data-view="libwebrtc"[^>]*>libwebrtc</button>', HTML)


def test_the_section_belongs_to_the_view_not_team_view():
    m = re.search(r'<div id="libwebrtc-section" class="([^"]+)"', HTML)
    assert m and m.group(1).split() == ["libwebrtc-only"], m and m.group(1)


def test_stale_data_is_flagged():
    """If the weekly fetch keeps failing, last week's file is kept, so the
    page must say how old the data is rather than look current."""
    assert 'id="libwebrtc-stale"' in HTML
    assert re.search(r"LIBWEBRTC_STALE_DAYS\s*=\s*10\b", HTML)


def test_section_renderers_are_isolated():
    """One malformed section must not stop the others or the tab gate."""
    assert re.search(r"try \{ fn\(data\); \} catch \(e\)", HTML)


def test_sections_in_order():
    html = HTML[HTML.index('id="libwebrtc-section"'):]
    order = [html.index(x) for x in ('id="libwebrtc-rows"', 'id="lw-plan-rows"',
                                     'id="lw-lag"', 'id="chart-lw-stack"')]
    assert order == sorted(order)
