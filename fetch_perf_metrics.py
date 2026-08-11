#!/usr/bin/env python3
"""Fetch media Raptor numbers from Perfherder for the Metrics subview.

Writes `<team>/data_metrics.json`. Thin I/O only — the aggregation lives in
`reviewstats.perfmetrics`.

    python fetch_perf_metrics.py                 # 30-day window, playback
    python fetch_perf_metrics.py --days 30

Kept separate from analyze_git.py because this is a different data source with a
different failure mode: Perfherder being slow or down must not fail the weekly
report build. A missing data_metrics.json degrades to "no Metrics subview".

Three things about the API that are not obvious and are handled here:

  * **The `suite=` query parameter does not filter.** Passing it still returns
    every signature on the platform, including Speedometer subtests. Filtering
    happens client-side on the `suite` field.
  * **`lower_is_better` is `None` on most signatures**, so direction is declared
    in METRICS below rather than read from the API. Trusting the API would
    silently invert a chart.
  * **Several signature ids share a (browser, suite, test)**, differing by build
    options. `pick_signature` chooses one rather than blending builds.

Power is deliberately absent. The only media-named suite with power data is the
WebCodecs encode suite, where the number is whole-task system energy that nobody
designed as a media measurement — see
media-raptor-cross-browser-cpu-power-investigation.md.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.perfmetrics import (
    is_safe_to_write,
    pick_signature,
    select_recent_window,
    summarize,
)

PROJECT = "mozilla-central"
BASE = f"https://treeherder.mozilla.org/api/project/{PROJECT}/performance"
BROWSERTIME_FRAMEWORK = 13
UA = "firefox-review-stats (media dashboard; github.com/alastor0325/firefox-review-stats)"

MAC_INTEL = "macosx1470-64-shippable"

# What to chart, and in what order. `group` gathers metrics onto one shared scale.
# `lower_is_better` is authoritative here — see the module docstring.
METRICS = [
    {"id": "vpl.h264", "group": "First frame latency", "title": "H.264",
     "suite": "vpl-h264", "test": "estimatedFirstFrameLatency",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True,
     "note": "Local 1080p file, time to first painted frame."},
    {"id": "vpl.vp9", "group": "First frame latency", "title": "VP9",
     "suite": "vpl-vp9", "test": "estimatedFirstFrameLatency",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True, "note": ""},
    {"id": "vpl.av1", "group": "First frame latency", "title": "AV1",
     "suite": "vpl-av1", "test": "estimatedFirstFrameLatency",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True, "note": ""},
    {"id": "webaudio.score", "group": "Web Audio score", "title": "Score",
     "suite": "webaudio", "test": None,
     "platform": MAC_INTEL, "unit": "score", "lower_is_better": False,
     "note": "Web Audio graph performance, not video playback. The only media "
             "suite that runs on Safari."},
    # WebCodecs encode: the only media suite family running on three browsers.
    # `frame-to-frame mean (non key)` is per-frame encode time, which is the
    # throughput question. The canvas-source variants are excluded so all three
    # browsers are measured on the same input path.
    {"id": "ve.h264", "group": "WebCodecs encode", "title": "H.264 realtime",
     "suite": "ve-h264-rt-sd", "test": None,
     "test_contains": "realtime encode - frame-to-frame mean (non key)",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True,
     "note": "Per-frame encode time, VideoEncoder realtime mode."},
    {"id": "ve.vp8", "group": "WebCodecs encode", "title": "VP8 realtime",
     "suite": "ve-vp8-rt", "test": None,
     "test_contains": "realtime encode - frame-to-frame mean (non key)",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True, "note": ""},
    {"id": "ve.vp9", "group": "WebCodecs encode", "title": "VP9 realtime",
     "suite": "ve-vp9-rt", "test": None,
     "test_contains": "realtime encode - frame-to-frame mean (non key)",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True, "note": ""},
    {"id": "ve.av1", "group": "WebCodecs encode", "title": "AV1 realtime",
     "suite": "ve-av1-rt", "test": None,
     "test_contains": "realtime encode - frame-to-frame mean (non key)",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True, "note": ""},
    {"id": "media-seek.cold", "group": "Seek latency", "title": "Decoder cold",
     "suite": "media-seek", "test": "seekedColdLatency",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True,
     "note": "256x144 VP9 clip. Firefox only so far."},
    {"id": "media-seek.warm", "group": "Seek latency", "title": "Decoder warm",
     "suite": "media-seek", "test": "seekedWarmLatency",
     "platform": MAC_INTEL, "unit": "ms", "lower_is_better": True, "note": ""},
]

# Which suites run on which browsers, so the page can show what cannot be
# compared at all. Measured from the signature dump, not read off config.
COVERAGE_SUITES = [
    ("vpl", "vpl-", "First frame latency"),
    ("ve", "ve-", "WebCodecs encode"),
    ("webaudio", "webaudio", "Web Audio"),
    ("media-seek", "media-seek", "Seek latency"),
    ("youtube-playback", "youtube-playback", "Certification-suite playback"),
    ("media-capabilities", "media-capabilities", "decodingInfo() latency"),
]
COVERAGE_BROWSERS = ["firefox", "chrome", "safari", "custom-car"]


def _get(url: str, timeout: int = 90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_signatures(platform: str) -> dict:
    q = urllib.parse.urlencode(
        {"framework": BROWSERTIME_FRAMEWORK, "subtests": 1, "platform": platform}
    )
    return _get(f"{BASE}/signatures/?{q}")


# How far back to look for data. The reported window stays `--days` long; this is
# only the search horizon, because a suite that has stopped producing still has a
# real 30-day window further back. Widening the window itself would mean
# comparing a 30-day median against a 180-day one, which is not like-for-like.
SEARCH_DAYS = 365


def fetch_points(signature_id: int, days: int) -> list:
    """Samples with their push timestamps, so staleness can be reported."""
    q = urllib.parse.urlencode(
        {"signature_id": signature_id, "interval": days * 86400}
    )
    data = _get(f"{BASE}/data/?{q}")
    return [
        p for series in data.values() for p in series
        if p.get("value") is not None
    ]


def fetch_samples(signature_id: int, days: int) -> list:
    q = urllib.parse.urlencode(
        {"signature_id": signature_id, "interval": days * 86400}
    )
    data = _get(f"{BASE}/data/?{q}")
    return [
        p["value"] for series in data.values() for p in series
        if p.get("value") is not None
    ]


def build_coverage(signatures: dict) -> dict:
    """Which browsers each suite family actually runs on."""
    seen = defaultdict(set)
    for v in signatures.values():
        if not isinstance(v, dict):
            continue
        suite, app = str(v.get("suite") or ""), v.get("application")
        if not app:
            continue
        for key, prefix, _ in COVERAGE_SUITES:
            if suite == prefix or suite.startswith(prefix):
                seen[key].add(app)
    return {
        "browsers": COVERAGE_BROWSERS,
        "rows": [
            {"suite": key, "label": label,
             "measured": [b for b in COVERAGE_BROWSERS if b in seen.get(key, ())]}
            for key, _, label in COVERAGE_SUITES
        ],
    }


def collect(days: int) -> dict:
    platforms = sorted({m["platform"] for m in METRICS})
    sigs: dict[str, dict] = {}
    for p in platforms:
        print(f"Fetching signatures for {p}...")
        sigs.update(fetch_signatures(p))

    out_metrics = []
    for spec in METRICS:
        # The API's suite filter is a no-op, so match here.
        candidates = defaultdict(list)
        for v in sigs.values():
            if not isinstance(v, dict):
                continue
            if v.get("suite") != spec["suite"]:
                continue
            if v.get("machine_platform") != spec["platform"]:
                continue
            want, contains = spec["test"], spec.get("test_contains")
            got = v.get("test")
            if contains is not None:
                # ve-* prefixes every measure with its own codec string, so match
                # on the measure name and exclude the canvas-source variants.
                if not got or contains not in got:
                    continue
                if any(x in got for x in ("RGBX", "I420")):
                    continue
            elif want is not None:
                if got != want:
                    continue
            elif got:
                continue  # want the suite-level score, not a subtest
            app = v.get("application")
            if app:
                candidates[app].append(v)

        series = {}
        window_end, days_behind = None, None
        now_ts = datetime.now(timezone.utc).timestamp()
        for app, rows in candidates.items():
            enriched = []
            for r in rows:
                try:
                    # One wide fetch, then slide a fixed-length window over it.
                    pts = fetch_points(r["id"], SEARCH_DAYS)
                except (urllib.error.URLError, TimeoutError) as e:
                    print(f"  ! {spec['id']} {app} signature {r['id']}: {e}")
                    continue
                w = select_recent_window(pts, days=days, now_ts=now_ts)
                enriched.append({"id": r["id"], "samples": w["values"],
                                 "window": w})
            chosen = pick_signature(enriched)
            if not chosen:
                continue
            sm = summarize(chosen["samples"])
            if sm:
                sm["signature_id"] = chosen["id"]
                series[app] = sm
                w = chosen["window"]
                if window_end is None or (w["window_end"] or 0) > window_end:
                    window_end = w["window_end"]
                days_behind = (w["days_behind"] if days_behind is None
                               else min(days_behind, w["days_behind"]))

        # "Stale" means the 30-day window ended a while ago, not that the window
        # is a different length. A few days behind is normal scheduling jitter.
        stale = bool(series) and (days_behind or 0) > 7
        if stale:
            print(f"       ^ STALE: newest data is {days_behind}d old; "
                  f"showing the {days}d window ending then")
        out_metrics.append({
            k: spec[k] for k in
            ("id", "group", "title", "unit", "lower_is_better", "platform", "note")
        } | {
            "series": series,
            "window_days": days,
            "stale": stale,
            "days_behind": days_behind,
            "window_end": (datetime.fromtimestamp(window_end, timezone.utc)
                           .date().isoformat()) if window_end else None,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window_days": days,
        "source": f"{BASE}/data/ (framework {BROWSERTIME_FRAMEWORK})",
        "metrics": out_metrics,
        "coverage": build_coverage(sigs),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30,
                    help="Rolling window in days (default 30).")
    ap.add_argument("--team", default="playback",
                    help="Output team directory (default playback).")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--allow-shrink", action="store_true",
                    help="Write even if the metric count collapsed (see "
                         "reviewstats.perfmetrics.is_safe_to_write).")
    args = ap.parse_args(argv)

    try:
        data = collect(args.days)
    except (urllib.error.URLError, TimeoutError) as e:
        # Perfherder being unreachable must not fail the build; the page simply
        # renders without the Metrics subview until the next run.
        print(f"Perfherder unreachable ({e}); leaving data_metrics.json alone.",
              file=sys.stderr)
        return 1

    path = Path(args.out) / args.team / "data_metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    # A successful response with nothing usable in it must not blank the subview.
    existing = 0
    if path.exists():
        try:
            existing = len(
                (json.loads(path.read_text(encoding="utf-8")) or {})
                .get("metrics") or [])
        except (OSError, json.JSONDecodeError):
            existing = 0
    ok, why = is_safe_to_write(len(data.get("metrics") or []), existing)
    if not ok and not args.allow_shrink:
        print(f"{why}. Pass --allow-shrink if this is intended.",
              file=sys.stderr)
        return 1

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    n = len(data["metrics"])
    compared = sum(1 for m in data["metrics"] if len(m["series"]) > 1)
    print(f"Wrote {path.name}: {n} metrics, {compared} with a cross-browser "
          f"comparison, {args.days}-day window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
