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

# A run-to-run spread this wide is louder than most differences worth detecting,
# so the page says so rather than plotting it as though it were solid.
NOISY_CV_PERCENT = 15.0

# Below this many runs, a median is thin evidence and the card says so. Roughly a
# month of daily runs, chosen so a newly landed suite warns until it has a month of
# history and then stops warning by itself -- no flag anyone has to remember to
# clear. Added because the warning rule looked at staleness and spread but not at
# sample count, so a metric with 15 runs sat beside one with 75 and read the same.
MIN_SAMPLES = 30

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
    series = {b: s for b, s in (metric.get("series") or {}).items() if s}
    firefox = series.get("firefox")
    if not firefox:
        # The whole view is "where Firefox stands"; a row without us says nothing.
        return None

    rivals = {b: s["median"] for b, s in series.items() if b != "firefox"}
    comparison = compare_to_firefox(
        firefox["median"], rivals,
        lower_is_better=bool(metric.get("lower_is_better", True)),
    )

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

    compared = sum(1 for m in rendered if m["compared"])
    return {
        "generated_at": str(raw.get("generated_at", "")),
        "window_days": int(raw.get("window_days", 30)),
        "metrics": rendered,
        "groups": groups,
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
