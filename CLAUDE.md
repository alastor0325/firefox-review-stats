# Dev Rules

All code changes must follow the **firefox-review-stats Dev Loop** defined in `.claude/skills/firefox-review-stats-dev/skill.md`. Run `/firefox-review-stats-dev` at the start of every implementation task.

## Project context

- **Purpose:** analyze dom/media review-load distribution and surface bottleneck risk.
- **Design doc:** `~/firefox-bug-investigation/dom-media-reviewer-bottleneck-investigation.md` (authoritative — scope, definitions, charts).
- **Refresh cadence:** weekly (rolling 6-month window).
- **Stack:** Python 3 stdlib (Phase 1), plus `requests` (Phase 2). Chart.js via CDN for HTML rendering.
- **No new heavy deps without explicit user approval.**
