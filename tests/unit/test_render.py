import json

from reviewstats.render import render_html


def test_renders_placeholder_replaced():
    data = {"meta": {"path": "dom/media", "group": "g"}, "summary": {}}
    html = render_html(data)
    assert "__DATA_JSON__" not in html
    # The JSON should be embedded somewhere in the output.
    assert "dom/media" in html


def test_data_is_valid_json_inline():
    data = {"meta": {"group": "media-playback-reviewers"}}
    html = render_html(data)
    # Pull out the JSON between markers.
    start_marker = "const DATA = "
    end_marker = ";\n"
    idx = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, idx)
    parsed = json.loads(html[idx:end])
    assert parsed["meta"]["group"] == "media-playback-reviewers"


def test_dangerous_content_is_escaped():
    # JSON serialization should escape angle brackets so an injected
    # `</script>` in the data cannot break out of the inline script.
    data = {"meta": {"group": "</script><script>alert(1)</script>"}}
    html = render_html(data)
    # The literal `</script>` should NOT appear inside the embedded JSON.
    start = html.index("const DATA = ")
    end = html.index(";\n", start)
    inline_block = html[start:end]
    assert "</script>" not in inline_block
