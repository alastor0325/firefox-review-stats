"""Assemble the JSON-ready report dict from parsed commits.

Output shape is documented in
~/firefox-bug-investigation/dom-media-reviewer-bottleneck-investigation.md §5.
"""

from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from reviewstats.git_log import Commit
from reviewstats.members import MEMBERS as _DEFAULT_MEMBERS
from reviewstats.metrics import (
    author_patch_counts,
    author_reviewer_pairs,
    bus_factor,
    compute_gini,
    count_by_individual,
    filter_commits_within,
    iso_week,
    landed_without_team_review,
    reviewer_to_authors,
    routing_breakdown,
    sole_reviewer_counts,
    top_n_share,
    total_reviews_per_member,
    weekly_authored_per_member,
    weekly_counts_per_reviewer,
)


_TOP_N_FOR_TREND = 5
_TOP_AUTHORS = 15

# The dashboard's audience works out of Portland; the refresh runs in
# CI under UTC. Render the human-readable "generated" stamp in Pacific
# time so it reads correctly regardless of where it was produced.
_DISPLAY_TZ = ZoneInfo("America/Los_Angeles")


def format_generated_at(dt: datetime) -> str:
    """Format `dt` as a Pacific-time display string, e.g.
    "Jun 1, 2026, 10:30 AM PDT".

    A tz-naive `dt` is assumed to be UTC (CI passes aware UTC datetimes,
    but this keeps a dev box from accidentally stamping local time).
    DST is handled by the zone: PDT in summer, PST in winter.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_DISPLAY_TZ)
    return local.strftime("%b %-d, %Y, %-I:%M %p %Z")

# Period axis on the Team View. Keys are the data-period attribute
# values the rendered HTML uses; values are months-back from
# window_end. 6m is the canonical six-month window that drives
# top-level fields too — 1m / 3m are extra slices added in the
# 1-month / 3-month period toggle.
TEAM_VIEW_WINDOWS = {
    "1m": 1,
    "3m": 3,
    "6m": 6,
}
_DAYS_PER_MONTH = 30


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


def _filter_no_team_review_list(
    rows: list[dict],
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[dict]:
    """Filter pre-built bad-commit rows by their ISO `date` string.

    The rows are constructed in analyze_git.py with `c.date.date().isoformat()`
    so a plain string comparison against the window's start/end dates
    keeps the same inclusivity contract as `filter_commits_within`.
    """
    start = window_start.date().isoformat()
    end = window_end.date().isoformat()
    return [r for r in rows if start <= r["date"] <= end]


def build_team_view(
    commits: Iterable[Commit],
    *,
    group: str,
    members: dict[str, str],
    window_start: datetime,
    window_end: datetime,
    no_team_review_list: list[dict] | None = None,
) -> dict:
    """Compute the per-window team-view fields shown by the Team toggle.

    Returns only the fields that vary by window (summary, concentration,
    within_group_total, sole_reviewer, total_reviews_per_member, authors),
    plus the window dates. Cross-window fields (weekly_trend, members,
    per-member views) live at the top of the report — including them
    here would triple the rendered JSON for no benefit.

    `no_team_review_list` is the FULL bad-commit list (built once from
    the 6-month commit fetch). We filter it by date here so 1-month
    and 3-month slices show only patches landed inside the window;
    the per-subdir bucket counts are re-derived from the filtered list.
    """
    in_window = filter_commits_within(
        commits, window_start=window_start, window_end=window_end
    )
    member_ids = frozenset(members)

    routing = routing_breakdown(in_window, group=group)
    no_team_review = landed_without_team_review(
        in_window, group=group, members=member_ids
    )
    indiv_counts = count_by_individual(
        in_window, group=group, members=member_ids
    )
    sole_counts = sole_reviewer_counts(in_window, members=member_ids)
    total_reviews = total_reviews_per_member(
        in_window, group=group, members=member_ids
    )
    author_totals = author_patch_counts(in_window)
    author_reviewers = author_reviewer_pairs(in_window, members=member_ids)

    ranked_individuals = _ranked_pairs(indiv_counts)
    ranked_authors = _ranked_pairs(author_totals)[:_TOP_AUTHORS]
    top_authors = [a for a, _ in ranked_authors]
    author_reviewer_matrix = {
        author: author_reviewers.get(author, {})
        for author in top_authors
    }

    weeks = _iso_weeks_between(window_start, window_end)
    num_weeks = max(len(weeks), 1)

    filtered_list = (
        _filter_no_team_review_list(
            no_team_review_list,
            window_start=window_start,
            window_end=window_end,
        )
        if no_team_review_list
        else []
    )
    by_subdir = Counter(r["primary_subdir"] for r in filtered_list)

    return {
        "window_start": window_start.date().isoformat(),
        "window_end": window_end.date().isoformat(),
        "summary": {
            "total_patches": routing["total"],
            "group_tagged_patches": routing["group_tagged"],
            "group_tagged_pct": _pct(
                routing["group_tagged"], routing["total"]
            ),
            "landed_without_team_review": no_team_review,
            "landed_without_team_review_pct": _pct(
                no_team_review, routing["total"]
            ),
            "landed_without_team_review_by_subdir": dict(by_subdir),
            "landed_without_team_review_list": filtered_list,
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
        "total_reviews_per_member": total_reviews,
        "authors": {
            "top_total": _to_ranked_list(ranked_authors),
            "reviewer_matrix": author_reviewer_matrix,
        },
    }


def build_report(
    commits: Iterable[Commit],
    *,
    group: str,
    path: str | None = None,
    paths: tuple[str, ...] | None = None,
    window_start: datetime,
    window_end: datetime,
    generated_at: datetime,
    excludes: tuple[str, ...] = (),
    no_team_review_by_subdir: dict[str, int] | None = None,
    no_team_review_list: list[dict] | None = None,
    members: dict[str, str] | None = None,
) -> dict:
    # Both `path` (singular, kept for older callers) and `paths`
    # (plural, used by multi-path teams) are supported. If `paths` is
    # given it wins; otherwise we lift the singular `path` into a
    # one-tuple. Meta carries both fields so templates and tests can
    # read either without churn.
    if paths is None:
        if path is None:
            raise TypeError("build_report requires `path` or `paths`")
        paths = (path,)
    elif path is None:
        path = paths[0]
    commits = list(commits)
    # Caller can pass a team-specific roster; defaults to the playback
    # roster so existing callers keep working unchanged.
    members_dict = _DEFAULT_MEMBERS if members is None else members
    member_ids = frozenset(members_dict)

    # Per-window team-view aggregates: same content as the top-level
    # 6m fields but recomputed over a shorter slice for the 1-Month /
    # 3-Month period toggle. The "6m" slot keeps the full window the
    # caller passed in — i.e. min(commit.date) → max(commit.date) —
    # so the top-level fields (which alias `team_views["6m"]`) match
    # the pre-window-toggle behaviour exactly.
    team_views: dict[str, dict] = {}
    for key, months in TEAM_VIEW_WINDOWS.items():
        if key == "6m":
            sub_start = window_start
        else:
            sub_start = max(
                window_start,
                window_end - timedelta(days=_DAYS_PER_MONTH * months),
            )
        team_views[key] = build_team_view(
            commits,
            group=group,
            members=members_dict,
            window_start=sub_start,
            window_end=window_end,
            no_team_review_list=no_team_review_list,
        )

    six_month_view = team_views["6m"]

    # Cross-window fields: weekly_trend and the member-profile data
    # live at the top level because they're already 6m-wide.
    weekly = weekly_counts_per_reviewer(
        commits, group=group, members=member_ids
    )
    by_member_authors = reviewer_to_authors(commits, members=member_ids)
    author_totals = author_patch_counts(commits)
    member_authored_counts = {
        member: author_totals.get(canonical, 0)
        for member, canonical in members_dict.items()
    }

    weeks = _iso_weeks_between(window_start, window_end)
    top_reviewers = [r["name"] for r in six_month_view["within_group_total"][:_TOP_N_FOR_TREND]]

    all_members_weekly = {
        member: [weekly.get(wk, {}).get(member, 0) for wk in weeks]
        for member in member_ids
    }
    authored_per_member_weekly = weekly_authored_per_member(
        commits, members_dict, weeks,
    )

    return {
        "meta": {
            "path": path,
            "paths": list(paths),
            "group": group,
            "excludes": list(excludes),
            "window_start": window_start.date().isoformat(),
            "window_end": window_end.date().isoformat(),
            "generated_at": generated_at.isoformat(),
            "generated_at_display": format_generated_at(generated_at),
        },
        # Top-level mirrors the 6m team_view so older clients (and
        # any test that pre-dates `team_views`) read the same numbers.
        "summary": six_month_view["summary"],
        "within_group_total": six_month_view["within_group_total"],
        "concentration": six_month_view["concentration"],
        "sole_reviewer": six_month_view["sole_reviewer"],
        "weekly_trend": {
            "weeks": weeks,
            "top_reviewers": top_reviewers,
            "all_members": all_members_weekly,
            "authored_per_member": authored_per_member_weekly,
        },
        "total_reviews_per_member": six_month_view["total_reviews_per_member"],
        "members": members_dict,
        "authors": six_month_view["authors"],
        "per_member_authors": by_member_authors,
        "member_authored_counts": member_authored_counts,
        # Per-window slices for the Team-View period toggle. Top-level
        # fields above carry the 6m numbers (backward compat);
        # `team_views["1m"]` / `team_views["3m"]` are the same shape
        # with a narrower commit slice.
        "team_views": team_views,
    }
