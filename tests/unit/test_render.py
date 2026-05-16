import json

from reviewstats.render import render_html


def test_renders_placeholder_replaced():
    data = {"meta": {"path": "dom/media", "group": "g"}, "summary": {}}
    html = render_html(data)
    assert "__DATA_JSON__" not in html
    assert "dom/media" in html


def test_data_is_valid_json_inline():
    data = {"meta": {"group": "media-playback-reviewers"}}
    html = render_html(data)
    start = html.index("const DATA = ") + len("const DATA = ")
    end = html.index(";\n", start)
    parsed = json.loads(html[start:end])
    assert parsed["meta"]["group"] == "media-playback-reviewers"


def test_dangerous_content_is_escaped():
    data = {"meta": {"group": "</script><script>alert(1)</script>"}}
    html = render_html(data)
    start = html.index("const DATA = ")
    end = html.index(";\n", start)
    assert "</script>" not in html[start:end]
