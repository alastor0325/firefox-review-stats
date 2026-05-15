"""Pure aggregation metrics over parsed commits."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol

from reviewstats.parse import Reviewer


class _CommitLike(Protocol):
    reviewers: list[Reviewer]
    date: datetime


@dataclass(frozen=True)
class ActiveWindow:
    first_week: str
    last_week: str


def iso_week(date: datetime) -> str:
    iso = date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _has_group(commit: _CommitLike, group: str) -> bool:
    return any(r.is_group and r.name == group for r in commit.reviewers)


def _individuals(commit: _CommitLike) -> list[str]:
    return [r.name for r in commit.reviewers if not r.is_group]


def count_by_individual(
    commits: Iterable[_CommitLike], *, group: str
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for c in commits:
        if not _has_group(c, group):
            continue
        for name in _individuals(c):
            counts[name] += 1
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


def sole_reviewer_counts(commits: Iterable[_CommitLike]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for c in commits:
        if len(c.reviewers) != 1:
            continue
        only = c.reviewers[0]
        if only.is_group:
            continue
        counts[only.name] += 1
    return dict(counts)


def weekly_counts_per_reviewer(
    commits: Iterable[_CommitLike], *, group: str
) -> dict[str, dict[str, int]]:
    """{ "2026-W20": { "padenot": 5, ... }, ... }"""
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in commits:
        if not _has_group(c, group):
            continue
        week = iso_week(c.date)
        for name in _individuals(c):
            out[week][name] += 1
    return {wk: dict(d) for wk, d in out.items()}


def active_windows(
    commits: Iterable[_CommitLike], *, group: str
) -> dict[str, ActiveWindow]:
    first: dict[str, datetime] = {}
    last: dict[str, datetime] = {}
    for c in commits:
        if not _has_group(c, group):
            continue
        for name in _individuals(c):
            if name not in first or c.date < first[name]:
                first[name] = c.date
            if name not in last or c.date > last[name]:
                last[name] = c.date
    return {
        name: ActiveWindow(iso_week(first[name]), iso_week(last[name]))
        for name in first
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
