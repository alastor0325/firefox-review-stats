"""Cross-browser metric comparison — the Metrics subview of Media Health.

Answers one question: **where does Firefox stand against other browsers on the
media metrics that actually run cross-browser today?** Numbers come from
Perfherder; this module is the pure layer between the raw samples and the page.

Four decisions worth knowing, each of which changed how this is written.

**Direction is declared here, not read from Perfherder.** Some metrics are better
lower (latency), some better higher (score). `lower_is_better` is `None` on most
signatures, so trusting it would silently invert a chart. It lives in the fetcher's
metric table instead.

**Comparison is against the strongest rival, not an average.** "We are behind
Chrome" is the fact worth acting on; averaging in a weaker browser flatters us.

**`n` travels with every summary.** Firefox runs far more often than Chrome — 75
against 13 over a 30-day window — so equal-looking marks would imply equal
confidence.

**Firefox-only metrics are kept and flagged, not dropped.** `media-seek` has no
rival measured yet. Showing it as an unopposed bar would read as a win; hiding it
would hide that the gap exists.
"""

import statistics as _st
from collections import defaultdict

# A run-to-run spread this wide is louder than most differences worth detecting,
# so the page says so rather than plotting it as though it were solid.
NOISY_CV_PERCENT = 15.0

# Below this many runs, a median is thin evidence and the card says so. Roughly a
# month of daily runs, chosen so a newly landed suite warns until it has a month of
# history and then stops warning by itself -- no flag anyone has to remember to
# clear. Added because the warning rule looked at staleness and spread but not at
# sample count, so a metric with 15 runs sat beside one with 75 and read the same.
MIN_SAMPLES = 30

# How far behind "now" a window may end before it is called stale. A few days is
# ordinary scheduling jitter; a suite that stopped weeks ago is a different claim.
STALE_AFTER_DAYS = 7

# The browsers this view compares against, and the only ones it shows. `custom-car`
# is a Chromium build that tracks Chrome, so its bar restated Chrome's to within a
# rounding error while carrying its own staleness caveat -- two lines of caveat for no
# extra information. Excluded here rather than in the template so the verdict, the
# plot and the warnings all agree about who is in the comparison.
DISPLAY_BROWSERS = ("firefox", "chrome", "safari")

# Perfherder's own graph view, so a reader can go from a card straight to the
# series it was computed from. Several `series` params put every browser on one
# graph. `timerange` only accepts a fixed set of values; 30 days is one of them.
PERFHERDER_GRAPHS = "https://treeherder.mozilla.org/perfherder/graphs"
PERFHERDER_PROJECT = "mozilla-central"
BROWSERTIME_FRAMEWORK = 13
_ALLOWED_TIMERANGES = (86400, 604800, 1209600, 2592000, 5184000, 7776000,
                       31536000)


def graph_url(series: dict, *, days: int, days_behind: int = 0) -> str:
    """Deep link to Perfherder for every browser charted on this metric.

    `days_behind` matters and was the bug: Perfherder's `timerange` counts back
    from *now*, not from the window we charted. A metric whose data stopped 100
    days ago needs a range covering the lag plus the window, or the graph opens
    empty -- which reads as "these numbers are fabricated", the exact opposite of
    what the link is for.

    Returns "" when no signature ids are known rather than a link that opens on
    nothing: a dead "see the data" link is worse than none.
    """
    ids = [s.get("signature_id") for s in (series or {}).values()
           if s.get("signature_id")]
    if not ids:
        return ""
    span = (days + max(0, days_behind or 0)) * 86400
    # Smallest allowed range that still covers the span; the largest if none do.
    bigger = [t for t in _ALLOWED_TIMERANGES if t >= span]
    timerange = min(bigger) if bigger else max(_ALLOWED_TIMERANGES)
    parts = [f"series={PERFHERDER_PROJECT},{i},1,{BROWSERTIME_FRAMEWORK}"
             for i in sorted(ids)]
    return f"{PERFHERDER_GRAPHS}?{'&'.join(parts)}&timerange={timerange}"


