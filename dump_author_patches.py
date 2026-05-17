#!/usr/bin/env python3
"""Dump a hierarchical per-author patch listing for verification.

Fetches commits directly from the GitHub mirror (no local clone).
Same filter rules as analyze_git.py: webrtc subdir, Lando-author,
merge, Revert subjects all skipped. Output: author_patches.txt in the
project root.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reviewstats.aliases import AUTHOR_ALIASES
from reviewstats.github_commits import fetch_commits


_DEFAULT_REPO = "mozilla-firefox/firefox"
PATH = "dom/media"
EXCLUDE_PATHS = ("dom/media/webrtc",)
OUT = Path(__file__).resolve().parent / "author_patches.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=_DEFAULT_REPO)
    parser.add_argument("--months", type=int, default=6)
    args = parser.parse_args()
    since = (
        datetime.now(timezone.utc) - timedelta(days=30 * args.months)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits = fetch_commits(
        repo=args.repo, path=PATH, since=since, exclude_paths=EXCLUDE_PATHS,
    )

    by_author: dict[str, list] = defaultdict(list)
    for c in commits:
        by_author[c.author].append(c)
    for patches in by_author.values():
        patches.sort(key=lambda c: c.date, reverse=True)

    authors_sorted = sorted(
        by_author.items(), key=lambda kv: (-len(kv[1]), kv[0])
    )

    total = sum(len(v) for v in by_author.values())
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("DOM/MEDIA AUTHOR-PATCH LISTING (raw author %an, no aliasing)")
    lines.append(f"Source: github.com/{args.repo}   Path: {PATH}   Since: {since}")
    lines.append(f"Excluded paths: {', '.join(EXCLUDE_PATHS)}")
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

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}  ({total} patches across {len(authors_sorted)} authors)")


if __name__ == "__main__":
    main()
