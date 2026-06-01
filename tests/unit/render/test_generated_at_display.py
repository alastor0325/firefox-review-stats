"""The header's generated-time line prefers the Pacific display string.

`build_report` now emits `meta.generated_at_display` (Pacific time).
The template shows that, falling back to the raw ISO `generated_at`
for reports generated before the field existed — same defensive
pattern as `DATA.meta.excludes || []`.
"""

from reviewstats.render import render_html

from tests.unit.render.test_two_axis_toggle import _MINIMAL_DATA


def test_header_uses_pacific_display_with_iso_fallback():
    html = render_html(_MINIMAL_DATA)
    assert "DATA.meta.generated_at_display" in html, (
        "header should show the Pacific display string"
    )
    # Legacy reports lack the field — fall back to the ISO instant.
    assert "DATA.meta.generated_at_display || DATA.meta.generated_at" in html, (
        "must fall back to the raw ISO generated_at when the display "
        "field is absent (older reports)"
    )
