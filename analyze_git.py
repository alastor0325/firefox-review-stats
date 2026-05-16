#!/usr/bin/env python3
"""Generate the dom/media reviewer-load report from git log only.

Reads commits from a local Firefox checkout, computes the metrics, and
writes:
  - data_git.json  : machine-readable report data
  - index.html     : self-contained HTML with Chart.js (CDN)

For the weekly cadence, run via refresh.sh; an `--archive-week` flag
also copies the JSON into archive/data_git_<YYYY-WW>.json.
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.git_log import parse_git_log_output, run_git_log
from reviewstats.metrics import iso_week
from reviewstats.render import render_html
from reviewstats.report import build_report


_DEFAULT_SINCE = "6 months ago"
_DEFAULT_PATH = "dom/media"
_DEFAULT_GROUP = "media-playback-reviewers"
_EXCLUDE_PATHS = ("dom/media/webrtc",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(Path.home() / "firefox"))
    parser.add_argument("--path", default=_DEFAULT_PATH)
    parser.add_argument("--since", default=_DEFAULT_SINCE)
    parser.add_argument("--group", default=_DEFAULT_GROUP)
    parser.add_argument(
        "--out", default=str(Path(__file__).resolve().parent)
    )
    parser.add_argument("--archive-week", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = run_git_log(
        args.repo, args.path, args.since, exclude_paths=_EXCLUDE_PATHS
    )
    commits = parse_git_log_output(raw)
    if not commits:
        print(f"No commits found under {args.path} since {args.since}.")
        return 1

    now = datetime.now(timezone.utc)
    window_start = min(c.date for c in commits)
    window_end = max(c.date for c in commits)

    report = build_report(
        commits,
        group=args.group,
        path=args.path,
        window_start=window_start,
        window_end=window_end,
        generated_at=now,
    )

    json_path = out_dir / "data_git.json"
    json_path.write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    html_path = out_dir / "index.html"
    html_path.write_text(render_html(report), encoding="utf-8")

    if args.archive_week:
        archive_dir = out_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        week_slug = iso_week(now)
        archived = archive_dir / f"data_git_{week_slug}.json"
        shutil.copyfile(json_path, archived)

    print(
        f"Wrote {json_path.relative_to(out_dir)} "
        f"and {html_path.relative_to(out_dir)} "
        f"({report['summary']['total_patches']} patches, "
        f"{report['summary']['group_tagged_patches']} tagged with "
        f"{args.group})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
