---
name: add-media-metric
description: Add, repoint or remove a metric in the Media Health → Metrics subview. Use whenever METRICS in fetch_perf_metrics.py changes, or when a card reads stale, blank or surprising. Covers the checks that catch a metric which fetches fine and never paints.
---

# Adding a metric to Media Health

A metric can be wrong in three ways that all look like success: it never appears, it
appears with numbers from months ago, or it compares Firefox against a series that
stopped reporting. None of them fail a build. This is the procedure that catches each,
and the reasoning for it — every rule below is here because it already went wrong.

Follow the [dev loop](../firefox-review-stats-dev/skill.md) as well: failing test
first, `pytest tests/` green before commit.

---

## 1. Find the signature before writing any config

Do not guess a suite or subtest name. Ask Perfherder:

```bash
python - <<'PY'
import json, urllib.request
UA = "firefox-review-stats (media dashboard)"
BASE = "https://treeherder.mozilla.org/api/project/mozilla-central/performance"
def get(u):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers={"User-Agent": UA}), timeout=90).read())
sigs = get(f"{BASE}/signatures/?framework=13&subtests=1"
           f"&platform=macosx1470-64-shippable")
for k, v in sigs.items():
    if str(v.get("suite", "")).startswith("YOUR-SUITE-PREFIX"):
        print(k, v.get("suite"), "|", v.get("application"), "|", v.get("test"))
PY
```

Three API facts that produce wrong answers if forgotten:

- **The `suite=` query parameter does not filter.** It returns every signature on the
  platform. Filter client-side.
- **The dict keys ARE the signature ids.** `v["id"]` is not the id you want.
- **`/data/?signature_id=N` must be read via `data.values()`**, not `data[str(n)]`.
  Reading it by key returns nothing and looks exactly like "this suite has no data" —
  that misreading once produced a confident report that suites we actively chart were
  dead. `interval` must be a value Perfherder allows (86400 × a permitted day count).

**Confirm the signature has recent data, not just that it exists.** Perfherder
registers a signature when a test is *defined*; data follows only if it runs, and
lingers long after it stops.

## 2. Write the config entry

In `fetch_perf_metrics.py`'s `METRICS`. Required keys — a config test enforces all of
them, so a missing one fails at commit rather than at fetch:

| Key | Notes |
|---|---|
| `id` | unique; `family.thing` |
| `group` | cards sharing a group share one axis, unit, direction and platform |
| `title` | **put the resolution or condition in it** — see below |
| `suite` | exact Perfherder suite |
| `test` **or** `test_suffix` | never both |
| `platform` | usually `MAC_INTEL` |
| `unit`, `lower_is_better` | `lower_is_better` must be a real `bool` |
| `note` | `""` is fine when the group's first card explains the family |
| `baseline`, `baseline_label` | optional; point a card with no rival browser at a sibling of ours, so it shows e.g. `1.05× warm` instead of "no other browser measured yet" |

### `test` vs `test_suffix`

- `test` — exact subtest name (`seekedColdLatency`).
- `test_suffix` — anchored suffix, for suites that prefix every subtest with a
  per-codec string (`avc1.42001E (annexb) …`). **Give the whole measure including its
  variant.**
- Neither — the suite-level score.

`matches_test` in `reviewstats/perfmetrics.py` implements exactly those three modes and
nothing else. There is no substring match, deliberately. The WebCodecs cards spent 102 days on a
dead series because they matched a substring plus a hardcoded "exclude anything with
RGBX or I420" — written to keep the then-current variant, so when that variant died
the exclusion was blocking its only successors. `pick_signature` then resolved the
widened match by sample count, choosing the longest history: the corpse.

Suffix anchoring is an improvement, **not a guarantee** — the old bare name is itself
a suffix of its successors. `ambiguous_matches` is the actual tripwire.

### Titles must carry the condition

`ve-h264-rt-sd` is 640×480 while every sibling is 1920×1080, because Chrome refuses
WebCodecs H.264 encode above SD. Cards titled plain "H.264" and "VP9" invite reading a
resolution difference as a codec difference. If a card is not like-for-like with its
group, say so in the title and the note.

## 3. Fetch and read the warnings

```bash
python fetch_perf_metrics.py --days 30
```

Two warnings go to stderr. **Neither is fatal, and both mean the page is wrong:**

- `WARNING <id>: <app> matched N subtests, expected 1` — from `ambiguous_matches`. The
  upstream test was re-cut, so your `test_suffix` is now vague. Re-run step 1 and pick
  the exact variant.
