"""Pure functions for computing review wait time from Phab transactions."""

import statistics
from typing import Callable, Mapping

from reviewstats.git_log import Commit
from reviewstats.metrics import iso_week


def composite_wait_seconds(raw: dict) -> tuple[int | None, int | None, str | None]:
    """Pick the best-available wait timing for a revision.

    Returns `(react_seconds, accept_seconds, anchor)`.

    * Prefer creation-anchored timings (`time_to_react_seconds` /
      `time_to_accept_seconds`) — those count from the moment the
      patch was submitted to Phab, regardless of which reviewer was
      tagged. Covers patches that never had `media-playback-reviewers`
      added as a group reviewer (e.g. `r=padenot` only).
    * Fall back to queue-anchored timings (`queue_seconds` /
      `queue_to_accept_seconds`) when the creation timestamp is
      missing — typically older revisions whose `create` event has
      paged off Phab's rendered timeline.
    * Returns `(None, None, None)` when neither anchor is available.

    The composite ensures the team-level histogram and the Wait Queue
    use the same wait number for every revision, so a long-wait patch
    that shows up in one view also shows up in the other.
    """
    react_s = raw.get("time_to_react_seconds")
    accept_s = raw.get("time_to_accept_seconds")
    if react_s is not None or accept_s is not None:
        return react_s, accept_s, "creation"
    qs = raw.get("queue_seconds")
    qas = raw.get("queue_to_accept_seconds")
    if qs is not None or qas is not None:
        return qs, qas, "queue-added"
    return None, None, None


def member_authored_wait_revisions(
    d_numbers: list[str],
    raw_for_d: Mapping[str, dict] | Callable[[str], dict | None],
    commits_by_d: Mapping[str, Commit],
    *,
    members: frozenset[str],
) -> list[dict]:
    """Return per-revision wait entries for `aggregate_wait_times`.

    Filter contract:
      * `raw['author']` MUST be in `members` — patches authored by
        non-members never enter the team-level wait-time aggregate.
      * `raw['queue_seconds']` MUST be non-None (queue-added → member
        reacted is computable).
      * Commits not in the active window (`commits_by_d`) are
        skipped.

    Pinned by tests in test_wait_revisions_filter.py so a regression
    in the filtering logic surfaces in CI rather than silently
    inflating the team-level wait-time histogram with non-member
    patches.
    """
    fetch = (
        raw_for_d if callable(raw_for_d) else raw_for_d.get
    )
    out: list[dict] = []
    for d in d_numbers:
        raw = fetch(d)
        if raw is None:
            continue
        if raw.get("author") not in members:
            continue
        react_s, _accept_s, _anchor = composite_wait_seconds(raw)
        if react_s is None:
            continue
        commit = commits_by_d.get(d)
        if commit is None:
            continue
        first_review = raw.get("first_member_review") or {}
        out.append({
            "d_number": d,
            "wait_days": react_s / 86400.0,
            "reviewer": first_review.get("actor"),
            "week": iso_week(commit.date),
        })
    return out


_REVIEW_TX_TYPES = frozenset({
    "comment",
    "accept",
    "reject",
    "request-changes",
    "inline",
})
_BOT_PHID_PREFIXES = (
    "PHID-APPS-",        # herald / lint bots
    "PHID-USER-fwic",    # autoland-bot — best-effort prefix match
)


def _is_bot(phid: str | None) -> bool:
    if not phid:
        return True
    return phid.startswith(_BOT_PHID_PREFIXES)


def first_review_timestamp(
    transactions: list[dict], *, author_phid: str | None
) -> int | None:
    candidates: list[int] = []
    for tx in transactions:
        if tx.get("type") not in _REVIEW_TX_TYPES:
            continue
        actor = tx.get("authorPHID")
        if actor == author_phid:
            continue
        if _is_bot(actor):
            continue
        ts = tx.get("dateCreated")
        if ts is not None:
            candidates.append(int(ts))
    return min(candidates) if candidates else None


def wait_time_days(
    *, date_created: int, first_review: int | None
) -> float | None:
    if first_review is None:
        return None
    return (first_review - date_created) / 86400.0


def bucket_wait_days(days: float) -> str:
    if days < 1:
        return "< 1 day"
    if days < 3:
        return "1-3 days"
    if days < 7:
        return "3-7 days"
    if days < 14:
        return "1-2 weeks"
    if days < 28:
        return "2-4 weeks"
    return "> 1 month"


BUCKETS = ("< 1 day", "1-3 days", "3-7 days", "1-2 weeks", "2-4 weeks", "> 1 month")


def percentile_days(values: list[float], p: float) -> float | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def aggregate_wait_times(
    per_revision: list[dict],
) -> dict:
    """`per_revision`: items with keys `wait_days` (float|None) and
    optionally `reviewer` (str|None) and `week` (str). Returns the shape
    consumed by the HTML report.
    """
    valid = [r for r in per_revision if r.get("wait_days") is not None]
    days = [r["wait_days"] for r in valid]

    histogram: dict[str, int] = {b: 0 for b in BUCKETS}
    for d in days:
        histogram[bucket_wait_days(d)] += 1
    total = sum(histogram.values()) or 1
    histogram_list = [
        {"bucket": b, "count": histogram[b], "pct": histogram[b] / total}
        for b in BUCKETS
    ]

    by_week: dict[str, list[float]] = {}
    for r in valid:
        wk = r.get("week")
        if wk:
            by_week.setdefault(wk, []).append(r["wait_days"])
    weekly = sorted(
        [
            {"week": wk, "median_days": statistics.median(vs), "count": len(vs)}
            for wk, vs in by_week.items()
        ],
        key=lambda r: r["week"],
    )

    return {
        "n": len(valid),
        "histogram": histogram_list,
        "percentiles": {
            "p50": percentile_days(days, 50),
            "p75": percentile_days(days, 75),
            "p90": percentile_days(days, 90),
        },
        "weekly_median": weekly,
        "last_week": _last_week_slice(by_week),
    }


def _last_week_slice(by_week: dict[str, list[float]]) -> dict | None:
    """Most-recent week's wait-time data shaped like the top-level
    aggregate (n / histogram / percentiles) plus the week label.

    Returns None when no week has any samples.

    Used by the Team / Per-Week view so the report can show "this week
    only" stats rather than the 6-month rollup.
    """
    if not by_week:
        return None
    week = max(by_week)  # ISO `YYYY-Www` sorts lexically by recency
    days = by_week[week]
    histogram: dict[str, int] = {b: 0 for b in BUCKETS}
    for d in days:
        histogram[bucket_wait_days(d)] += 1
    total = sum(histogram.values()) or 1
    return {
        "week": week,
        "n": len(days),
        "histogram": [
            {"bucket": b, "count": histogram[b], "pct": histogram[b] / total}
            for b in BUCKETS
        ],
        "percentiles": {
            "p50": percentile_days(days, 50),
            "p75": percentile_days(days, 75),
            "p90": percentile_days(days, 90),
        },
    }
