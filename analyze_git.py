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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reviewstats.github_commits import fetch_commits
from reviewstats.metrics import iso_week
from reviewstats.render import render_html
from reviewstats.report import build_report


_DEFAULT_MONTHS = 6
_DEFAULT_PATH = "dom/media"
_DEFAULT_GROUP = "media-playback-reviewers"
_EXCLUDE_PATHS = ("dom/media/webrtc",)
_DEFAULT_REPO = "mozilla-firefox/firefox"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=_DEFAULT_REPO,
        help='GitHub repo "owner/name" (default: mozilla-firefox/firefox).',
    )
    parser.add_argument("--path", default=_DEFAULT_PATH)
    parser.add_argument(
        "--months",
        type=int,
        default=_DEFAULT_MONTHS,
        help="Window size in months back from today.",
    )
    parser.add_argument("--group", default=_DEFAULT_GROUP)
    parser.add_argument(
        "--out", default=str(Path(__file__).resolve().parent)
    )
    parser.add_argument("--archive-week", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fetch commits from GitHub directly — no local checkout needed.
    # ~30 days per month is good enough for a "since" cutoff; commits
    # within the actual window are then bounded by min/max of the
    # returned set.
    since = (
        datetime.now(timezone.utc) - timedelta(days=30 * args.months)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Fetching commits from github.com/{args.repo} (since {since})...")
    commits = fetch_commits(
        repo=args.repo,
        path=args.path,
        since=since,
        exclude_paths=_EXCLUDE_PATHS,
    )
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

    phab_path = out_dir / "data_phab.json"
    phab_data = (
        json.loads(phab_path.read_text(encoding="utf-8"))
        if phab_path.exists()
        else None
    )

    html_path = out_dir / "index.html"
    html_path.write_text(
        render_html(report, phab_data=phab_data), encoding="utf-8"
    )

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
