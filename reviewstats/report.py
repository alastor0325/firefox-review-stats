"""Assemble the JSON-ready report dict from parsed commits.

Output shape is documented in
~/firefox-bug-investigation/dom-media-reviewer-bottleneck-investigation.md §5.
"""

from datetime import datetime, timedelta
from typing import Iterable

from reviewstats.git_log import Commit
from reviewstats.metrics import (
    active_windows,
    bus_factor,
    compute_gini,
    count_by_individual,
    iso_week,
    routing_breakdown,
    sole_reviewer_counts,
    top_n_share,
    weekly_counts_per_reviewer,
)


_TOP_N_FOR_TREND = 5


def _pct(part: int, whole: int) -> float:
    return (part / whole) if whole else 0.0


def _ranked_pairs(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: -kv[1])


def _to_ranked_list(pairs: list[tuple[str, int]]) -> list[dict]:
    total = sum(cnt for _, cnt in pairs) or 1
    return [
        {"name": name, "count": cnt, "pct": cnt / total}
        for name, cnt in pairs
    ]


def _iso_weeks_between(start: datetime, end: datetime) -> list[str]:
    cur = start - timedelta(days=start.isoweekday() - 1)
    weeks: list[str] = []
    while cur <= end:
        weeks.append(iso_week(cur))
        cur += timedelta(days=7)
    return weeks


def build_report(
    commits: Iterable[Commit],
    *,
    group: str,
    path: str,
    window_start: datetime,
    window_end: datetime,
    generated_at: datetime,
) -> dict:
    commits = list(commits)

    routing = routing_breakdown(commits, group=group)
    indiv_counts = count_by_individual(commits, group=group)
    sole_counts = sole_reviewer_counts(commits)
    weekly = weekly_counts_per_reviewer(commits, group=group)
    windows = active_windows(commits, group=group)

    weeks = _iso_weeks_between(window_start, window_end)
    num_weeks = max(len(weeks), 1)

    ranked_individuals = _ranked_pairs(indiv_counts)
    top_reviewers = [name for name, _ in ranked_individuals[:_TOP_N_FOR_TREND]]

    trend_counts = {
        name: [weekly.get(wk, {}).get(name, 0) for wk in weeks]
        for name in top_reviewers
    }

    return {
        "meta": {
            "path": path,
            "group": group,
            "window_start": window_start.date().isoformat(),
            "window_end": window_end.date().isoformat(),
            "generated_at": generated_at.isoformat(),
        },
        "summary": {
            "total_patches": routing["total"],
            "group_tagged_patches": routing["group_tagged"],
            "group_tagged_pct": _pct(
                routing["group_tagged"], routing["total"]
            ),
            "with_individual_named": routing["group_with_individual"],
            "with_individual_pct": _pct(
                routing["group_with_individual"], routing["group_tagged"]
            ),
            "group_only": routing["group_only"],
            "group_only_pct": _pct(
                routing["group_only"], routing["group_tagged"]
            ),
            "unique_individuals": len(indiv_counts),
            "avg_per_week": routing["group_tagged"] / num_weeks,
        },
        "within_group_total": _to_ranked_list(ranked_individuals),
        "concentration": {
            "top1_share": top_n_share(indiv_counts, 1),
            "top3_share": top_n_share(indiv_counts, 3),
            "top5_share": top_n_share(indiv_counts, 5),
            "gini": compute_gini(list(indiv_counts.values())),
            "bus_factor": bus_factor(indiv_counts, threshold=0.5),
        },
        "sole_reviewer": _to_ranked_list(_ranked_pairs(sole_counts)),
        "weekly_trend": {
            "weeks": weeks,
            "top_reviewers": top_reviewers,
            "counts": trend_counts,
        },
        "active_windows": {
            name: {"first_week": w.first_week, "last_week": w.last_week}
            for name, w in windows.items()
        },
    }
