#!/usr/bin/env python3
"""Fetch which libwebrtc each supported Firefox release ships, for the WebRTC
page's version table.

Writes `<team>/data_libwebrtc.json`. Thin I/O only — the logic lives in
`reviewstats.libwebrtc`.

    python fetch_libwebrtc_status.py             # webrtc

Kept separate from analyze_git.py for the same reason as fetch_perf_metrics.py:
GitHub, chromiumdash and Gitiles being slow or down must not fail the weekly
report build. If the core Releases data can't be fetched, last week's file is
left in place and the script exits nonzero; the Next-update and Patch-stack
sections fall back to last week's copy on their own. With no file at all the
page simply has no libwebrtc tab.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.github_commits import _API, _get_auth_token
from reviewstats.github_http import get_json, get_text
from reviewstats.libwebrtc import collect_status

# Last week's table is the fallback, so give up fast rather than spend the
# default five 30s attempts per call across ~30-50 calls.
_HTTP = {"timeout": 15, "max_attempts": 2}


def _annotate(level: str, msg: str) -> None:
    """On GitHub Actions, an annotation on the run summary — the step is
    continue-on-error, so a log line alone would go unnoticed. Elsewhere,
    stderr."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        msg = msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{level} title=libwebrtc fetch::{msg}")
    else:
        print(msg, file=sys.stderr)


def report_fallback(key: str, exc: Exception) -> None:
    _annotate("warning", f"{key} fetch failed ({exc}); keeping last week's copy.")


def collect(previous: dict | None) -> dict:
    """Fetch this week's view. Last week's file supplies settled values and
    backs the optional sections; a section that falls back is reported, and
    keeps its own as_of so the page can say it is stale."""
    token = _get_auth_token()
    return collect_status(
        lambda path: get_json(_API + path, token=token, **_HTTP),
        lambda url: get_text(url, **_HTTP),
        today=datetime.now(timezone.utc).date(),
        previous=previous,
        on_error=report_fallback,
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team", default="webrtc",
                    help="Output team directory (default webrtc).")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.out) / args.team / "data_libwebrtc.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        previous = None

    try:
        view = collect(previous)
    except Exception as e:  # noqa: BLE001 — any upstream failure degrades
        _annotate("error", f"fetch failed ({e}); {path.name} keeps last week's data.")
        return 1
    if not view["rows"]:
        _annotate("error", f"no supported releases in the response; {path.name} "
                           "keeps last week's data.")
        return 1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(view, indent=2), encoding="utf-8")
    print(f"Wrote {path}: " + ", ".join(
        f"{r['label']} M{r['milestone']}" for r in view["rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
