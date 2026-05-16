import json

from reviewstats.render import render_html


def test_renders_placeholder_replaced():
    data = {"meta": {"path": "dom/media", "group": "g"}, "summary": {}}
    html = render_html(data)
    assert "__DATA_JSON__" not in html
    assert "__PHAB_DATA_JSON__" not in html
    assert "dom/media" in html


def test_phab_data_defaults_to_null():
    html = render_html({"meta": {}})
    # When no phab data, the inline literal should be `null`.
    start = html.index("const PHAB_DATA = ")
    end = html.index(";\n", start)
    assert html[start + len("const PHAB_DATA = "):end] == "null"


def test_phab_data_embedded_when_provided():
    html = render_html({"meta": {}}, phab_data={"n": 100})
    start = html.index("const PHAB_DATA = ") + len("const PHAB_DATA = ")
    end = html.index(";\n", start)
    parsed = json.loads(html[start:end])
    assert parsed["n"] == 100


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
