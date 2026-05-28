from datetime import datetime, timezone

from reviewstats.metrics import filter_commits_within
from reviewstats.parse import Reviewer


class _C:
    def __init__(self, date: datetime):
        self.date = date
        self.reviewers: list[Reviewer] = []


_DATES = [
    datetime(2026, 1, 1, tzinfo=timezone.utc),  # well outside
    datetime(2026, 4, 1, tzinfo=timezone.utc),  # inside 6m, outside 3m
    datetime(2026, 5, 1, tzinfo=timezone.utc),  # inside 3m, outside 1m
    datetime(2026, 5, 20, tzinfo=timezone.utc),  # inside 1m
    datetime(2026, 5, 28, tzinfo=timezone.utc),  # right at window_end
]


class TestFilterCommitsWithin:
    def test_returns_only_in_range(self):
        commits = [_C(d) for d in _DATES]
        out = filter_commits_within(
            commits,
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert [c.date for c in out] == _DATES[2:]

    def test_inclusive_boundaries(self):
        commits = [_C(d) for d in _DATES]
        out = filter_commits_within(
            commits,
            window_start=_DATES[2],
            window_end=_DATES[2],
        )
        # Boundaries are inclusive on both sides; one match at the start
        # equal to the end is a real corner case (single-day window).
        assert [c.date for c in out] == [_DATES[2]]

    def test_empty_input(self):
        assert filter_commits_within(
            [],
            window_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
        ) == []

    def test_no_match(self):
        commits = [_C(_DATES[0])]
        assert filter_commits_within(
            commits,
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        ) == []

    def test_iterable_input(self):
        # Accepts any iterable, not just list — many call sites pass
        # generators (e.g. `(c for c in fetch_commits(...) if c.date)`).
        commits = [_C(d) for d in _DATES]
        out = filter_commits_within(
            (c for c in commits),
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert len(list(out)) == 3
