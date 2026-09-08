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
_DISABLED_VIEWS_PLACEHOLDER = "__DISABLED_VIEWS_JSON__"

# Views switched off on every team page, whatever data exists behind them —
# a config gate, unlike Recent Changes and Media Health which hide
# themselves when their payload is missing. Ordered, so the rendered page
# doesn't churn between runs.
#
# TO RE-ENABLE: remove the id. Nothing else to undo.
DISABLED_VIEWS: tuple[str, ...] = ("queue",)

# Payload that only a disabled view can render, and is worth not shipping:
# `patch_list` is 13-20% of a rendered page and has exactly one reader, the
# Wait Queue table. Keyed by view id so the association is explicit.
_VIEW_PAYLOAD_KEYS: dict[str, str] = {"queue": "patch_list"}


def _safe_json(data: object) -> str:
    # Escape `<` so a `</script>` inside any string value can't break out
    # of the inline <script> block.
    return (
        json.dumps(data, default=str, ensure_ascii=False)
        .replace("<", "\\u003c")
    )


def strip_disabled_payloads(
    phab_data: dict | None,
    disabled: tuple[str, ...] | None = None,
) -> dict | None:
    """Drop payload whose only reader is a disabled view.

    Hiding the tab already makes the view unreachable; this stops the page
    carrying data nothing can render. Returns a shallow copy — the caller's
    dict is written to disk as `data_phab.json` and must keep every key, so
    re-enabling stays a config flip with no re-scrape.
    """
    # Resolved at call time, not bound as a default — otherwise the module
    # constant is captured at import and can never be overridden.
    disabled = DISABLED_VIEWS if disabled is None else disabled
    if not phab_data:
        return phab_data
    drop = {
        key for view, key in _VIEW_PAYLOAD_KEYS.items()
        if view in disabled and key in phab_data
    }
    if not drop:
        return phab_data
    return {k: v for k, v in phab_data.items() if k not in drop}


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
        .replace(_PHAB_PLACEHOLDER, _safe_json(strip_disabled_payloads(phab_data)))
        .replace(_ROADMAP_PLACEHOLDER, _safe_json(roadmap_data))
        .replace(_METRICS_PLACEHOLDER, _safe_json(metrics_data))
        .replace(_GH_CORNER_PLACEHOLDER, github_corner_html())
        .replace(_GH_CORNER_CSS_PLACEHOLDER, GITHUB_CORNER_CSS)
        .replace(_DISABLED_VIEWS_PLACEHOLDER, _safe_json(list(DISABLED_VIEWS)))
    )
