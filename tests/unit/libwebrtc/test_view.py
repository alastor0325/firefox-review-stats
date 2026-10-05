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


def test_has_three_sub_tabs_defaulting_to_releases():
    bar = re.search(r'class="toggle-bar"(.*?)</nav>', HTML, re.DOTALL).group(1)
    assert re.findall(r'<button data-lw="(\w+)"', bar) == ["releases", "next", "stack"]
    assert re.search(r'<body[^>]*data-lw="releases"', HTML)


def test_sub_tab_group_is_shown_only_in_this_view():
    assert re.search(r"\.toggle-group-lw,\s*\.toggle-sep-lw\b", HTML)
    shown = re.findall(r'body\[data-view="(\w+)"\]\s*\.toggle-(?:group|sep)-lw', HTML)
    assert set(shown) == {"libwebrtc"}, shown


def test_each_sub_view_is_hidden_unless_selected():
    for sub in ("releases", "next", "stack"):
        assert re.search(rf'body:not\(\[data-lw="{sub}"\]\)\s*\.lw-{sub}-only', HTML), sub
        assert f'class="lw-{sub}-only"' in HTML, sub


def test_sub_view_is_part_of_the_hash_and_shift_arrows():
    assert re.search(r"libwebrtc:\s*\{ axis: 'lw', def: 'releases', set: setLw \}", HTML)


def test_stale_data_is_flagged():
    """If the weekly fetch keeps failing, last week's file is kept, so the
    page must say how old the data is rather than look current."""
    assert 'id="libwebrtc-stale"' in HTML
    assert re.search(r"LIBWEBRTC_STALE_DAYS\s*=\s*10\b", HTML)


def test_new_sub_view_containers_exist():
    for el in ('id="lw-current"', 'id="lw-upcoming-rows"', 'id="lw-lag"',
               'id="lw-stack-summary"', 'id="chart-lw-stack"', 'id="lw-stack-rows"'):
        assert el in HTML, el


def test_each_optional_section_has_its_own_note():
    """A section that fell back to last week's copy, or has no data yet,
    says so inside its own sub-tab."""
    for el in ('id="lw-next-note"', 'id="lw-stack-note"'):
        assert el in HTML, el


def test_projected_targets_are_labelled_as_projected():
    assert "Targets Firefox (projected)" in HTML


def test_section_renderers_are_isolated():
    """One malformed section must not stop the others or the tab gate."""
    assert re.search(r"try \{ fn\(data\); \} catch \(e\)", HTML)
