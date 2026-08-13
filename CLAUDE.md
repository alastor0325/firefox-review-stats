# Dev Rules

All code changes must follow the **firefox-review-stats Dev Loop** defined in `.claude/skills/firefox-review-stats-dev/skill.md`. Run `/firefox-review-stats-dev` at the start of every implementation task.

Touching `METRICS` in `fetch_perf_metrics.py` — adding, repointing or removing a Media Health metric — additionally requires `/add-media-metric`. A metric can fetch without error and still never paint, or paint numbers from months ago; that skill is the verification sequence. Do not conclude a metric works because the fetch exited zero.

## Project context

- **Purpose:** analyze dom/media review-load distribution and surface bottleneck risk.
- **Design doc:** `~/firefox-bug-investigation/dom-media-reviewer-bottleneck-investigation.md` (authoritative — scope, definitions, charts).
- **Refresh cadence:** weekly (rolling 6-month window).
- **Stack:** Python 3 stdlib (Phase 1), plus `requests` (Phase 2). Chart.js via CDN for HTML rendering.
- **No new heavy deps without explicit user approval.**
