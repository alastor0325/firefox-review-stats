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
