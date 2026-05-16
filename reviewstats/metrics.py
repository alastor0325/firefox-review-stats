"""Pure aggregation metrics over parsed commits."""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Iterable, Protocol

from reviewstats.aliases import canonicalize_author
from reviewstats.parse import Reviewer


class _CommitLike(Protocol):
    reviewers: list[Reviewer]
    date: datetime
    author: str


def iso_week(date: datetime) -> str:
    iso = date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _has_group(commit: _CommitLike, group: str) -> bool:
    return any(r.is_group and r.name == group for r in commit.reviewers)


def _individuals(commit: _CommitLike) -> list[str]:
    return [r.name for r in commit.reviewers if not r.is_group]


def _keep(name: str, members: frozenset[str] | None) -> bool:
    return members is None or name in members


def count_by_individual(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str] | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for c in commits:
        if not _has_group(c, group):
            continue
        counts.update(n for n in _individuals(c) if _keep(n, members))
    return dict(counts)


def non_member_reviewer_counts(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for c in commits:
        if not _has_group(c, group):
            continue
        counts.update(n for n in _individuals(c) if n not in members)
    return dict(counts)


def routing_breakdown(commits: Iterable[_CommitLike], *, group: str) -> dict[str, int]:
    total = 0
    group_tagged = 0
    group_with_individual = 0
    group_only = 0
    for c in commits:
        total += 1
        if _has_group(c, group):
            group_tagged += 1
            if _individuals(c):
                group_with_individual += 1
            else:
                group_only += 1
    return {
        "total": total,
        "group_tagged": group_tagged,
        "group_with_individual": group_with_individual,
        "group_only": group_only,
    }


def sole_reviewer_counts(
    commits: Iterable[_CommitLike],
    *,
    members: frozenset[str] | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for c in commits:
        if len(c.reviewers) != 1:
            continue
        only = c.reviewers[0]
        if only.is_group or not _keep(only.name, members):
            continue
        counts[only.name] += 1
    return dict(counts)


def weekly_counts_per_reviewer(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str] | None = None,
) -> dict[str, dict[str, int]]:
    """{ "2026-W20": { "padenot": 5, ... }, ... }"""
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in commits:
        if not _has_group(c, group):
            continue
        week = iso_week(c.date)
        for name in _individuals(c):
            if _keep(name, members):
                out[week][name] += 1
    return {wk: dict(d) for wk, d in out.items()}


def total_reviews_per_member(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str],
) -> list[dict]:
    in_group: Counter[str] = Counter()
    out_of_group: Counter[str] = Counter()
    for c in commits:
        bucket = in_group if _has_group(c, group) else out_of_group
        bucket.update(n for n in _individuals(c) if n in members)
    names = set(in_group) | set(out_of_group)
    rows = [
        {
            "name": n,
            "in_group": in_group.get(n, 0),
            "out_of_group": out_of_group.get(n, 0),
            "total": in_group.get(n, 0) + out_of_group.get(n, 0),
        }
        for n in names
    ]
    rows.sort(key=lambda r: -r["total"])
    return rows


def author_patch_counts(
    commits: Iterable[_CommitLike],
) -> dict[str, int]:
    """Count unique patches (D-numbers) per author.

    A patch that's backed out and re-landed shows up as multiple
    commits with the same Differential Revision — we count it once.
    Commits without a Differential Revision (rare for filtered
    dom/media) count individually.
    """
    seen: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    for c in commits:
        author = canonicalize_author(c.author)
        d = getattr(c, "differential_revision", None)
        if d:
            if d in seen[author]:
                continue
            seen[author].add(d)
        counts[author] += 1
    return dict(counts)


def author_reviewer_pairs(
    commits: Iterable[_CommitLike],
    *,
    members: frozenset[str] | None = None,
) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for c in commits:
        author = canonicalize_author(c.author)
        for name in _individuals(c):
            if _keep(name, members):
                out[author][name] += 1
    return {a: dict(d) for a, d in out.items() if d}


def reviewer_to_authors(
    commits: Iterable[_CommitLike],
    *,
    members: frozenset[str],
) -> dict[str, list[dict]]:
    """For each member, return an ordered list of {name, count} for the
    authors whose patches they reviewed (descending by count).
    """
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for c in commits:
        author = canonicalize_author(c.author)
        for name in _individuals(c):
            if name in members:
                out[name][author] += 1
    return {
        member: [
            {"name": author, "count": cnt}
            for author, cnt in sorted(counter.items(), key=lambda kv: -kv[1])
        ]
        for member, counter in out.items()
    }


def compute_gini(counts: list[int]) -> float:
    """Gini coefficient. 0 = perfectly even, 1 = one person has everything."""
    n = len(counts)
    if n <= 1:
        return 0.0
    total = sum(counts)
    if total == 0:
        return 0.0
    sorted_counts = sorted(counts)
    cumulative_index_weighted = sum(
        (i + 1) * v for i, v in enumerate(sorted_counts)
    )
    return (2 * cumulative_index_weighted) / (n * total) - (n + 1) / n


def top_n_share(counts: dict[str, int], n: int) -> float:
    if not counts:
        return 0.0
    total = sum(counts.values())
    if total == 0:
        return 0.0
    sorted_vals = sorted(counts.values(), reverse=True)
    return sum(sorted_vals[:n]) / total


def bus_factor(counts: dict[str, int], *, threshold: float) -> int:
    if not counts:
        return 0
    total = sum(counts.values())
    if total == 0:
        return 0
    sorted_vals = sorted(counts.values(), reverse=True)
    accum = 0
    for k, v in enumerate(sorted_vals, start=1):
        accum += v
        if accum / total >= threshold:
            return k
    return len(sorted_vals)
