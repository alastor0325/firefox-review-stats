"""Filtering wait-time records to a sub-window (1m / 3m / 6m).

The Team View period toggle lets users see wait-time stats for the
last month and the last three months alongside the six-month rollup.
`filter_wait_revisions_within` is the pure helper that backs each
windowed `aggregate_wait_times` call in `analyze_phab.py`.
"""

from datetime import datetime, timezone

from reviewstats.wait_time import filter_wait_revisions_within


def _rev(date_iso: str, wait_days: float = 1.0) -> dict:
    return {
        "d_number": f"D{date_iso}",
        "wait_days": wait_days,
        "week": "2026-W20",
        "date": date_iso,
    }


class TestFilterWaitRevisionsWithin:
    def test_returns_only_records_within_window(self):
        revs = [
            _rev("2026-01-01"),  # well outside
            _rev("2026-04-01"),  # outside 1m, inside 3m
            _rev("2026-05-20"),  # inside 1m
        ]
        out = filter_wait_revisions_within(
            revs,
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert [r["d_number"] for r in out] == ["D2026-05-20"]

    def test_inclusive_boundaries(self):
        revs = [_rev("2026-05-01"), _rev("2026-05-28")]
        out = filter_wait_revisions_within(
            revs,
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert len(out) == 2

    def test_accepts_datetime_date_field_too(self):
        # `member_authored_wait_revisions` historically attached
        # `commit.date` (a datetime) to per-revision dicts. Accept
        # both datetime and ISO string so the helper survives a
        # schema change without breaking callers.
        revs = [{
            "d_number": "D1",
            "wait_days": 1.0,
            "week": "2026-W20",
            "date": datetime(2026, 5, 20, tzinfo=timezone.utc),
        }]
        out = filter_wait_revisions_within(
            revs,
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert len(out) == 1

    def test_missing_date_field_is_dropped(self):
        # Records without a date can't be windowed reliably; drop them
        # from sub-window slices rather than silently double-counting
        # in every period.
        revs = [_rev("2026-05-20"), {"d_number": "D2", "wait_days": 1.0}]
        out = filter_wait_revisions_within(
            revs,
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert [r["d_number"] for r in out] == ["D2026-05-20"]
