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

from reviewstats.commit_files import fetch_commit_files_cached
from reviewstats.github_commits import _get_auth_token, fetch_commits
from reviewstats.members import MEMBER_IDS
from reviewstats.metrics import (
    classify_landed_without_team_review_by_subdir,
    iso_week,
    primary_subdir,
)
from reviewstats.render import render_html
from reviewstats.report import build_report
from reviewstats.teams import PLAYBACK_TEAM


# Path / group / excludes flow from the team registry so adding a
# second team later is a pure config change — no constants to keep
# in sync across analyzers.
_DEFAULT_TEAM = PLAYBACK_TEAM
_DEFAULT_MONTHS = 6
_DEFAULT_REPO = "mozilla-firefox/firefox"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=_DEFAULT_REPO,
        help='GitHub repo "owner/name" (default: mozilla-firefox/firefox).',
    )
    parser.add_argument("--path", default=_DEFAULT_TEAM.path)
    parser.add_argument(
        "--months",
        type=int,
        default=_DEFAULT_MONTHS,
        help="Window size in months back from today.",
    )
    parser.add_argument("--group", default=_DEFAULT_TEAM.group)
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
        exclude_paths=_DEFAULT_TEAM.excludes,
    )
    if not commits:
        print(f"No commits found under {args.path} since {args.since}.")
        return 1

    now = datetime.now(timezone.utc)
    window_start = min(c.date for c in commits)
    window_end = max(c.date for c in commits)

    # For each commit that landed without any team-roster reviewer,
    # fetch the file list (cached) so we can build a per-subdir
    # breakdown for the pie chart.
    bad_commits: list = []
    for c in commits:
        has_group = any(
            r.is_group and r.name == args.group for r in c.reviewers
        )
        if has_group:
            continue
        if any(
            r.name in MEMBER_IDS for r in c.reviewers if not r.is_group
        ):
            continue
        bad_commits.append(c)

    cache_dir = out_dir / ".commit_files_cache"
    token = _get_auth_token()
    bad_with_files: list = []
    if bad_commits:
        print(
            f"Classifying {len(bad_commits)} 'without team review' "
            f"commits by primary subdir..."
        )
    for c in bad_commits:
        files = fetch_commit_files_cached(
            args.repo, c.sha, cache_dir=cache_dir, token=token,
        )
        bad_with_files.append((c, files))
    by_subdir = classify_landed_without_team_review_by_subdir(
        bad_with_files, path=args.path,
    )
    no_team_review_list = [
        {
            "sha": c.sha,
            "short_sha": c.sha[:12],
            "date": c.date.date().isoformat(),
            "author": c.author,
            "subject": c.subject,
            "reviewers": [
                {"name": r.name, "is_group": r.is_group}
                for r in c.reviewers
            ],
            "differential_revision": c.differential_revision,
            "primary_subdir": primary_subdir(files, path=args.path) or "(unknown)",
        }
        for c, files in bad_with_files
    ]
    no_team_review_list.sort(key=lambda r: r["date"], reverse=True)

    report = build_report(
        commits,
        group=args.group,
        path=args.path,
        window_start=window_start,
        window_end=window_end,
        generated_at=now,
        excludes=_DEFAULT_TEAM.excludes,
        no_team_review_by_subdir=by_subdir,
        no_team_review_list=no_team_review_list,
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
