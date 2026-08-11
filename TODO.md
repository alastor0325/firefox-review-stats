# Possible improvements

A running list of ideas. Each entry has a sketch of the approach and a rough effort estimate so we can pick off whatever's interesting without reinventing the design every time.

---

## From user observation

### "Last-fix without re-review" metric

> I often land code with fixes in response to the last review comment without having it re-reviewed, and I don't know if that is good or bad habit, but the data on how often that occurs might be enlightening.

**What it would measure**: how often a patch lands with author updates that came *after* the most recent reviewer action — i.e. the reviewer's accept covers an earlier diff, the author then revised based on the comment, and the revised version landed without a second look.

**Why interesting**: this isn't obviously good or bad. Sometimes it's "the reviewer asked for a trivial rename, I did it, landed". Sometimes it's "the reviewer asked for a structural change, I redesigned the patch, landed without re-confirm". The data tells us the distribution.

**Approach**: the per-revision timeline (`raw_data/D<n>.json`) already has every event. Add a derived field at aggregation time:

```python
# In wait_time.py or a new analyzer:
# For each revision:
#   accepts = [e for e in events if e.action == "accept" and e.actor != author]
#   if not accepts: skip
#   last_accept_ts = max(accepts, key=...).timestamp
#   author_updates_after = [e for e in events
#                           if e.actor == author
#                           and e.action == "update"
#                           and e.timestamp > last_accept_ts]
#   counts as "post-accept-update" if author_updates_after.
```

Then surface:
- A team-summary tile: "Landed with post-accept updates: N (X%)".
- A per-author tile in Member Profile: "Your post-accept-update rate".
- Maybe a foldable patch list with the deltas.

**Effort**: 1 day. Backend math is straightforward; frontend pattern matches the existing "Landed without team review" lazy reveal.

**Open questions**:
- Threshold: count *any* author update after accept, or only updates that change >N lines? Trivial-rename-after-accept probably shouldn't dominate the signal.
- Should we distinguish "post-accept comment + update" (responding to a fresh comment) from "silent update after stale accept"?

### "Media Health" view — a 5th view, playback only

> A new view about the media team specifically, so it won't happen on other
> teams. Two subviews: the performance metrics we collect from our media Raptor
> tests, and the roadmap tasks.

**What it would do**: add a fifth value to the `data-view` axis, sitting in the
toggle bar after `Recent Changes`, with a secondary toggle for its two subviews:

```
Team View | Member View | Wait Queue | Recent Changes | Media Health
                                                        └─ Performance | Roadmap
```

`Performance` leads and is the default. It answers two questions the existing
views cannot: *what is our current status*, and *how do we compare with other
browsers*.

**Why these two halves belong in one view rather than two**: the roadmap already
defines its `perennial` scope as *"held as metrics with targets, not a bug list,
and budgeted as a share of time"*. It carries a `metrics:` block of 8, and 6
items point into it — but **every single `target:` is `TBD`**, which the roadmap's
own handoff calls the blocker on that scope being usable at all. So Performance
isn't a neighbouring topic; it supplies the missing half of a scope Roadmap
cannot currently operate. Splitting them would keep that gap invisible.

**Why it's fine that this is playback-only**: the other four views are lenses on
review *process*, which is generic across teams — so a view missing from gfx or
webrtc would read as a bug. Product direction and codec performance aren't
generic, so this one reads as team-specific by nature rather than as an
unfinished rollout.

**Approach**:

- *View plumbing is an existing pattern, not new mechanism.* The template already
  gates a secondary toggle group per view — Period only appears in Team View, the
  week/month window only in Recent Changes (`templates/index.html.tmpl:526-538`).
  The Performance/Roadmap split is a third instance. Add `health` to the
  `data-view` matrix at `:504-517` and a `.health-only` class alongside
  `.team-only` / `.member-only` / `.queue-only` / `.recent-only`.
- *Gate the whole view to playback.* The three team pages share one template, so
  the toggle button and its sections need to render only for the media team. Needs
  a decision — see open questions.
- *Two generators, two cadences — this is the load-bearing constraint.* Roadmap is
  hand-curated YAML that is slow-moving and must **not** be auto-refreshed; its
  handoff is explicit that folding it into the weekly run means it either gets
  overwritten or needs a special-case no-op. Performance is Raptor data that is
  worthless *unless* refreshed. One view cannot have a single refresh policy.
  Keep them as separate generators writing separate JSON, sharing only the shell.
