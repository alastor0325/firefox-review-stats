# Media Health — how to update it

Everything the Media Health view shows comes from three independent sources with
three different cadences and three different failure modes. This is the operational
sequence for each, and the gotchas that have actually bitten.

The view is playback-only (`Team.has_roadmap`) and has two subviews: **Metrics**
(default) and **Roadmap**.

---

## Which thing did you change?

| You changed | Run | Cadence |
|---|---|---|
| A roadmap item, rating, or wording | `python analyze_git.py` then **commit** | whenever; **local only** |
| Nothing — just want fresh Raptor numbers | `python fetch_perf_metrics.py --days 30` | **weekly, automatic in CI** |
| Nothing — want fresh browser codec support | `tools/media-caps/run_probe.py` then `build_matrix.py` | quarterly, or after a browser release |

If you changed *code* rather than data, the [dev loop](../.claude/skills/firefox-review-stats-dev/skill.md)
applies: failing test first, `pytest tests/` green before commit.

---

## 1. Roadmap

**The source is not in this repo.** It is:

```
~/firefox-bug-investigation/roadmap/roadmap.yaml     # override with $ROADMAP_YAML
```

That repo is private, and **CI cannot see it**. This is the single most important
fact in this document, because it used to fail silently: with no YAML,
`_load_roadmap_view` returned `None`, the Media Health tab was hidden, and the
weekly job committed that page over the good one — deleting the whole view.

So a local run also writes `playback/data_roadmap.json`, the **public projection**,
which CI reads as a fallback. Consequences:

- **Editing the roadmap requires a local regeneration and a commit.** The weekly job
  cannot pick up YAML changes; it re-publishes the last committed projection.
- The write is gated on `audience == "public"`. An `--roadmap-audience internal` run
  does **not** overwrite it, so it cannot leak withheld fields.

```bash
# 1. edit ~/firefox-bug-investigation/roadmap/roadmap.yaml
# 2. regenerate (public is the default, and must stay the default)
python analyze_git.py

# 3. check what you are about to publish
git diff --stat playback/
python -m pytest tests/

# 4. commit BOTH repos - the YAML is the source of truth, the projection is derived
git -C ~/firefox-bug-investigation add -A && git -C ~/firefox-bug-investigation commit
git add playback/ && git commit
```

To read the unredacted version locally:

```bash
python analyze_git.py --roadmap-audience internal --out /tmp/internal-build
```

**Never commit an internal build.** `artifacts/` is gitignored for this reason; if
you write an internal build anywhere inside the repo, check `git status` before
committing.

### Rating an item

Ordering is **churn, then cheapest first**. Four fields, all judgement, all meant to
be argued with separately:

| Field | Values | Means |
|---|---|---|
| `churn` | `LEAVES` / `SECOND-BROWSER` / `ANNOYS` / `INVISIBLE` | does not doing it cost us the user |
| `user_value` | `4`…`1` | what a user gets (shown in the expansion, **does not order**) |
| `fills` | `BLOCKED` / `BROKEN` / `ABSENT-API` / `POLISH` | what kind of hole |
| `cost` | `S` / `M` / `L` / `XL` | effort |

Plus `rating_note`: one sentence of reasoning, which renders under "Why this
rating". A rating with no note is an assertion.

`user_value` deliberately does not affect the order, and `quick_win` deliberately
does not depend on it — a field that moves rows or lights markers without being
visible is the hidden-score problem the old `impact × reach` score had.

An item with `confidence: low` is flagged **needs measuring** and sorts last. It is
marked, not hidden: whether we can rank something is a fact about our evidence, not
about the work.

### Before you add an item

**Verify the premise against the tree.** A verification pass over 29 items found 7
whose premise was stale or wrong — two had already shipped. Cite `file:line` or a bug
number in `evidence`; an item with no evidence is a guess with a rating on it.

Three items have live Glean probes that answer their demand question, so query
rather than guess:

- `media_recorder.mime_type_query` — `dom/media/metrics.yaml:546`
- `hls.canplay_requested` — `dom/media/DecoderTraits.cpp:134-136` (all platforms)
- `mse_source_buffer_type` — `dom/media/mediasource/MediaSource.cpp:79-127`

### What must not be published

The repo is public and the site is GitHub Pages. Annotate anything sensitive:

```yaml
  internal:
    withhold: [details]
    notes: >
      Kept out of the public build entirely.
```

Categories that have needed withholding: **partner and provider commercial status**
(who has enabled us, who is holding out), **cross-team ownership disputes**, named
customer requests, and anything quoting internal planning documents or ticket IDs.

Code paths and pref names are fine — mozilla-central is public, and the citations are
what make the roadmap checkable.

A test guards real partner names out of `reviewstats/`, `tests/`, `templates/` and
`tools/`. It exists because the module docstring once illustrated the withhold
mechanism *using a real partner named as a holdout* — publishing, in source, exactly
what the mechanism protects.

---

## 2. Metrics (Perfherder)

Runs in the weekly job, before `analyze_git.py`, marked `continue-on-error`. Nothing
to do by hand unless you want it fresher:

```bash
python fetch_perf_metrics.py --days 30
```

