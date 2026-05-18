"""Tests for the `last_week` slice on aggregate_wait_times output.

The Team / Per-Week view should show only the most recent week's
wait-time stats instead of the 6-month rollup. To support that the
backend emits a `last_week` slice with the same shape as the
top-level aggregate (n / histogram / percentiles), scoped to a
single ISO week.
"""

from reviewstats.wait_time import aggregate_wait_times


def _row(wait_days: float | None, week: str | None = None) -> dict:
    return {"wait_days": wait_days, "week": week}


def test_last_week_picks_most_recent_week_with_samples():
    """ISO week strings sort lexically — `last_week` must be the
    chronologically latest week that has at least one sample, not
    the order in which rows happen to be passed in."""
    rows = [
        _row(0.5, "2026-W15"),
        _row(5.0, "2026-W20"),  # most recent
        _row(2.0, "2026-W18"),
    ]
    result = aggregate_wait_times(rows)
    assert result["last_week"]["week"] == "2026-W20"
    assert result["last_week"]["n"] == 1


def test_last_week_n_only_counts_samples_in_that_week():
    rows = [
        _row(1.0, "2026-W20"),
        _row(2.0, "2026-W20"),
        _row(99.0, "2026-W19"),  # earlier week — not counted
    ]
    result = aggregate_wait_times(rows)
    assert result["last_week"]["n"] == 2


def test_last_week_histogram_buckets_only_that_weeks_samples():
    rows = [
        _row(0.5, "2026-W20"),   # < 1 day
        _row(2.0, "2026-W20"),   # 1-3 days
        _row(40.0, "2026-W19"),  # > 1 month, but earlier week
    ]
    result = aggregate_wait_times(rows)
    counts = {b["bucket"]: b["count"] for b in result["last_week"]["histogram"]}
    assert counts["< 1 day"] == 1
    assert counts["1-3 days"] == 1
    assert counts["> 1 month"] == 0


def test_last_week_percentiles_use_only_that_weeks_samples():
    rows = [
        _row(1.0, "2026-W20"),
        _row(3.0, "2026-W20"),
        _row(99.0, "2026-W19"),  # outlier from an earlier week
    ]
    result = aggregate_wait_times(rows)
    assert result["last_week"]["percentiles"]["p50"] == 2.0


def test_last_week_is_none_when_no_samples_have_a_week():
    """If every row lacks a `week` value (or there are no rows), the
    slice is None — callers can short-circuit instead of rendering an
    empty card."""
    rows = [_row(1.0, None), _row(2.0, None)]
    result = aggregate_wait_times(rows)
    assert result["last_week"] is None


def test_last_week_is_none_when_no_valid_samples():
    rows = [_row(None, "2026-W20")]  # wait_days missing → excluded
    result = aggregate_wait_times(rows)
    assert result["last_week"] is None


def test_top_level_aggregates_unaffected_by_last_week_slice():
    """Adding the slice must not change the existing aggregate fields —
    n stays at total valid rows, percentiles cover the full window."""
    rows = [
        _row(1.0, "2026-W19"),
        _row(3.0, "2026-W20"),
    ]
    result = aggregate_wait_times(rows)
    assert result["n"] == 2
    assert result["percentiles"]["p50"] == 2.0
