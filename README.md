# firefox-review-stats

Per-team dashboards for Mozilla — review-load distribution plus a digest of what each component shipped recently. Each dashboard covers the past 6 months of patches landed under the team's owned paths, refreshed weekly via a GitHub Action and published to GitHub Pages.

**Live**: <https://alastor0325.github.io/firefox-review-stats/>

| Team | Group tag | Paths |
| --- | --- | --- |
| [Playback](https://alastor0325.github.io/firefox-review-stats/playback/) | `media-playback-reviewers` | `dom/media` (excluding `dom/media/webrtc`, `dom/media/systemservices`) |
| [WebRTC](https://alastor0325.github.io/firefox-review-stats/webrtc/) | `webrtc-reviewers` | `dom/media/webrtc`, `dom/media/systemservices` |
| [GFX](https://alastor0325.github.io/firefox-review-stats/gfx/) | `gfx-reviewers` | `gfx`, `image`, `dom/canvas`, `dom/webgpu` (excluding vendored upstreams) |

## What the dashboard shows

Each per-team page has four views, toggled at the top:

- **Team View** — Headline summary (in-scope patch count, group-tagged %, listed-members reviewing, "landed without team review" with a foldable drill-down pie + patch list). Within-group reviewer distribution, concentration metrics (Gini, bus factor), sole-reviewer-risk, total reviews per member, top patch authors, author→reviewer mapping. Four periods: **1-Month** / **3-Month** / **6-Month** rollups (same content, narrower commit slices) and **Per-Week** (most-recent-week slice for wait-time data).
- **Member View** — Per-member profile: weekly activity (reviews + patches submitted), authors whose patches they reviewed, wait-time tiles when they're the author.
- **Wait Queue** — Per-revision table of in-scope, member-authored patches sorted by longest wait first. Links straight into Phabricator.
- **Recent Changes** — A "what changed in this component" digest, defaulting to **This Week** (toggle to **This Month**). Landed **patches** (one per revision; re-lands counted once) are grouped into **feature areas** — the subdirectory each patch changed the most, mapped to a friendly label — **ordered by number of patches**, with a `count/total · %` badge per area. Each area shows a short, plain-language LLM **overview** (what changed and why it matters; a key highlight may be bolded in red) with its full patch list tucked behind a **"Show N patches"** toggle, collapsed by default. Covers all landings, not just team-reviewed ones. Overviews are generated at refresh time by the Claude API (see [Recent-change summaries](#recent-change-summaries)); without an API key the tab still renders the patch lists, just without overviews.

**Keyboard navigation:** on a team page, **←/→** cycle the view (Team → Member → Wait Queue → Recent Changes) and **Shift+←/→** cycle the period (6-Month → 3-Month → 1-Month → Per-Week, Team View only). Arrows are ignored while typing in a field, and Cmd/Alt/Ctrl+arrow are left to the OS/browser (Ctrl+← / → is the macOS Spaces switch, which is why Shift — not Ctrl — drives the period).

**Deep links:** the view and its period/window are encoded in the URL hash, so you can link straight to a state — `#team/6m`, `#team/3m`, `#team/1m`, `#team/weekly`, `#member`, `#queue`, `#recent/1w`, `#recent/1m`. The hash updates as you toggle and is restored on load and on back/forward.

The landing page is a static picker that lists every registered team and links into its subfolder. **↑/↓** move a focus highlight through the teams; **Enter** opens the highlighted one.

## Architecture

Three top-level scripts produce the per-team output:

```text
analyze_git.py             # GitHub commits → <slug>/data_git.json + <slug>/index.html
                           # + root index.html (landing picker)
analyze_phab.py            # Phab revision timelines → <slug>/data_phab.json
dump_author_patches.py     # Plain-text per-author dump → <slug>/author_patches.txt
```

All three iterate `reviewstats.teams.TEAMS` and produce per-team output under `<slug>/`. `raw_data/` and the on-disk caches (`.phab_html_cache/`, `.commit_files_cache/`) stay flat at root — they're keyed by D-number / SHA and shared across teams.

Data sources:

- **GitHub REST API** for commit history (auth via `GH_TOKEN` env or `gh auth token`).
- **Phabricator HTML scraping** via Playwright (real Chromium TLS fingerprint — anonymous `urlopen` trips Varnish 429s). Public revisions only; sec-bug revisions return the login page and are skipped.
- **Single-commit GitHub endpoint** for file-list lookups, used by the "landed without team review" subdir classifier and the Recent Changes feature-area grouping. Cached per-SHA on disk (shared between both passes — a SHA is fetched at most once).
- **LLM inference** for the Recent Changes per-area overviews — [GitHub Models](https://github.com/marketplace/models) in CI (free, no stored key) or the Claude API locally. One overview per feature area per window, cached by content hash in the git-tracked `.summary_cache/`. See [Recent-change summaries](#recent-change-summaries).

The library is in `reviewstats/`:

```text
teams.py        # Team dataclass + TEAMS registry (config-only edits to add a team)
members.py      # Thin re-export of PLAYBACK_TEAM.members for legacy callers
metrics.py      # Pure aggregations: routing, sole-reviewer, weekly trends, gini, bus factor
recent_changes.py  # Feature-area labels + grouping for the Recent Changes tab
summarize.py    # LLM "what we did" summaries (Anthropic SDK, disk-cached by content hash)
report.py       # build_report(): the JSON shape consumed by the HTML page
render.py       # Inlines build_report's output into templates/index.html.tmpl
landing.py      # Root index.html team picker
github_commits.py / phab_html.py / commit_files.py    # External-data clients
wait_time.py / patch_list.py     # Wait-time + Wait Queue helpers
parse.py / aliases.py / git_log.py     # Commit subject parsing + author canonicalisation
```

## Adding a new team

The multi-team refactor means this is a config-only change. Roughly 4 lines + tests:

1. Edit `reviewstats/teams.py`:
   ```python
   FOO_TEAM = Team(
       slug="foo",
       display_name="foo-reviewers",
       group="foo-reviewers",
       paths=("some/path",),
       excludes=(),                  # vendored upstreams under your paths, if any
       members={"handle": "Display Name", ...},
   )
   TEAMS[FOO_TEAM.slug] = FOO_TEAM
   ```
2. Edit `.github/workflows/refresh.yml` and add `foo/` to the `git add` line.
3. Add a `test_foo_team_matches_user_spec` (and roster test) in `tests/unit/core/test_teams.py` — mirrors the existing `WEBRTC_TEAM` / `GFX_TEAM` tests.
4. Run `python analyze_git.py && python analyze_phab.py && python dump_author_patches.py` locally. Verify `foo/index.html` looks right. Commit + push.

The `test_commits_per_team_subfolders` test iterates `TEAMS` and will fail loudly if step 2 is missing.

## Local development

Python 3.10+ (CI runs 3.12). Set up a virtualenv and install Playwright:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest playwright anthropic   # anthropic only needed for summaries
python -m playwright install chromium
```

Run the test suite:

```bash
python -m pytest tests/             # 349 tests (unit + integration)
python -m pytest tests/unit/        # unit only
python -m pytest tests/integration/ # value-side end-to-end checks
```

Generate the site:

```bash
python analyze_git.py               # cheap (GitHub API, paginated commits)
python analyze_phab.py              # slow first time per new team (Playwright + Phab)
python dump_author_patches.py       # cheap (re-uses analyze_git's API)
```

Serve locally:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
# Then open http://127.0.0.1:8765/
```

### Recent-change summaries

The Recent Changes tab's per-area overviews are generated in `analyze_git.py`. They're **optional** — with no backend the tab still renders the patch lists. `analyze_git.py` picks a backend from `REVIEW_STATS_SUMMARY_BACKEND`:

- **`github` (CI default) — free, no key stored.** Uses [GitHub Models](https://github.com/marketplace/models) via the workflow's own token (`permissions: models: read`), so nothing third-party is stored. Default model `openai/gpt-4o-mini` (small is plenty for short summaries; override with `REVIEW_STATS_SUMMARY_MODEL`). Calls are paced for the free per-minute limit; a once-weekly batch (~80 short requests) sits comfortably under the free low-tier daily cap. The free tier is framed for experimentation, not production.
- **`anthropic` (local, nicer prose).** Uses the Claude API (`ANTHROPIC_API_KEY`, `pip install anthropic`), default `claude-opus-4-8`. Run [`./refresh-overviews.sh`](refresh-overviews.sh) locally to regenerate, commit cache entries, and push. Use this if you want Opus-grade wording without storing a key in CI.
- **off / unset.** No generation; overviews already in the committed cache are still reused.

**`.summary_cache/` is tracked in git** — each overview is cached by content hash (feature area + its set of patches), so any backend reuses overviews already generated (within a run and across runs when the same patch set recurs) and only generates genuinely-new areas. Delete the directory to force a full re-summarize.

Past overviews are snapshotted under [`summary-baselines/`](summary-baselines/) (text + the inputs they were generated from) so different models can be compared.

## Tests

Organised by concern, not by source file:

```text
tests/unit/
  core/        Team registry, parse, aliases, git_log, members/author filters
  fetch/       github_commits, phab_html, incremental_fetch
  metrics/     aggregations, classifier, wait_time, patch_list (13 files)
  report/      build_report shape (4 files)
  render/      HTML template + page UI (12 files)
  analyzers/   analyze_git + analyze_phab per-team loops
  workflow/    GitHub Action contract (iterates TEAMS to verify the
               workflow file picks up every registered team)

tests/integration/
  test_team_report_render_e2e.py   commits → build_report → render → value-side asserts
                                   (for both single-path Playback and multi-path WebRTC)
  test_phab_render_e2e.py          phab_data round-trips intact through render
  test_landing_e2e.py              landing renders every registered team correctly
```

The workflow runs `pytest tests/` so both layers gate every weekly refresh.

## CI / weekly refresh

`.github/workflows/refresh.yml` fires on Monday 09:00 UTC and on manual `workflow_dispatch`. Each run:

1. Restores the `.phab_html_cache/` and `.commit_files_cache/` from the previous run (keyed by `github.run_id`, with a fallback prefix restore key — so a brand-new run can still inherit caches). (`.summary_cache/` is tracked in git, not restored here.)
2. Runs the full test suite.
3. Runs `analyze_git.py` → `analyze_phab.py` → `dump_author_patches.py` over every registered team.
4. Stages `index.html`, `<slug>/` for every team, and `raw_data/`.
5. Commits (`weekly: YYYY-WW refresh`) and pushes if anything changed. GitHub Pages picks up the push and republishes.

Steady-state runtime: ~5 minutes (warm cache). Cold-cache for a brand-new team: ~10–15 minutes the first time (Playwright fetches the team's new D-numbers, then they're cached).

The Recent Changes overviews are generated in CI via GitHub Models (free, using the workflow's own `models: read` token — no stored key), and cached in the committed `.summary_cache/` for reuse. See [Recent-change summaries](#recent-change-summaries).

## Layout

```text
index.html                  # Landing page, regenerated each run
playback/                   # Per-team subfolders, regenerated each run
  index.html
  data_git.json
  data_phab.json
  author_patches.txt
webrtc/  gfx/               # Same shape

raw_data/D<n>.json          # Parsed Phab timelines, team-agnostic, committed to git
.phab_html_cache/           # Raw Phab HTML, gitignored, restored from GHA cache
.commit_files_cache/        # GitHub single-commit responses, gitignored, GHA cache
```