- `WARNING N configured metric(s) produced no Firefox data` — from
  `unresolved_metrics`. The metric will not appear at all. Check the suite spelling, the
  platform, and whether the subtest was renamed. This is the guard for the most common
  mistake, and it is why "it ran without errors" is not evidence.

Both are printed to **stderr and nothing else** — they do not change the exit code,
because a partly-good table still beats no table in the weekly run. Read them.

Also check the written count: `is_safe_to_write` refuses a fetch returning nothing or
under half the previous metric count, but it does **not** notice a single row that
never arrived.

## 4. Render and look at it

```bash
python analyze_git.py
python -m pytest tests/
python -m http.server 8765   # http://127.0.0.1:8765/playback/
```

- **Look at the served page**, not the file on disk.
- Media Health is `display:none` until its tab is active, and Metrics is its default
  subview. Measuring geometry before clicking through returns zeros.
- **Expand the card.** The window, the per-browser rows and the source link are all in
  the expansion, and a collapsed card hides every fact worth checking.
- Static tests cannot see a runtime error and `node --check` only checks syntax. A page
  whose JavaScript throws on line 1 passes both — that happened with 841 tests green.
  Confirm no page errors:

```bash
python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.firefox.launch(headless=True); p = b.new_page()
    errs = []; p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("http://127.0.0.1:8765/playback/", wait_until="domcontentloaded")
    p.click('[data-view="health"]'); p.click('[data-health="metrics"]')
    p.wait_for_timeout(600)
    print("cards:", p.eval_on_selector_all("details.pm-card", "e => e.length"))
    print("PAGE ERRORS:", errs or "none")
    b.close()
PY
```

## 5. What you do not have to do

**A new `group` needs no template work.** Categories are derived from the data
(`METRICS.groups`, built by `build_metrics_view`), and a test asserts no group name is
hardcoded in the template. So a new family paints by itself — that part is structural,
not something to remember.

---

## Reading a card critically

Before believing a gap, check these — the numbers alone will not tell you:

- **Per-series freshness.** Each series' window ends at *its own* newest run, so a
  browser that stopped reporting still yields a full 30-day window, just an old one.
  `custom-car` stopped on 2026-06-28 and kept drawing bars beside current ones; on VP8
  its 45-day-old number beat current Chrome by 0.1 ms and took both the `best` label
  and the headline verdict. Stale rivals are now marked, drawn recessively, and barred
  from being comparator or leader while a current rival exists — but check
  `days_behind` per series when a result surprises you.
- **A brand-new rival needs no config change to appear.** The fetcher collects every
  application matching the suite/test/platform, so a browser that starts running an
  existing suite shows up on the next refresh — at whatever sample count it has, and it
  will carry the verdict from its first run. Check `n` in the expansion before quoting
  a factor. Only `DISPLAY_BROWSERS` (firefox, chrome, safari) is shown at all;
  `custom-car` is filtered because it duplicated Chrome to within a rounding error.
- **Sample counts differ by design.** Non-Firefox perf tasks have
  `run-on-projects: []` and are scheduled by cron, so Firefox lands ~246 runs a year
  where Chrome lands ~44. A thin rival series is normal, not suspicious.
- **The `!` marker means uncompared, dead, or mixed-window** — not "slightly noisy".
  Spread and low samples ride along as extra lines in the expansion but never earn the
  marker alone, so it stays meaningful.

### Where a new card will land

The subview has a **compared** half and a **Firefox only** section at the end, decided
**per card** by whether it has any rival. A Firefox-only suite (media-capabilities, and
seek's cold half) lands in the second section automatically — that is not a problem to
fix, and cards there deliberately do not carry a `!` for being uncompared. A group with
both kinds appears in both halves under the same title.

## The weekly refresh

`.github/workflows/refresh.yml` runs `fetch_perf_metrics.py --days 30` before
`analyze_git.py`, marked `continue-on-error`, and commits `playback/`. Tests in
`tests/unit/workflow/` and `tests/unit/roadmap/test_perfmetrics.py` pin that the step
exists and runs in that order — it once existed in no workflow at all, so the data only
refreshed when someone ran it by hand.

**The refresh cannot pick up a `METRICS` change on its own** — that is code, so it
lands with your commit. What it does pick up is fresh numbers for whatever is
configured at that commit. So verify locally; CI will not tell you the card is missing.
