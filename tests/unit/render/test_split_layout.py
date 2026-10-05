"""The `.split` row (bar chart + doughnut) must stay inside its card when
the window narrows. A Chart.js canvas keeps its old pixel width after a
resize, and both a bare `fr` track and an auto-margin grid item size
themselves to it, so the row overflowed instead of shrinking."""

import re

from reviewstats.render import render_html
from tests.unit.render.test_sticky_layout import _MINIMAL_DATA


def test_every_split_track_has_a_zero_minimum():
    html = render_html(_MINIMAL_DATA)
    rules = re.findall(r"\.split\s*\{([^}]*)\}", html)
    assert len(rules) == 2, "expected the base rule and the stacked @media rule"
    for rule in rules:
        cols = re.search(r"grid-template-columns:([^;]+)", rule).group(1)
        assert len(re.findall(r"[\d.]+fr", cols)) == len(
            re.findall(r"minmax\(\s*0\s*,", cols)
        ), cols


def test_square_chart_box_fills_its_track():
    # Anchored: `.nested-detail .chart-box.square` comes first in the file.
    m = re.search(r"(?m)^\s*\.chart-box\.square\s*\{([^}]*)\}",
                  render_html(_MINIMAL_DATA))
    assert m, "no .chart-box.square rule"
    rule = m.group(1)
    assert re.search(r"(^|;)\s*width:\s*100%", rule), rule
