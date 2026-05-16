"""Pure functions for computing review wait time from Phab transactions."""

import statistics


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
    }
