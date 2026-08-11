"""Render the report dict into a self-contained HTML page."""

import json
from pathlib import Path

from .ui import GITHUB_CORNER_CSS, github_corner_html


_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "index.html.tmpl"
_DATA_PLACEHOLDER = "__DATA_JSON__"
_PHAB_PLACEHOLDER = "__PHAB_DATA_JSON__"
_ROADMAP_PLACEHOLDER = "__ROADMAP_DATA_JSON__"
_METRICS_PLACEHOLDER = "__METRICS_DATA_JSON__"
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
    roadmap_data: dict | None = None,
    metrics_data: dict | None = None,
    template_path: Path | None = None,
) -> str:
    """Render one team page.

    `roadmap_data` and `metrics_data` are optional and only supplied for the
    team that has a roadmap. When it is None the payload serialises to `null`, which is the
    signal the page uses to remove the Media Health tab — the same
    data-availability gate Recent Changes already uses. That keeps the view
    playback-only without the template needing to know team names.
    """
    path = template_path or _TEMPLATE_PATH
    template = path.read_text(encoding="utf-8")
    return (
        template
        .replace(_DATA_PLACEHOLDER, _safe_json(data))
        .replace(_PHAB_PLACEHOLDER, _safe_json(phab_data))
        .replace(_ROADMAP_PLACEHOLDER, _safe_json(roadmap_data))
        .replace(_METRICS_PLACEHOLDER, _safe_json(metrics_data))
        .replace(_GH_CORNER_PLACEHOLDER, github_corner_html())
        .replace(_GH_CORNER_CSS_PLACEHOLDER, GITHUB_CORNER_CSS)
    )
