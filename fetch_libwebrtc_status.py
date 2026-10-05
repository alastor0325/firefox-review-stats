#!/usr/bin/env python3
"""Fetch which libwebrtc each supported Firefox release ships, for the WebRTC
page's version table.

Writes `<team>/data_libwebrtc.json`. Thin I/O only — the logic lives in
`reviewstats.libwebrtc`.

    python fetch_libwebrtc_status.py             # webrtc

Kept separate from analyze_git.py for the same reason as fetch_perf_metrics.py:
GitHub, chromiumdash and Gitiles being slow or down must not fail the weekly
report build. A failed or empty fetch leaves last week's file in place and exits
nonzero; with no file at all the page simply has no card.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.github_commits import _API, _get_auth_token
from reviewstats.github_http import get_json, get_text
from reviewstats.libwebrtc import collect_status, known_branch_dates

# Last week's table is the fallback, so give up fast rather than spend the
# default five 30s attempts per call across ~25 calls.
_HTTP = {"timeout": 15, "max_attempts": 2}


def collect(known: dict[int, str]) -> dict:
    token = _get_auth_token()
    return collect_status(
        lambda path: get_json(_API + path, token=token, **_HTTP),
        lambda url: get_text(url, **_HTTP),
        today=datetime.now(timezone.utc).date(),
        known_branch_dates=known,
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
        view = collect(known_branch_dates(previous))
    except Exception as e:  # noqa: BLE001 — any upstream failure degrades
        print(f"libwebrtc status fetch failed ({e}); leaving {path.name} alone.",
              file=sys.stderr)
        return 1
    if not view["rows"]:
        print(f"No supported releases in the response; leaving {path.name} alone.",
              file=sys.stderr)
        return 1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(view, indent=2), encoding="utf-8")
    print(f"Wrote {path}: " + ", ".join(
        f"{r['label']} M{r['milestone']}" for r in view["rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
