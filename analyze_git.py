#!/usr/bin/env python3
"""Generate the reviewer-load reports — one per registered team.

For each `Team` in `reviewstats.teams.TEAMS` we fetch commits from
GitHub for that team's paths, build the report, and write:

    <out>/<slug>/data_git.json
    <out>/<slug>/index.html

raw_data/ and the on-disk caches (.commit_files_cache,
.phab_html_cache) stay flat at the project root — they're keyed by
SHA / D-number and are safely shared across teams.

For the weekly cadence, run via refresh.sh; an `--archive-week`
flag also copies each team's JSON into archive/<slug>/data_git_<YYYY-WW>.json.
"""

import argparse
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reviewstats.commit_files import fetch_commit_files_cached
from reviewstats.github_commits import _get_auth_token, fetch_commits
from reviewstats.landing import render_landing_page
from reviewstats.metrics import (
    classify_landed_without_team_review_by_subdir,
    iso_week,
    primary_subdir,
)
from reviewstats.parse import (
    extract_bug_number,
    strip_bug_prefix,
    strip_reviewer_tag,
)
from reviewstats.recent_changes import deep_feature_bucket
from reviewstats.render import render_html
from reviewstats.report import RECENT_CHANGES_WINDOWS, build_report
from reviewstats.summarize import (
    DEFAULT_GITHUB_MODEL as _DEFAULT_GITHUB_MODEL,
    DEFAULT_SUMMARY_MODEL as _DEFAULT_SUMMARY_MODEL,
    make_anthropic_summarizer,
    make_github_models_summarizer,
    summarize_features,
)
from reviewstats.teams import TEAMS, Team


_DEFAULT_MONTHS = 6
_DEFAULT_REPO = "mozilla-firefox/firefox"