- *Roadmap subview source*: `~/firefox-bug-investigation/roadmap/roadmap.yaml`
  (47 items, 7 initiatives, 8 metrics) plus its two renderers, which per the
  handoff must be **restructured rather than copied** — I/O is currently mixed
  into rendering and there are no tests at all.
- *Performance subview source*: undecided, see open questions.

**A cheap first slice worth knowing about**: four of the eight metrics *already*
run nightly against other browsers — both video-playback-latency metrics carry
`cross_browser: [chrome, chrome-m, geckoview, fenix, firefox, safari]`, and both
seek metrics carry `[firefox, chrome, safari]`. The cross-browser comparison is
already being collected and nobody looks at it. So a first version that only
surfaces what already runs is much cheaper than the full Raptor build-out, and it
would make the case for the rest with real numbers.

**Effort**: the view plumbing and the Roadmap subview are each 1–2 days. The
Performance subview depends entirely on the data-source decision below, and on how
much of the Raptor improvement lands first — anywhere from an afternoon (deep-link
Perfherder) to a week (fetch, snapshot, chart, compare).

**Open questions**:

- *What feeds Performance?* Three shapes, and this decides the most: a generator
  that pulls the Perfherder API on a schedule and commits a snapshot (matches how
  the existing views work, stays static, gives history in git); fetching
  Perfherder client-side at page load (always current, but breaks offline and
  depends on their CORS and uptime); or deep-linking Perfherder's own comparison
  graphs (cheapest, least control over framing).
- *How is the view gated to playback?* A `TEAM_ID` conditional in the template, a
  per-team capability flag in `teams.py`, or generating the section and hiding it
  via CSS for other teams. The first two are honest; the third ships dead markup.
- *Do targets belong on the page before they exist?* Every target is currently
  `TBD`. Rendering 8 rows of `TBD` advertises the gap, which may be the point — or
  may make the subview look unfinished on day one.
- *Does Roadmap show `reach`?* It is currently computed and hidden along with the
  score. Reach is an input rather than arithmetic and is UNKNOWN on 27 of 47
  items; hiding it conceals that some items are ranked on guesses while
  higher-severity ones are unranked. Leaning toward showing reach, keeping score
  hidden.
- *Items have no `status` field.* Assigned, scheduled work and untouched
  speculation render as identical rows today. For a team-facing view this is the
  first thing a reader wants and the schema cannot express it.

### Additional time-range filters

> It might be interesting to have a couple of extra filters over 6-month / 1 week for the team view? Maybe a 3-month and a 12-month filter?

**What it would do**: the period toggle (currently `6-Month` / `Per-Week`) gains `3-Month` and `12-Month` options. The 6-month view stays the default landing state.

**Approach**:
- analyze_git.py / analyze_phab.py emit *multiple* JSON files per team — `data_git_3m.json`, `data_git_6m.json`, `data_git_12m.json` — by re-running `build_report` with different `since` cutoffs over the same fetched commit set. Same `raw_data/` is reused (Phab timelines are time-invariant).
- Template's period toggle gains two more buttons. JS swaps `DATA = TEAM_DATA[currentPeriod]` and re-renders charts.
- `Per-Week` stays as the most-recent-week slice (it already uses `phab.last_week` regardless of window).

**Effort**: 1–2 days. Main work is the chart-lifecycle refactor (Chart.js needs `chart.destroy()` before re-init when data changes) and the multi-file output plumbing.

**Cost**: 12-month window doubles the GitHub commit fetch and roughly doubles the Phab cold-cache cost the first time. Subsequent runs cached.

**Open questions**:
- Render all four datasets eagerly, or lazy-load `data_git_<n>m.json` on click? Lazy makes the initial page lighter but adds a network round-trip on toggle.
- Should the workflow's first run for a new team always populate all four windows, or just 6-month, with the others backfilled gradually?

---

## Observed during development, worth picking up

### `(unknown)` bucket in the pie

The "Landed without team review" subdir classifier has an `(unknown)` slice — usually 4–5 commits per team. These are 300+-file mega-refactors where the GitHub single-commit `files` array is truncated past the cap, so we can't tell which subdir they primarily touched.

