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