def summarize(values: list) -> dict | None:
    """Median, quartiles, spread and sample count for one browser's samples.

    Returns None for an empty series: zero would plot as a real measurement
    sitting at the origin.
    """
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None

    if len(nums) < 4:
        # `quantiles` needs at least two points and is meaningless on very few;
        # collapse the box to the median rather than invent a spread.
        median = _st.median(nums)
        p25 = p75 = median
    else:
        q = _st.quantiles(nums, n=4)
        median, p25, p75 = _st.median(nums), q[0], q[2]

    mean = _st.fmean(nums)
    cv = (100.0 * _st.pstdev(nums) / mean) if mean else 0.0
    return {
        "n": len(nums),
        "median": round(median, 1),
        "p25": round(p25, 1),
        "p75": round(p75, 1),
        "cv": round(cv, 1),
    }


def compare_to_firefox(
    firefox: float, others: dict, *, lower_is_better: bool
) -> dict:
    """How Firefox stands against the strongest other browser.

    `factor` is always >= 1 and reads as "this many times", with `ahead` saying
    which way. Expressing it that way lets one row of the summary read the same
    whether the metric is better-higher or better-lower — which is what makes a
    parity-centred bar honest across mixed directions.

    All three fields are None when no rival was measured. That is a distinct
    state from parity and must not render as a win.
    """
    measured = {b: float(v) for b, v in (others or {}).items() if v is not None}
    if not measured or not firefox:
        return {"ahead": None, "factor": None, "versus": None, "rival_count": 0}

    # Strongest rival by the metric's own direction.
    versus = min(measured, key=measured.get) if lower_is_better \
        else max(measured, key=measured.get)
    rival = measured[versus]
    if not rival:
        return {"ahead": None, "factor": None, "versus": None, "rival_count": 0}

    # advantage > 1 means Firefox is better, whichever way the metric runs.
    advantage = (rival / firefox) if lower_is_better else (firefox / rival)
    ahead = advantage >= 1.0
    factor = advantage if ahead else (1.0 / advantage)
    # rival_count so the page can say "best of 2" -- otherwise picking the
    # strongest rival silently hides that another browser was also measured.
    return {"ahead": ahead, "factor": round(factor, 2), "versus": versus,
            "rival_count": len(measured)}


def rival_breakdown(firefox: float, series: dict, *, lower_is_better: bool) -> list:
    """One entry per rival browser: its factor, its direction, and its caveats.

    `compare_to_firefox` answers "how do we stand against the strongest rival", which
    is the headline. It cannot say who else was measured -- the card read
    `1.80x ahead / chrome / (of 2)` while Safari, which we beat by more, went
    unnamed. This gives the page a line per rival instead of a count.

    Order is load-bearing: the first entry must be the browser the headline is
    computed from, or the big number and the list disagree. So entries sort current
    before stale, and only then by strength.

    Sample size does not gate a factor. A rival with a handful of runs still gets one;
    its `n` rides along and is shown in the expansion, so a thin comparison is
    labelled rather than withheld.
    """
    out = []
    for b, s in (series or {}).items():
        if b == "firefox" or not s:
            continue
        factor = ahead = None
        if firefox and s.get("median"):
            rival = float(s["median"])
            advantage = (rival / firefox) if lower_is_better else (firefox / rival)
            ahead = advantage >= 1.0
            factor = round(advantage if ahead else (1.0 / advantage), 2)
        out.append({
            "browser": b,
            "factor": factor,
            "ahead": ahead,
            "stale": bool(s.get("stale")),
            "n": int(s.get("n") or 0),
            "median": s.get("median"),
        })

    def key(r):
        med = float(r["median"] or 0)
        return (r["stale"], med if lower_is_better else -med)

    return sorted(out, key=key)


