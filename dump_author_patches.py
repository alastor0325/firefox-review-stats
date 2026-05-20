#!/usr/bin/env python3
"""Dump hierarchical per-author patch listings — one per registered
team — for verification.

Fetches commits directly from the GitHub mirror (no local clone).
Same filter rules as analyze_git.py: team-specific excludes,
Lando-author, merge, Revert subjects all skipped. Output: a
`<slug>/author_patches.txt` file per team.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reviewstats.aliases import AUTHOR_ALIASES
from reviewstats.github_commits import fetch_commits
from reviewstats.teams import TEAMS, Team


_DEFAULT_REPO = "mozilla-firefox/firefox"
_OUT_DIR = Path(__file__).resolve().parent


def _dump_for_team(team: Team, *, repo: str, since: str) -> None:
    commits = fetch_commits(
        repo=repo,
        paths=team.paths,
        since=since,
        exclude_paths=team.excludes,
    )
    if not commits:
        print(f"[{team.slug}] No commits found; skipping.")
        return

    by_author: dict[str, list] = defaultdict(list)
    for c in commits:
        by_author[c.author].append(c)
    for patches in by_author.values():
        patches.sort(key=lambda c: c.date, reverse=True)

    authors_sorted = sorted(
        by_author.items(), key=lambda kv: (-len(kv[1]), kv[0])
    )

    total = sum(len(v) for v in by_author.values())
    paths_str = ", ".join(team.paths)
    excludes_str = ", ".join(team.excludes) if team.excludes else "(none)"
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append(
        f"{team.display_name.upper()} AUTHOR-PATCH LISTING "
        "(raw author %an, no aliasing)"
    )
    lines.append(f"Source: github.com/{repo}   Paths: {paths_str}   Since: {since}")
    lines.append(f"Excluded paths: {excludes_str}")
    lines.append(
        f"Authors: {len(authors_sorted)}    Patches: {total}    "
        "(Lando-format / Lando-author / merge / Revert commits already excluded)"
    )
    lines.append("=" * 78)
    lines.append("")

    if AUTHOR_ALIASES:
        lines.append("Known aliases (applied in HTML report, NOT below):")
        merged: dict[str, list[str]] = defaultdict(list)
        for alias, canonical in AUTHOR_ALIASES.items():
            merged[canonical].append(alias)
        for canonical, aliases in sorted(merged.items()):
            lines.append(
                f"  {', '.join(sorted(aliases))}  ->  {canonical}"
            )
        lines.append("")
        lines.append("=" * 78)
        lines.append("")

    for idx, (author, patches) in enumerate(authors_sorted, 1):
        lines.append(f"[{idx:>2}] {author}  —  {len(patches)} patch(es)")
        lines.append("    " + "-" * 70)
        for c in patches:
            date_only = c.date.date().isoformat()
            lines.append(f"      {date_only}  {c.sha[:12]}  {c.subject}")
        lines.append("")

    team_dir = _OUT_DIR / team.slug
    team_dir.mkdir(parents=True, exist_ok=True)
    out_path = team_dir / "author_patches.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"[{team.slug}] Wrote {out_path.relative_to(_OUT_DIR)}  "
        f"({total} patches across {len(authors_sorted)} authors)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=_DEFAULT_REPO)
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()
    since = (
        datetime.now(timezone.utc) - timedelta(days=30 * args.months)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for team in TEAMS.values():
        _dump_for_team(team, repo=args.repo, since=since)


if __name__ == "__main__":
    main()