- Plain HTTP to Treeherder, no browser, no auth, ~8s.
- Perfherder unreachable → previous file kept, exits nonzero. Weekly tolerates it.
- A *successful* fetch returning nothing, or under half the previous metric count, is
  **refused** — a suite rename upstream would otherwise blank the subview silently.
  `--allow-shrink` overrides, deliberately.
- Writes `playback/data_metrics.json`, which the weekly job already commits.

### Two ways a card lies without going blank

Both of these were live on the page, and neither showed up as an error.

**A renamed subtest.** The four WebCodecs encode cards read 102 days stale because
their subtests were re-cut upstream on 2026-05-02 — one measure per suite became
three, prefixed `RGBX canvas` / `I420 canvas` / `camera`. The config matched on a
`contains` substring plus a hardcoded "exclude anything with RGBX or I420", which was
written to keep the then-current bare variant; once that died the exclusion blocked
the only rows still reporting, and `pick_signature` resolved the widened match by
sample count — choosing the longest history, which was the corpse.

So subtests now match by **anchored suffix** (`test_suffix`), and `ambiguous_matches`
prints a warning if one card resolves to more than one distinct subtest. That warning
is the tripwire: it means the upstream test changed shape. Suffix anchoring alone is
not enough, because the old bare name is itself a suffix of its successors.

**A rival that stopped.** Each series' window ends at *its own* newest run, so a
browser that stopped reporting still produces a full 30-day window — just an old one.
`custom-car` stopped on 2026-06-28 and kept drawing bars beside current Firefox and
Chrome ones, and on VP8 its 45-day-old number beat current Chrome by 0.1 ms and took
both the `best` label and the headline verdict. Now: freshness is per series, a stale
rival is marked and made recessive but still plotted, and it cannot be the comparator
or the leader while a current rival exists. If *every* rival is stale the comparison
still runs against them — an old comparison, marked, beats claiming nobody measures it.

Neither problem is detectable from the numbers alone. When a cross-browser card looks
surprising, check `days_behind` per series before believing the gap.

---

## 3. Codec and container support (browser probe)

Measured by asking browsers, not by reading source — that is the whole point. An
earlier source-derived matrix claimed Chrome plays PCM and AC-3 in Matroska; shipping
Chrome answers no to both.

```bash
python tools/media-caps/run_probe.py      # drives the published probe page
python tools/media-caps/build_matrix.py   # read-only summary; nonzero on a bad run
python analyze_git.py                     # rebuilds the page from results/
```

**Requirements, none of them optional:**

- **Real Chrome**, not Playwright's Chromium — Chromium ships without H.264, AAC and
  HEVC, so probing it describes a Chrome that does not exist. Found per-OS, or set
  `CHROME_PATH`. A missing Chrome is an **error**, not a skip.
- **macOS**, to match the committed results. Codec support is platform-specific (HEVC
  comes from VideoToolbox), and `check_run` rejects a matrix assembled from two
  platforms. The workflow pins `macos-14` for the same reason.
- `python -m playwright install firefox webkit` for the other two engines.

There is **no derived file to commit**: the support table is rebuilt from
`tools/media-caps/results/*.json` at render time. A committed derived table went
stale the moment the transform changed and rendered the previous shape with every
test passing.

`.github/workflows/media-caps.yml` does this quarterly and on `workflow_dispatch`.
**It has never been executed** — dispatch it manually once and read the log before
trusting the schedule.

### Editing the probe page

`media-capabilities/index.html` is published so anyone can open it in their own
browser, including Safari, which Playwright cannot drive. `tools/media-caps/run_probe.py` loads that
exact file, so the dashboard and a hand-run agree by construction.

Three traps, all of which produced wrong cells:

- **Codec spelling is per surface.** In WebM, Chrome answers `no` to
  `decodingInfo({codecs:"vp9"})` and `yes` to `vp09.00.10.08`; its MediaRecorder does
  the exact opposite. The probe asks every accepted spelling and keeps the strongest
  answer.
- **A spelling can collide.** `1` is the WAV format tag for PCM, and Chrome also
  accepts `1` in Matroska — as a legacy id for a *different* codec. Matroska
  therefore has a per-container override. Aliases cannot express this.
- **One resolution is not an answer.** WebKit refuses AV1 at 1080p and accepts it at
  480p. Probing 1080p alone recorded "WebKit has no AV1". Every surface takes the best
  answer across resolution tiers.

Rule of thumb: if a cell says a major browser lacks something ubiquitous, the probe
is wrong, not the browser.

---

## Verifying a change

Static tests cannot see a runtime error, and `node --check` only checks syntax — a
page whose JavaScript throws on line 1 passes both. That happened: 841 tests green,
page blank, found from a screenshot.

```bash
python -m pytest tests/            # includes a real-browser run
python -m http.server 8765         # then open http://127.0.0.1:8765/playback/
```

- **Look at the served page, not the file on disk.** A stale copy or an unrefreshed
  derived file will otherwise convince you a change landed when it did not.
- The Media Health view is `display:none` until its tab is active, and the caps table
  lives under **Metrics**. Measuring geometry before clicking through returns zeros.
- Expand rows before auditing text. A collapsed table hides `details` and `evidence`
  from any scan you run.