def select_recent_window(points: list, *, days: int, now_ts: float) -> dict:
    """Slice the most recent `days`-long window that actually contains data.

    The window LENGTH is fixed; only its position slides. That matters: widening
    the window instead would mean comparing a 30-day median against a 180-day
    one, which is not a like-for-like comparison. Sliding keeps every median
    computed over the same span of time, so a stale metric is still comparable to
    a fresh one -- it just describes an older period, which the caller reports.

    `points` are Perfherder samples: {"value": float, "push_timestamp": int}.
    """
    usable = [p for p in points or []
              if p.get("value") is not None and p.get("push_timestamp")]
    if not usable:
        return {"values": [], "window_end": None, "window_start": None,
                "days_behind": None}

    newest = max(p["push_timestamp"] for p in usable)
    span = days * 86400
    cutoff = newest - span
    values = [p["value"] for p in usable if p["push_timestamp"] > cutoff]
    return {
        "values": values,
        "window_end": newest,
        "window_start": cutoff,
        # How far behind "now" the window ends. Zero-ish means current.
        "days_behind": max(0, int((now_ts - newest) // 86400)),
    }


def matches_test(spec: dict, test_name) -> bool:
    """Does a Perfherder signature's subtest name belong to this metric?

    Three modes, in precedence order:

      * `test` -- an exact subtest name (`seekedColdLatency`).
      * `test_suffix` -- an anchored **suffix**, for suites that prefix every
        subtest with a per-codec string (`avc1.42001E (annexb) ...`). The suffix
        carries the whole measure *including* its input-source variant.
      * neither -- the suite-level score, which means a row with no subtest.

    Suffix rather than substring, because substring matching silently outlived a
    rename. When the WebCodecs encode subtests were split by frame source, the old
    bare name became a prefix of all three successors, so `contains` went on
    selecting a series that had stopped reporting.

    Anchoring the tail is a real improvement but not a guarantee: the bare name is
    itself a suffix of its successors, so a *vague* suffix still matches several
    variants. Precision comes from configuring the whole measure including its
    variant; `ambiguous_matches` is what notices when that stops being enough.
    """
    if spec.get("test") is not None:
        return test_name == spec["test"]
    suffix = spec.get("test_suffix")
    if suffix is not None:
        return bool(test_name) and str(test_name).endswith(suffix)
    return not test_name


def unresolved_metrics(metrics: list) -> list:
    """Ids of configured metrics that produced no Firefox series.

    A new metric whose `suite`, `platform` or subtest does not match anything is
    otherwise invisible: it is collected with an empty `series`, dropped by
    `_render_metric` for having no Firefox data, and the page simply renders one card
    fewer. `is_safe_to_write` does not help -- it guards against losing half the
    table, not against never gaining a row.

    Config order is preserved so the report reads like the METRICS list.
    """
    return [str(m.get("id", ""))
            for m in metrics or []
            if not ((m.get("series") or {}).get("firefox"))]


def ambiguous_matches(rows: list) -> dict:
    """Browsers for which a metric's match covers more than one distinct subtest.

    Returns `{browser: [subtest, ...]}`, sorted, empty when every browser resolved
    to exactly one subtest. Several signature *ids* for the same subtest is normal
    (build options) and not reported -- `pick_signature` handles that.

    Two different subtests under one card is never intended: it means the upstream
    test was re-cut and the config still describes the old shape. That is how the
    WebCodecs encode cards went stale. When their subtests split by frame source,
    the configured match widened from one row to four, and `pick_signature` resolved
    the tie on sample count -- so it chose the longest history, which was precisely
    the series that had just stopped.
    """
    by_app: dict[str, set] = defaultdict(set)
    for r in rows or []:
        app = (r or {}).get("application")
        if app:
            by_app[app].add(r.get("test"))
    return {a: sorted(t for t in names if t)
            for a, names in sorted(by_app.items()) if len(names) > 1}


def pick_signature(candidates: list) -> dict | None:
    """Choose one signature where several share a (browser, suite, test).

    They differ by build options, so blending their samples would mix builds.
    Most samples wins; lowest id breaks ties so a rebuild does not reshuffle the
    page for no reason.
    """
    usable = [c for c in candidates or [] if c.get("samples")]
    if not usable:
        return None
    return min(usable, key=lambda c: (-len(c["samples"]), c.get("id", 0)))


def _render_metric(metric: dict) -> dict | None:
    series = {b: s for b, s in (metric.get("series") or {}).items()
              if s and b in DISPLAY_BROWSERS}
    firefox = series.get("firefox")
    if not firefox:
        # The whole view is "where Firefox stands"; a row without us says nothing.
        return None

    # Each series' window is measured from its own newest point, so a browser that
    # stopped reporting still yields a full window -- just an old one. Mark it per
    # series: the card-level `stale` takes the freshest series and so reads false
    # while a weeks-old rival bar sits next to a current one.
    for b, s in series.items():
        db = s.get("days_behind")
        s["stale"] = db is not None and db > STALE_AFTER_DAYS
        # A lone sample has no spread. `summarize` yields cv 0.0 for it, which renders
        # as "CV 0%" and reads as rock-steady -- the opposite of what one run supports.
        s["cv_known"] = int(s.get("n") or 0) >= 2
    stale_browsers = sorted(b for b, s in series.items()
                            if b != "firefox" and s["stale"])

    lower_better = bool(metric.get("lower_is_better", True))

    # A stale rival must not be the headline comparator: on VP8 a 45-day-old
    # custom-car beat current Chrome by a rounding error and took the verdict. So
    # prefer current rivals -- but if every rival is stale, compare against them
    # anyway, because "nobody measures this" would be a bigger lie than an old
    # number, and the card carries the marker either way.
    # Every rival counts, whatever its sample size. A thin series is reported through
    # its `n` in the expansion rather than by withholding the comparison: a rough
    # comparison, labelled, is more use than none. (Earlier this excluded rivals under
    # five runs, which suppressed Safari and Chrome entirely on their first week.)
    rivals = {b: s["median"] for b, s in series.items() if b != "firefox"}
    fresh_rivals = {b: v for b, v in rivals.items() if not series[b]["stale"]}
    comparison = compare_to_firefox(
        firefox["median"], fresh_rivals or rivals, lower_is_better=lower_better,
    )

    # Who is actually ahead, decided here rather than in the template so freshness
    # is applied once. Same rule: a stale series cannot hold the "best" label while
    # a current one is on the card.
    ranked = [b for b in series if not series[b]["stale"]] or ["firefox"]
    leader = min(ranked, key=lambda b: (
        series[b]["median"] if lower_better else -series[b]["median"]))

    # One shared scale per metric so the marks are comparable; it has to reach
    # the slowest browser's p75 or that bar runs off the end.
    axis_max = max(
        [s["p75"] for s in series.values()] + [s["median"] for s in series.values()]
    )
    return {
        "id": metric.get("id", ""),
        "title": metric.get("title", ""),
        "group": metric.get("group", ""),
        "unit": metric.get("unit", ""),
        "lower_is_better": bool(metric.get("lower_is_better", True)),
        "platform": metric.get("platform", ""),
        "note": metric.get("note", ""),
        # Which sibling metric this card is measured against, if any. Resolved in a
        # second pass once every card exists.
        "baseline": metric.get("baseline"),
        "baseline_label": metric.get("baseline_label"),
        "self_label": metric.get("self_label"),
        # A metric can be measured on a wider window than the page's default when
        # its suite has stopped producing. Carried per metric so the row can say
        # so rather than silently mixing a 30-day median with a 180-day one.
        "window_days": int(metric.get("window_days") or 0),
        "stale": bool(metric.get("stale")),
        "days_behind": metric.get("days_behind"),
        "window_end": metric.get("window_end") or "",
        "series": series,
        "comparison": comparison,
        "compared": comparison["factor"] is not None,
        "axis_max": axis_max,
        "noisy": any(s["cv"] >= NOISY_CV_PERCENT for s in series.values()),
        # A comparison drawn across timeframes. Distinct from `stale`, which is about
        # the card as a whole being old; here our number is current and the rival's
        # is not, which flatters or damns us by accident.
        # One entry per rival so the verdict can name each instead of "best of N".
        "rivals": rival_breakdown(firefox["median"], series,
                                  lower_is_better=lower_better),
        "mixed_windows": bool(stale_browsers),
        "stale_browsers": stale_browsers,
        "leader": leader,
        # Firefox's own count decides, not the smallest across browsers. Rival
        # suites legitimately run far less often -- Chrome lands 13 runs where
        # Firefox lands 75 -- so a minimum-across-browsers rule fired on every card,
        # and a marker that is always on says nothing. The per-browser counts are in
        # the expansion for anyone weighing the comparison itself.
        "low_samples": _own_samples(series) < MIN_SAMPLES,
        "min_samples": _own_samples(series),
        "graph_url": graph_url(
            series,
            days=int(metric.get("window_days") or 30),
            days_behind=int(metric.get("days_behind") or 0),
        ),
    }


def _summary_key(m: dict) -> tuple:
    """Behind first, then by how far behind; uncompared rows last.

    Matches how the Roadmap subview orders its cards — worst first — so the two
    halves of Media Health read the same way.
    """
    c = m["comparison"]
    if c["factor"] is None:
        return (2, 0.0)
    return (0, -c["factor"]) if not c["ahead"] else (1, c["factor"])


def _own_samples(series: dict) -> int:
    """Firefox's run count, or the largest available if Firefox is absent."""
    ff = series.get("firefox")
    if ff:
        return int(ff.get("n") or 0)
    return max((int(s.get("n") or 0) for s in series.values()), default=0)


def baseline_comparison(metric: dict, by_id: dict) -> dict | None:
    """Ratio of a card against a sibling measurement of our own, or None.

    For a card no other browser reports, this is the only comparison available -- and
    often a useful one. `Decoder cold` has no rival and never will, but its ratio
    against `Decoder warm` is the cost of re-initialising the decoder, which is a real
    finding about our own code and says more than "no other browser measured yet".

    Declared per card (`baseline`, `baseline_label`) rather than inferred from the
    group: "the other metric here" is not a rule, and the capability-query group has
    seven cards with no such pairing.

    `worse` follows the metric's own direction, not the arithmetic, so it stays right
    on a higher-is-better measure. Deliberately NOT called `ahead`/`behind`: this is
    not a verdict against another browser and must not be coloured like one.
    """
    ref_id = metric.get("baseline")
    if not ref_id:
        return None
    sibling = (by_id or {}).get(ref_id)
    if not sibling:
        # The sibling can vanish -- a renamed suite, or a metric that resolved to
        # nothing. Leave the card plain rather than raising.
        return None
    ours = (metric.get("series") or {}).get("firefox") or {}
    theirs = (sibling.get("series") or {}).get("firefox") or {}
    a, b = ours.get("median"), theirs.get("median")
    if not a or not b:
        return None
    lower_better = bool(metric.get("lower_is_better", True))
    worse = (a > b) if lower_better else (a < b)
    factor = (a / b) if a >= b else (b / a)
    return {
        "against": sibling.get("id", ref_id),
        "label": str(metric.get("baseline_label") or sibling.get("title", "")),
        # Our own half of the pair, so the plot can label two rows rather than one
        # anonymous `firefox`.
        "self_label": str(metric.get("self_label") or "this"),
        "factor": round(factor, 2),
        "worse": worse,
        # The sibling's figures, so the expansion can draw it beside ours.
        "series": dict(theirs),
    }


def _split_groups(groups: list, *, compared: bool) -> list:
    """The same groups, holding only their compared or only their uncompared cards.

    Split per CARD, not per group. `Seek latency` holds a cold card no browser else
    reports and a warm card Chrome does, and they belong in different halves of the
    page: warm is a comparison, cold is a trend line. An earlier version split whole
    groups to keep the family together, which left the compared half showing a
    hatched card that could never be filled in.

    A group appears in both halves when it has both kinds, under the same title, and
    `axis_max` is recomputed per half so the bars scale to what is actually drawn.
    """
    out = []
    for g in groups:
        picked = [m for m in g["metrics"]
                  if bool(m["compared"] or m.get("charted")) is compared]
        if not picked:
            continue
        out.append({**g, "metrics": picked,
                    "axis_max": max(m["axis_max"] for m in picked)})
    return out


def build_metrics_view(raw: dict) -> dict:
    """Build the JSON payload for the Metrics subview."""
    rendered = [
        m for m in (_render_metric(x) for x in raw.get("metrics") or []) if m
    ]

    # Grouped for the detail charts, in the order the fetcher listed them, so a
    # codec family stays together and keeps a stable reading order.
    groups: list[dict] = []
    by_title: dict[str, dict] = {}
    for m in rendered:
        g = by_title.get(m["group"])
        if g is None:
            g = {"title": m["group"], "unit": m["unit"],
                 "lower_is_better": m["lower_is_better"],
                 "platform": m["platform"], "metrics": [], "axis_max": 0}
            by_title[m["group"]] = g
            groups.append(g)
        g["metrics"].append(m)
        g["axis_max"] = max(g["axis_max"], m["axis_max"])

    for g in groups:
        g["compared"] = any(m["compared"] for m in g["metrics"])

    # Second pass: a sibling ratio needs every card rendered first.
    by_id = {m["id"]: m for m in rendered}
    for m in rendered:
        b = baseline_comparison(m, by_id)
        m["baseline_comparison"] = b
        if b:
            # The plot draws two rows now, so the axis has to reach the further of
            # them or one bar runs off the end.
            m["axis_max"] = max(m["axis_max"],
                                b["series"].get("p75") or 0,
                                b["series"].get("median") or 0)
            # A card with a chart does not belong under "no other browser measures
            # these" -- that section is for cards with nothing to show. `compared`
            # stays False: this is a comparison, but not a cross-browser one.
            m["charted"] = True
            # "open these exact series" has to open BOTH rows the card draws. Built
            # from the same two series the plot uses, so the link cannot describe a
            # different chart than the one above it.
            m["graph_url"] = graph_url(
                {**m["series"], "_baseline": b["series"]},
                days=int(m.get("window_days") or 30),
                days_behind=int(m.get("days_behind") or 0),
            )

    compared = sum(1 for m in rendered if m["compared"])
    return {
        "generated_at": str(raw.get("generated_at", "")),
        "window_days": int(raw.get("window_days", 30)),
        "metrics": rendered,
        # The undivided list stays published so the split is a presentation concern
        # rather than a change to the data itself.
        "groups": groups,
        "groups_compared": _split_groups(groups, compared=True),
        "groups_firefox_only": _split_groups(groups, compared=False),
        "summary": sorted(rendered, key=_summary_key),
        "coverage": raw.get("coverage") or {"browsers": [], "rows": []},
        "counts": {
            "total": len(rendered),
            "compared": compared,
            "firefox_only": len(rendered) - compared,
        },
    }


# A refresh that loses most of the metrics is a broken query, not news. Perfherder
# renaming a suite is enough to cause it, and the result would be a blank Metrics
# subview with a fresh date on it.
_COLLAPSE_RATIO = 0.5


def is_safe_to_write(new_count: int, existing_count: int) -> tuple[bool, str]:
    """Whether a freshly fetched metric set should replace what is on disk.

    The fetcher already handles Perfherder being unreachable -- leave the file,
    exit nonzero. This covers the case it did not: a *successful* response with
    nothing usable in it, which took the success path and wrote an empty file over
    a good one. Suite renames on the Perfherder side do that, and the failure is
    invisible: the page renders, the subview is just empty.

    A first run legitimately has nothing to compare against, so an empty write is
    allowed only when there was nothing there before.
    """
    if existing_count <= 0:
        return True, ""
    if new_count <= 0:
        return False, (
            f"refusing to overwrite {existing_count} metrics with an empty "
            "result -- a successful fetch that found nothing usually means a "
            "suite was renamed, not that the data went away"
        )
    if new_count < existing_count * _COLLAPSE_RATIO:
        return False, (
            f"refusing to overwrite {existing_count} metrics with {new_count} "
            "-- that many fewer looks like a broken query rather than a refresh"
        )
    return True, ""