**Fix**: paginate file lookup via `/repos/.../commits/<sha>` plus `Link` header (or use the GraphQL API, which doesn't have the 300-file cap). Adds one more API call per affected SHA — small.

**Effort**: half a day.

### WebRender vs gfx separation

gfx's "Landed without team review" count is high (462 / 1306 ≈ 35%), and the foldable patch list shows a lot of it is WebRender Rust patches reviewed by individuals (nical, gw, jnicol) without the `gfx-reviewers` group tag. Two options:

1. **Add gfx/wr to gfx's excludes**, attributing it to a new `webrender` team dashboard.
2. **Keep as-is** and treat it as a feature of the dashboard ("here's how often gfx work bypasses the group tag").

Needs a WebRender roster to do (1) properly. Otherwise (2) is fine and just needs better tooltip text explaining the high number.

**Effort**: option 1 is half a day; option 2 is 30 minutes of doc changes.

### Member-roster drift detection

Rosters in `teams.py` are manually maintained. Phab project membership changes; ours doesn't auto-sync. We learned the playback roster had "azebrowski" → "Andrew Zebrowski" but display name was stale.

**Approach**: a once-a-week job that scrapes the Phab project members page for each team and diffs against `teams.py.members`. Opens an issue when they differ.

**Effort**: 1 day. Requires authenticated Phab access (project pages are behind LDAP for non-public projects) — non-trivial.

### Sheriff / vendor-sync noise in bypass counts

A handful of "Landed without team review" entries are sheriff annotations (Sandor Molnar, Alexandru Marc disabling crashtests for greenness) or bulk vendor syncs. They land without explicit reviewers by convention, not because the team was bypassed.

**Approach**: extend `should_skip_commit` in `parse.py` with patterns for `a=sheriff`-style commits, vendor-sync subjects (`No bug — vendor libwebrtc`, etc.). Or surface them in a separate "Sheriff / vendor sync" bucket on the pie so they don't inflate the bad-signal number.

**Effort**: half a day. Already documented in the wiki as a known noise source.

### Sec-bug invisibility surface

Restricted Phab revisions (sec-bugs) return the login page when scraped anonymously. We silently drop them. For playback, ~30 of alwu's 96 authored patches over the window are sec-bugs and never appear on the wait-time histogram.

**Approach**: when `parse_html_to_raw` sees a login-page response, write a sentinel `{"d_number": "...", "restricted": true}` to `raw_data/` and surface a "N restricted revisions hidden" footnote on the wait-time section. Doesn't fix the data gap, but readers know it exists.

**Effort**: half a day.

### Trend comparison views

Per-week currently shows the most-recent week's data in isolation. A "this week vs the trailing 4-week median" comparison would surface whether things are getting slower or faster *right now*.

**Approach**: in `aggregate_wait_times`, add a `recent_vs_trailing` slice: percentiles for the most-recent week, plus the same percentiles for weeks `-2..-5`. Frontend renders both side by side.

**Effort**: half a day.

### Headless JS testing

Most rendering tests check for substrings in HTML; the JS itself isn't executed. A JS bug (e.g. a typo in a `getElementById`) would slip through. Could wire Playwright in test mode to load `index.html` and check that charts actually render.

**Effort**: 1–2 days, mostly for the test-infra setup.

### Mobile / narrow-viewport rendering

Hasn't been tested. Tables probably overflow; chart legends might wrap awkwardly. Low priority unless someone actually opens this on a phone.

**Effort**: half a day of CSS tweaking.

### Bot reviewers + the `?` flag

We skip Lando, but other automation flags exist (`?` for "review me but not landing yet"). Could matter for `landed_without_team_review` accuracy if any automation lands with a phantom reviewer.

**Effort**: an afternoon of looking at edge cases.

---

## Smaller polish items

- **Generated_at in local timezone** — currently UTC with a `+00:00` suffix. Add a small JS helper that also renders `new Date(generated_at).toLocaleString()` for readability.
- **RSS / Atom feed** of weekly snapshots, so people can subscribe instead of remembering to check the page.
- **Per-team favicons** — playback could keep the red `m`, webrtc could be blue, gfx could be green. Tiny win but visually distinct in a tab strip.
- **Dark mode** — the page is light-themed; a `prefers-color-scheme: dark` variant would be nice for late-night triage.
- **Accessibility audit** — ARIA roles on the toggle bar, alt text for the favicon, keyboard navigation through the Wait Queue table.

---

## Won't-do unless someone asks

- **Per-quarter / per-release windows** — beyond `--months N` (which 12-month already covers), arbitrary date pickers add a lot of UI for a use case nobody's mentioned.
- **Slack / email digests** — the page exists; if you want a Monday morning ping, set up a personal notification.
- **Per-member custom thresholds** — "alert me if my median wait > 5 days". Out of scope for a public dashboard.
