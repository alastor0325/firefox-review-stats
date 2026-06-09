"""Render the report dict into a self-contained HTML page."""

import json
from pathlib import Path

from .ui import GITHUB_CORNER_CSS, github_corner_html


_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "index.html.tmpl"
_DATA_PLACEHOLDER = "__DATA_JSON__"
_PHAB_PLACEHOLDER = "__PHAB_DATA_JSON__"
_GH_CORNER_PLACEHOLDER = "__GH_CORNER__"
_GH_CORNER_CSS_PLACEHOLDER = "__GH_CORNER_CSS__"


def _safe_json(data: object) -> str:
    # Escape `<` so a `</script>` inside any string value can't break out
    # of the inline <script> block.
    return (
        json.dumps(data, default=str, ensure_ascii=False)
        .replace("<", "\\u003c")
    )


def render_html(
    data: dict,
    *,
    phab_data: dict | None = None,
    template_path: Path | None = None,
) -> str:
    path = template_path or _TEMPLATE_PATH
    template = path.read_text(encoding="utf-8")
    return (
        template
        .replace(_DATA_PLACEHOLDER, _safe_json(data))
        .replace(_PHAB_PLACEHOLDER, _safe_json(phab_data))
        .replace(_GH_CORNER_PLACEHOLDER, github_corner_html())
        .replace(_GH_CORNER_CSS_PLACEHOLDER, GITHUB_CORNER_CSS)
    )