def _generate_for_team(
    team: Team,
    *,
    repo: str,
    since: str,
    out_dir: Path,
    cache_dir: Path,
    archive_week: bool,
    now: datetime,
    summarize_fn=None,
) -> None:
    """Build one team's report from scratch and write it to
    `<out_dir>/<team.slug>/`. raw_data/ and caches are shared
    across teams, hence the explicit `cache_dir` parameter so the
    caller controls placement (root, not per-team).

    `summarize_fn`, when supplied, generates the per-feature "what we
    did" summaries for the Recent Changes tab; None skips summarization
    (the tab still renders the change lists, just without summaries)."""
    print(
        f"[{team.slug}] Fetching commits from {repo} "
        f"paths={list(team.paths)} excludes={list(team.excludes)} "
        f"since {since}..."
    )
    commits = fetch_commits(
        repo=repo,
        paths=team.paths,
        since=since,
        exclude_paths=team.excludes,
    )
    if not commits:
        print(f"[{team.slug}] No commits found; skipping.")
        return
    # Only create the team subfolder once we know we'll write to it —
    # an empty <slug>/ directory on disk is a misleading signal that
    # the report exists but is broken.
    team_dir = out_dir / team.slug
    team_dir.mkdir(parents=True, exist_ok=True)

    window_start = min(c.date for c in commits)
    window_end = max(c.date for c in commits)

    # Identify commits that landed without any team-roster reviewer.
    member_ids = frozenset(team.members)
    bad_commits = []
    for c in commits:
        has_group = any(
            r.is_group and r.name == team.group for r in c.reviewers
        )
        if has_group:
            continue
        if any(
            r.name in member_ids for r in c.reviewers if not r.is_group
        ):
            continue
        bad_commits.append(c)

    token = _get_auth_token()

    # Memoise file lists for this run: the no-team-review pass and the
    # recent-changes pass below overlap on recently-landed SHAs, and
    # `fetch_commit_files_cached` re-reads its on-disk cache file every
    # call. An in-process dict keeps each SHA to a single disk read.
    _files_by_sha: dict[str, list] = {}

    def files_for(sha: str) -> list:
        files = _files_by_sha.get(sha)
        if files is None:
            files = fetch_commit_files_cached(
                repo, sha, cache_dir=cache_dir, token=token,
            )
            _files_by_sha[sha] = files
        return files

    bad_with_files: list = []
    if bad_commits:
        print(
            f"[{team.slug}] Classifying {len(bad_commits)} 'without team "
            f"review' commits by primary subdir..."
        )
    for c in bad_commits:
        bad_with_files.append((c, files_for(c.sha)))

    # Single-path teams bucket by sub-subdirectory; multi-path teams
    # bucket by which root path the patch touches most (coarser, but
    # the more useful distinction when a team spans multiple trees).
    if len(team.paths) == 1:
        by_subdir = classify_landed_without_team_review_by_subdir(
            bad_with_files, path=team.paths[0],
        )
        subdir_of = lambda fs: primary_subdir(fs, path=team.paths[0])
        # Single-root teams already bucket by immediate subdir — the
        # Recent Changes feed reuses that.
        recent_subdir_of = subdir_of
    else:
        by_subdir = classify_landed_without_team_review_by_subdir(
            bad_with_files, paths=team.paths,
        )
        subdir_of = lambda fs: primary_subdir(fs, paths=team.paths)
        # The no-team-review pie stays coarse (root-only), but the Recent
        # Changes feed buckets one level deeper so a multi-root team's
        # feature areas (e.g. gfx/wr, dom/media/webrtc/transport) are
        # meaningful rather than one giant root bucket.
        recent_subdir_of = lambda fs: deep_feature_bucket(fs, team.paths)

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
            "primary_subdir": subdir_of(files) or "(unknown)",
        }
        for c, files in bad_with_files
    ]
    no_team_review_list.sort(key=lambda r: r["date"], reverse=True)

    # Recent-changes feed: every in-scope landing in the most recent
    # window (the widest selectable slice), bucketed by feature area.
    # Unlike no_team_review this covers ALL landings — the tab answers
    # "what shipped", not "what bypassed review". File lists come from
    # the same SHA-keyed cache, so commits already fetched above for the
    # no-team-review pass don't hit the API twice.
    recent_cutoff = window_end - timedelta(days=max(RECENT_CHANGES_WINDOWS.values()))
    recent_commits = [c for c in commits if c.date >= recent_cutoff]
    recent_rows: list = []
    if recent_commits:
        print(
            f"[{team.slug}] Building recent-changes feed for "
            f"{len(recent_commits)} landings since {recent_cutoff.date()}..."
        )
    for c in recent_commits:
        files = files_for(c.sha)
        recent_rows.append(
            {
                "sha": c.sha,
                "short_sha": c.sha[:12],
                "date": c.date.date().isoformat(),
                "author": c.author,
                # Display title: drop the r= tag and the "Bug NNNN -"
                # prefix so each change reads as a description, not a bug ref.
                "subject": strip_bug_prefix(strip_reviewer_tag(c.subject)),
                "bug": extract_bug_number(c.subject),
                "differential_revision": c.differential_revision,
                "primary_subdir": recent_subdir_of(files) or "(unknown)",
            }
        )

    report = build_report(
        commits,
        group=team.group,
        paths=team.paths,
        window_start=window_start,
        window_end=window_end,
        generated_at=now,
        excludes=team.excludes,
        no_team_review_by_subdir=by_subdir,
        no_team_review_list=no_team_review_list,
        recent_rows=recent_rows,
        members=team.members,
    )

    # Annotate each Recent Changes feature area with a "what we did"
    # overview. Disk-cached by content hash, so the weekly refresh only
    # summarizes feature-sets it hasn't seen. No-op when summarize_fn is None.
    if "recent_changes" in report and summarize_fn is not None:
        print(f"[{team.slug}] Summarizing recent-change feature areas...")
        summarize_features(
            report["recent_changes"],
            cache_dir=out_dir / ".summary_cache",
            summarize_fn=summarize_fn,
        )

    json_path = team_dir / "data_git.json"
    json_path.write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    phab_path = team_dir / "data_phab.json"
    phab_data = (
        json.loads(phab_path.read_text(encoding="utf-8"))
        if phab_path.exists()
        else None
    )

    html_path = team_dir / "index.html"
    html_path.write_text(
        render_html(report, phab_data=phab_data), encoding="utf-8"
    )

    if archive_week:
        archive_dir = out_dir / "archive" / team.slug
        archive_dir.mkdir(parents=True, exist_ok=True)
        week_slug = iso_week(now)
        archived = archive_dir / f"data_git_{week_slug}.json"
        shutil.copyfile(json_path, archived)

    print(
        f"[{team.slug}] Wrote {json_path.relative_to(out_dir)} "
        f"and {html_path.relative_to(out_dir)} "
        f"({report['summary']['total_patches']} patches, "
        f"{report['summary']['group_tagged_patches']} tagged with "
        f"{team.group})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=_DEFAULT_REPO,
        help='GitHub repo "owner/name" (default: mozilla-firefox/firefox).',
    )
    parser.add_argument(
        "--months",
        type=int,
        default=_DEFAULT_MONTHS,
        help="Window size in months back from today.",
    )
    parser.add_argument(
        "--out", default=str(Path(__file__).resolve().parent)
    )
    parser.add_argument("--archive-week", action="store_true")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / ".commit_files_cache"

    since = (
        datetime.now(timezone.utc) - timedelta(days=30 * args.months)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc)

    # Pick the Recent Changes summarizer backend:
    #   REVIEW_STATS_SUMMARY_BACKEND=github  → GitHub Models (free, uses the
    #       workflow's own token; the CI default)
    #   =anthropic / ANTHROPIC_API_KEY set   → Claude API (local "nicer prose")
    #   =off, or nothing configured          → no generation; cached overviews
    #       in .summary_cache/ are still reused.
    backend = os.environ.get("REVIEW_STATS_SUMMARY_BACKEND", "").strip().lower()
    summarize_fn = None
    if backend == "off":
        print("Recent-change summaries disabled (backend=off); reusing cache only.")
    elif backend == "github":
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            model = os.environ.get("REVIEW_STATS_SUMMARY_MODEL", _DEFAULT_GITHUB_MODEL)
            summarize_fn = make_github_models_summarizer(token=token, model=model)
            print(f"Recent-change summaries via GitHub Models (model={model}).")
        else:
            print("backend=github but no GH_TOKEN/GITHUB_TOKEN — reusing cache only.")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        model = os.environ.get("REVIEW_STATS_SUMMARY_MODEL", _DEFAULT_SUMMARY_MODEL)
        try:
            summarize_fn = make_anthropic_summarizer(model=model)
            print(f"Recent-change summaries via Anthropic (model={model}).")
        except ImportError:
            print("ANTHROPIC_API_KEY set but `anthropic` not installed — cache only.")
    else:
        print("No summary backend configured — reusing cached overviews only.")

    for team in TEAMS.values():
        _generate_for_team(
            team,
            repo=args.repo,
            since=since,
            out_dir=out_dir,
            cache_dir=cache_dir,
            archive_week=args.archive_week,
            now=now,
            summarize_fn=summarize_fn,
        )

    landing_path = out_dir / "index.html"
    landing_path.write_text(
        render_landing_page(list(TEAMS.values())), encoding="utf-8"
    )
    print(f"Wrote {landing_path.relative_to(out_dir)} (landing page).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
