"""Assemble the JSON-ready report dict from parsed commits.

Output shape is documented in
~/firefox-bug-investigation/dom-media-reviewer-bottleneck-investigation.md §5.
"""

from datetime import datetime, timedelta
from typing import Iterable

from reviewstats.git_log import Commit
from reviewstats.members import MEMBERS, MEMBER_IDS
from reviewstats.metrics import (
    author_patch_counts,
    author_reviewer_pairs,
    bus_factor,
    compute_gini,
    count_by_individual,
    iso_week,
    reviewer_to_authors,
    routing_breakdown,
    sole_reviewer_counts,
    top_n_share,
    total_reviews_per_member,
    weekly_counts_per_reviewer,
)


_TOP_N_FOR_TREND = 5
_TOP_AUTHORS = 15


def author_count_for_member(
    member: str,
    members: dict[str, str],
    top_authors: list[dict],
) -> int:
    """Look up the patch-author count for a member, using the canonical
    display name from `members` to match against `top_authors`.

    The Member Profile view uses this to ensure the "patches authored"
    tile equals the bar shown in the Top Authors chart for the same
    person — same source, same alias collapsing, same number.
    """
    canonical = members.get(member)
    if canonical is None:
        return 0
    for row in top_authors:
        if row.get("name") == canonical:
            return int(row.get("count", 0))
    return 0


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
    indiv_counts = count_by_individual(
        commits, group=group, members=MEMBER_IDS
    )
    sole_counts = sole_reviewer_counts(commits, members=MEMBER_IDS)
    weekly = weekly_counts_per_reviewer(
        commits, group=group, members=MEMBER_IDS
    )
    total_reviews = total_reviews_per_member(
        commits, group=group, members=MEMBER_IDS
    )
    author_totals = author_patch_counts(commits)
    author_reviewers = author_reviewer_pairs(commits, members=MEMBER_IDS)
    by_member_authors = reviewer_to_authors(commits, members=MEMBER_IDS)
    member_authored_counts = {
        member: author_totals.get(canonical, 0)
        for member, canonical in MEMBERS.items()
    }

    weeks = _iso_weeks_between(window_start, window_end)
    num_weeks = max(len(weeks), 1)

    ranked_individuals = _ranked_pairs(indiv_counts)
    top_reviewers = [name for name, _ in ranked_individuals[:_TOP_N_FOR_TREND]]

    all_members_weekly = {
        member: [weekly.get(wk, {}).get(member, 0) for wk in weeks]
        for member in MEMBER_IDS
    }

    ranked_authors = _ranked_pairs(author_totals)[:_TOP_AUTHORS]
    top_authors = [a for a, _ in ranked_authors]
    author_reviewer_matrix = {
        author: author_reviewers.get(author, {})
        for author in top_authors
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
            "all_members": all_members_weekly,
        },
        "total_reviews_per_member": total_reviews,
        "members": MEMBERS,
        "authors": {
            "top_total": _to_ranked_list(ranked_authors),
            "reviewer_matrix": author_reviewer_matrix,
        },
        "per_member_authors": by_member_authors,
        "member_authored_counts": member_authored_counts,
    }
