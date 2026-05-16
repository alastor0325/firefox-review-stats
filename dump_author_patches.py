#!/usr/bin/env python3
"""Dump a hierarchical per-author patch listing for verification.

Uses the same filters as analyze_git.py (skips Lando auto-format commits,
merge commits). Output: author_patches.txt in the project root.
"""

from collections import defaultdict
from pathlib import Path

from reviewstats.aliases import AUTHOR_ALIASES
from reviewstats.git_log import parse_git_log_output, run_git_log


REPO = str(Path.home() / "firefox")
PATH = "dom/media"
SINCE = "6 months ago"
EXCLUDE_PATHS = ("dom/media/webrtc",)
OUT = Path(__file__).resolve().parent / "author_patches.txt"


def main() -> None:
    raw = run_git_log(REPO, PATH, SINCE, exclude_paths=EXCLUDE_PATHS)
    commits = parse_git_log_output(raw)

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
    lines.append(f"Repo: {REPO}   Path: {PATH}   Since: {SINCE}")
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
