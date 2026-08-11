# firefox-review-stats

Per-team dashboards for Mozilla — review-load distribution plus a digest of what each component shipped recently. Each dashboard covers the past 6 months of patches landed under the team's owned paths, refreshed weekly via a GitHub Action and published to GitHub Pages.

**Live**: <https://alastor0325.github.io/firefox-review-stats/>

| Team | Group tag | Paths |
| --- | --- | --- |
| [Playback](https://alastor0325.github.io/firefox-review-stats/playback/) | `media-playback-reviewers` | `dom/media` (excluding `dom/media/webrtc`, `dom/media/systemservices`) |
| [WebRTC](https://alastor0325.github.io/firefox-review-stats/webrtc/) | `webrtc-reviewers` | `dom/media/webrtc`, `dom/media/systemservices` |
| [GFX](https://alastor0325.github.io/firefox-review-stats/gfx/) | `gfx-reviewers` | `gfx`, `image`, `dom/canvas`, `dom/webgpu` (excluding vendored upstreams) |

## What the dashboard shows

Each per-team page has four views, toggled at the top — plus a fifth, **Media Health**, on the playback page only:

- **Team View** — Headline summary (in-scope patch count, group-tagged %, listed-members reviewing, "landed without team review" with a foldable drill-down pie + patch list). Within-group reviewer distribution, concentration metrics (Gini, bus factor), sole-reviewer-risk, total reviews per member, top patch authors, author→reviewer mapping. Four periods: **1-Month** / **3-Month** / **6-Month** rollups (same content, narrower commit slices) and **Per-Week** (most-recent-week slice for wait-time data).
- **Member View** — Per-member profile: weekly activity (reviews + patches submitted), authors whose patches they reviewed, wait-time tiles when they're the author.
- **Wait Queue** — Per-revision table of in-scope, member-authored patches sorted by longest wait first. Links straight into Phabricator.
- **Recent Changes** — A "what changed in this component" digest, defaulting to **This Week** (toggle to **This Month**). Landed **patches** (one per revision; re-lands counted once) are grouped into **feature areas** — the subdirectory each patch changed the most, mapped to a friendly label — **ordered by number of patches**, with a `count/total · %` badge per area. Each area shows a short, plain-language LLM **overview** (what changed and why it matters; a key highlight may be bolded in red) with its full patch list tucked behind a **"Show N patches"** toggle, collapsed by default. Covers all landings, not just team-reviewed ones. Overviews are generated at refresh time by the Claude API (see [Recent-change summaries](#recent-change-summaries)); without an API key the tab still renders the patch lists, just without overviews.
- **Media Health** *(playback only)* — The media roadmap and, later, the Raptor performance metrics. Two subviews: **Roadmap** and **Performance**. Roadmap renders the curated item list in three groups — **Ordered** (impact against how many users meet the problem, cost breaking ties), **Need measuring first** (unranked: low confidence, or no reach figure — the next action is to find out, not to build), and **Continuous** (spec and upkeep, budgeted as a share of time rather than ranked). Each row expands to its authored consequence, evidence and details. **Reach is shown; the score it feeds is not** — reach is a contested input worth arguing about, the arithmetic isn't. The metrics table at the bottom is the seam with Performance: every target is currently unset, which is what blocks the perennial-quality scope. Unlike the other four views, this one is about the product rather than the review process, which is why it exists for one team only. It removes itself automatically on teams with no roadmap.

**Keyboard navigation:** on a team page, **←/→** cycle the view (Team → Member → Wait Queue → Recent Changes → Media Health) and **Shift+←/→** cycle the current view's secondary axis — the period in Team View (6-Month → 3-Month → 1-Month → Per-Week), the window in Recent Changes, the section in Media Health. Arrows are ignored while typing in a field, and Cmd/Alt/Ctrl+arrow are left to the OS/browser (Ctrl+← / → is the macOS Spaces switch, which is why Shift — not Ctrl — drives the period).

**Deep links:** the view and its period/window are encoded in the URL hash, so you can link straight to a state — `#team/6m`, `#team/3m`, `#team/1m`, `#team/weekly`, `#member`, `#queue`, `#recent/1w`, `#recent/1m`, `#health/roadmap`. The hash updates as you toggle and is restored on load and on back/forward.

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
       # Optional: trusted handles NOT on the roster whose review still
       # counts as team oversight. Patches they review don't show up as
       # "landed without team review". Unlike members, they never appear
       # in any load-distribution view (not treated as team members).
       approved_reviewers=frozenset({"trusted-handle"}),
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
python -m pytest tests/             # 653 tests (unit + integration)
python -m pytest tests/unit/        # unit only
python -m pytest tests/integration/ # value-side end-to-end checks
```

Generate the site:

```bash
python analyze_git.py               # cheap (GitHub API, paginated commits)
python analyze_git.py --roadmap-audience internal   # local only, never commit the result
python analyze_phab.py              # slow first time per new team (Playwright + Phab)
python dump_author_patches.py       # cheap (re-uses analyze_git's API)
```

Serve locally:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
# Then open http://127.0.0.1:8765/
```

### The Media Health view (playback only)

The Roadmap subview is generated from a hand-curated YAML file that lives
**outside this repo**, in the investigation repo:

```
~/firefox-bug-investigation/roadmap/roadmap.yaml     # override with $ROADMAP_YAML
```

`analyze_git.py` only ever **reads** it. The roadmap is slow-moving and
human-authored, so the weekly refresh must never regenerate or overwrite it. If
the file is absent — a fresh checkout, or CI without the investigation repo —
the view degrades to "tab not there" rather than failing the build.

Which teams get the view is set by `has_roadmap` on the `Team` dataclass
(playback only). The template itself never learns a team name: it hides the tab
when no roadmap payload was injected, the same way Recent Changes hides itself
when there is no digest.

#### Internal vs public — read this before publishing

**This repo is public and the site is served from GitHub Pages.** The roadmap
carries candid internal assessment: contested ownership, partner names,
individual owners. An item — or a condition aspect — can declare what to hold
back:

```yaml
- id: playready-content-providers
  consequence: >          # public, neutral phrasing
    PlayReady works, but few providers have enabled it.
  internal:
    withhold: [details]
    notes: >              # never rendered at any audience
      Canal+ is enabled. Netflix is the significant holdout.
```

```bash
python analyze_git.py                                # public subset (default)
python analyze_git.py --roadmap-audience internal    # everything — DO NOT COMMIT
```

`--roadmap-audience` defaults to **public**, and it has to. `internal` output is
a strict superset of `public`, `<slug>/index.html` is git-tracked, and the
weekly workflow runs `analyze_git.py` with no flags and then `git add -A
playback/`. So an internal default would publish precisely the fields the
annotation exists to protect.

Withheld fields are **marked** in the expanded row, not silently dropped, so a
reader can tell something was held back.

> **Currently outstanding:** `roadmap.yaml` has no `internal:` blocks yet, so
> the public build still renders everything. The mechanism works and is tested;
> the annotation pass has not been done. Annotate before this view is published.

#### Codec and container support — measured, not read from source

The support matrix used to be written by reading Firefox and Chromium source, and
that produced wrong claims: Chromium's `mkv_audio_codecs` lists PCM and AC-3, so
the table said Chrome plays both in Matroska. Shipping Chrome answers `no` to
both — the codec list says what the code mentions, not what a build ships.

So support is **measured** by asking browsers directly. There is a probe page in
the repo, published alongside the dashboard so anyone can re-run it by hand:

```
media-capabilities/index.html            # the probe page (public)
```

```bash
.venv/bin/python tools/media-caps/run_probe.py      # drive it across engines
.venv/bin/python tools/media-caps/build_matrix.py   # summarise what they said
```

`run_probe.py` writes one raw JSON per engine into `tools/media-caps/results/`,
and those files are tracked. The support table is **derived from them at render
time** — `analyze_git.py` rebuilds it every run — so there is no second file to
keep in step. An earlier version committed the derived table, which went stale the
moment the transform changed: regenerating the site rendered the *previous* shape
with every test green, because no test reads on-disk JSON. `build_matrix.py` is
now a read-only summary of the last probe.

`run_probe.py` drives Playwright's Gecko, real Chrome, and Playwright's WebKit.
Two caveats are recorded in the output and shown on the page: Playwright's WebKit
is **not Safari** — it lacks the platform codec integration Safari gets from the
OS — and Playwright's Gecko is not a shipping Firefox configuration. Neither
refresh is part of the weekly run; re-run them when you want fresh answers.

Each of the three surfaces names the API that answered it, because they are not
all the same generation:

| Surface | Measured with | Why |
|---|---|---|
| Playback | `decodingInfo({type:'file'})` | definite answer |
| Streaming | `decodingInfo({type:'media-source'})` | same |
| Recording | `MediaRecorder.isTypeSupported` | `encodingInfo({type:'record'})` **throws on Chrome** for every configuration tried; driving the column with it reported Chrome as recording nothing |
| WC decode | `VideoDecoder`/`AudioDecoder.isConfigSupported` | separate API, separate registry |
| WC encode | `VideoEncoder`/`AudioEncoder.isConfigSupported` | the only place encode support is visible — see below |

> **WebCodecs is a separate category because its answers differ.** In WebM,
> Firefox's `MediaRecorder` accepts `vp8` alone, so the Recording column shows VP9
> and AV1 as gaps — but `VideoEncoder.isConfigSupported` reports **yes** for both,
> at parity with Chrome and WebKit. Reporting MediaRecorder alone made "we cannot
> record VP9" read as "we cannot encode VP9", and only the first is true. The gap
> is the wiring between the two, not the encoder.

Codec-string spellings are **not** interchangeable, and the correct one depends on
the surface. Measured in WebM: `codecs="vp9"` gets `no` from Chrome's
`decodingInfo` and `yes` from its `MediaRecorder`; `codecs="vp09.00.10.08"` gets
the reverse. Picking either alone writes a false `no` into the table, so the probe
asks every accepted spelling and keeps the strongest answer per surface. `maybe`
outranks `no`, and errors rank below any real answer.

MediaCapabilities requires a codecs parameter, so it cannot answer a bare
container type at all — it errors. Bare rows therefore read `canPlayType` /
`MediaSource.isTypeSupported`. Those rows are how HLS support is visible, so
losing them loses HLS. A precise call that *throws* also falls back to the legacy
answer: WebKit raises a `TypeError` from `decodingInfo` for every Matroska
configuration while answering `canPlayType` for the same input, and reporting
that as unknown would hide a real measured `no` behind an API quirk.

An expanded card holds **two sections, Decoding and Encoding**, each browser-major
with its surfaces nested beneath it:

```
DECODING                          Firefox            Chrome             WebKit
Codec            String           File  MSE   WC     File  MSE   WC     File  MSE   WC
AV1              av01.0.04M.08    yes   yes   yes    yes   yes   yes    no    no    yes
VP8              vp8              –     –     yes    –     –     yes    –     –     yes

ENCODING                          Firefox        Chrome         WebKit
Codec            String           Rec   WC       Rec   WC       Rec   WC
AV1              av01.0.04M.08    no    yes      yes   yes      yes   yes
```

Five separate per-surface tables put the same codec on the page five times, and
answering "can we encode AV1 at all" meant cross-referencing two of them — which
is the comparison that matters, since Firefox's MediaRecorder refuses VP9 and AV1
while its WebCodecs encoder accepts both. Decoding and encoding are the two
questions actually asked, so they are the two sections.

A row lives or dies on the whole section, not per surface: VP8 in MP4 is played by
no engine yet encoded by all three through WebCodecs, so a per-surface rule would
have dropped a real answer. Where a surface has no engine support the cell reads
`–` — "nobody does this" must not look like three separate failures. The row's
verdict is the worst across its section, so a gap cannot hide behind parity beside
it.

Inside each section, rows are grouped into **Video codecs** and **Audio codecs**,
worst-first within each group and between them. Interleaving the two by verdict
alone meant reading past six audio codecs to reach AV1.

Combinations **no engine supports** are left out. They are not a gap, not an
overclaim and not a win, and the probe asks every codec a container could
plausibly carry, so there are a fair few — VP8 in MP4 is one, refused by all three
engines. `build_matrix.py` prints how many were dropped, since the page no longer
does.

Each container card carries a **coverage level** — `no support`, `partial`, or
`full support` — computed as how many of the combinations *any* engine supports we
support too, aggregated over the three surfaces. The per-surface chips show the
same ratio (`10/14` = 14 work somewhere, we have 10). An earlier version showed the
gap count and a behind/parity pair, which behaved like a boolean: 13 of 14 read the
same as 0 of 14, and the figure rose as things got worse. Containers sort by level,
then by how much is missing.

Each row carries a coloured bar on the left saying whether **we** are covered:
green where Firefox supports it, amber where another engine does and we do not,
slate where we accept something no other engine will. `ahead` and `parity` share
green on purpose — for a team reading this, both mean covered.

That took two tries to get right. Parity first rendered with no bar, which read as
a styling miss; then with a neutral grey one, which was worse — grey said "nothing
to report" on a row showing three `yes` answers. Encoding Firefox's position rather
than the shape of the agreement is what fixed it.

> **`powerEfficient` and `smooth` are collected but not shown.** Two reasons,
> either sufficient. `powerEfficient` is not a hardware-decode flag — Firefox and
> Chrome both report it for MP3, FLAC, Vorbis and AAC, and neither ships a
> hardware decoder for any of them. And both are **per device**: the answer
> describes whichever machine ran the probe, so a general cross-browser table
> would invite reading "Firefox has hardware AV1 decode" off one laptop's GPU.
> The probe page still reports them, which is where a per-device fact belongs.
> `hw-decode-matrix` therefore still needs a real per-configuration answer.

The probe also asks about type strings that **cannot exist** (`audio/flac;
codecs="ac-3"`). That found a Firefox conformance bug: `FlacDecoder::
IsSupportedType` never reads the codecs parameter
(`dom/media/flac/FlacDecoder.cpp:16-21`), so Firefox alone accepts three invalid
pairs that Chrome and WebKit both reject. This check is **not on the dashboard** —
it is reported by `build_matrix.py`:

```
conformance  3 impossible type(s) wrongly accepted:
               firefox-playwright: audio/flac; codecs="ac-3"
               firefox-playwright: audio/flac; codecs="alac"
               firefox-playwright: audio/flac; codecs="opus"
```

### Recent-change summaries

The Recent Changes tab's per-area overviews are generated in `analyze_git.py`. They're **optional** — with no backend the tab still renders the patch lists. `analyze_git.py` picks a backend from `REVIEW_STATS_SUMMARY_BACKEND`:

- **`copilot` (CI default) — no key stored.** Shells out to the [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-in-actions) (`npm install -g @github/copilot`), which authenticates with the workflow's own `GITHUB_TOKEN` given `permissions: copilot-requests: write` — nothing third-party is stored. Default model **`auto`** (Copilot picks) — pinned ids are gated by the token's Copilot plan and fail hard with `Model … is not available` before any request, so `auto` is the only universally-safe default; override with `REVIEW_STATS_SUMMARY_MODEL` if you have a known-good id. **Cost:** calls consume GitHub AI Credits, drawn from the repo owner's Copilot seat (*"In a personally-owned repository, usage is billed to the repository owner's Copilot seat."*). On **Copilot Free** that is a **200 credit/month** allowance with `overage_permitted: false` — when it runs out, calls simply fail and **you are never charged**; there is no payment method and overage is opt-in. Check yours with `curl -H "Authorization: token $(gh auth token)" https://api.github.com/copilot_internal/user | jq .quota_snapshots.chat`. Batching (below) puts a weekly refresh at **15-24 credits/month** measured, or ~92 in the worst case if auto-selection routes to a pricier model — comfortably inside Free either way. Without batching it is 190-470/month, i.e. over the limit. Note Free also restricts you to **auto model selection only**, so `REVIEW_STATS_SUMMARY_MODEL` cannot pin a model there — every pinned id returns `not available`. Copilot is an *agent*, not a completion endpoint, so the invocation deliberately declaws it: `--available-tools=` (empty) exposes no tools to the model — which also keeps their schemas out of every billed request — `--disable-builtin-mcps` skips spawning the GitHub MCP server, `--no-custom-instructions` stops a stray `AGENTS.md` rewording the overviews, and the process runs in a throwaway empty directory rather than the checkout.

  **Calls are batched** (`DEFAULT_BATCH_SIZE`, 12 areas per call), which is what makes this affordable. The CLI bills a **~12,000-token agent preamble on every invocation** while our actual payload is ~700 tokens per area, so cost is almost entirely fixed overhead — measured at 13,620 input tokens for a batch of 12 vs ~12,300 for a batch of 1. One call per area costs **0.36–2.25 credits/area**; a batch of 12 costs **0.059/area** — a 6–38x saving. A full batch takes ~52s. Each batch asks for a JSON object keyed by content hash (`build_batch_prompt`) and `parse_batch_response` maps it back, so the per-area cache granularity is unchanged — only the misses are batched, and an area the model skips stays uncached and retries next run.
- **`anthropic` (local, nicer prose).** Uses the Claude API (`ANTHROPIC_API_KEY`, `pip install anthropic`), default `claude-opus-4-8`. Run [`./refresh-overviews.sh`](refresh-overviews.sh) locally to regenerate, commit cache entries, and push. Use this if you want Opus-grade wording without spending AI Credits.
- **off / unset.** No generation; overviews already in the committed cache are still reused.
- **Anything else** — including `github`, retired when GitHub Models shut down on 2026-07-30 — is treated as a misconfiguration and emits a `::warning::`, rather than silently degrading to cache-only. A backend that never runs is as invisible as one that always fails.

**`.summary_cache/` is tracked in git** — each overview is cached by content hash (feature area + its set of patches), so any backend reuses overviews already generated (within a run and across runs when the same patch set recurs) and only generates genuinely-new areas. Delete the directory to force a full re-summarize.

**This content hash is the regeneration guard** — generation is *content-based*, not time-based. Re-running on the same day with no new landings makes **zero** LLM calls (every area is a cache hit); the next time a component's patch list changes (e.g. the window slides a day later, or new patches land) only the *changed* areas are regenerated. Each run logs `[summary] N generated, M reused from cache, K failed`. Cache misses are collected first and then batched, so the log's `N generated` counts areas while the credit cost tracks the number of *batches*.

**On generation failure**, that one area is left **without an overview** (it still shows its heading + patch list), the failure is **not cached** (so the next run retries it), and the refresh as a whole **still succeeds** — one flaky area never blocks the others or the run.

**If *every* call fails**, the run emits a `::warning::` annotation on the Actions summary instead of passing quietly. A backend can die outright (GitHub Models did), and a 100% failure rate that still exits green is otherwise invisible until someone notices blank overviews on the live site. It stays a warning rather than an error so the data refresh still gets committed.

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
