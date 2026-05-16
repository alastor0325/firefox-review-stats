"""Render the report dict into a self-contained HTML page."""

import json
from pathlib import Path


_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "index.html.tmpl"
_DATA_PLACEHOLDER = "__DATA_JSON__"


def _safe_json(data: object) -> str:
    # Escape `<` so a `</script>` inside any string value can't break out
    # of the inline <script> block.
    return (
        json.dumps(data, default=str, ensure_ascii=False)
        .replace("<", "\\u003c")
    )


def render_html(data: dict, *, template_path: Path | None = None) -> str:
    path = template_path or _TEMPLATE_PATH
    template = path.read_text(encoding="utf-8")
    return template.replace(_DATA_PLACEHOLDER, _safe_json(data))
