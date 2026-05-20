from datetime import datetime, timezone

from reviewstats.metrics import (
    bus_factor,
    compute_gini,
    count_by_individual,
    iso_week,
    routing_breakdown,
    sole_reviewer_counts,
    top_n_share,
    weekly_counts_per_reviewer,
)
from reviewstats.parse import Reviewer


class _C:
    def __init__(self, reviewers: list[Reviewer], date: datetime | None = None):
        self.reviewers = reviewers
        self.date = date or datetime(2026, 5, 15, tzinfo=timezone.utc)


def _r(name: str, is_group: bool = False) -> Reviewer:
    return Reviewer(name, is_group=is_group)


GROUP = "media-playback-reviewers"


class TestIsoWeek:
    def test_known_date(self):
        # 2026-05-15 is a Friday in ISO week 20.
        assert iso_week(datetime(2026, 5, 15)) == "2026-W20"

    def test_year_boundary(self):
        # 2025-12-29 is in ISO week 2026-W01 by ISO calendar.
        assert iso_week(datetime(2025, 12, 29)) == "2026-W01"


class TestCountByIndividual:
    def test_basic_distribution(self):
        commits = [
            _C([_r("padenot"), _r(GROUP, True)]),
            _C([_r("padenot"), _r(GROUP, True)]),
            _C([_r("alwu"), _r(GROUP, True)]),
        ]
        # Filter to commits that involve the group.
        result = count_by_individual(commits, group=GROUP)
        assert result == {"padenot": 2, "alwu": 1}

    def test_ignores_commits_without_group(self):
        commits = [
            _C([_r("padenot"), _r(GROUP, True)]),
            _C([_r("emilio")]),  # not group-tagged → ignored
        ]
        assert count_by_individual(commits, group=GROUP) == {"padenot": 1}

    def test_group_only_patch_counts_nothing_for_individual_view(self):
        # `r=media-playback-reviewers` with no individual — no individual to
        # attribute. The patch is still counted in the group total elsewhere.
        commits = [_C([_r(GROUP, True)])]
        assert count_by_individual(commits, group=GROUP) == {}


class TestComputeGini:
    def test_perfectly_even(self):
        assert compute_gini([10, 10, 10, 10]) == 0.0

    def test_one_takes_all(self):
        assert compute_gini([0, 0, 0, 40]) > 0.7

    def test_empty(self):
        assert compute_gini([]) == 0.0

    def test_single_value(self):
        assert compute_gini([5]) == 0.0


class TestTopNShare:
    def test_top_1(self):
        counts = {"a": 50, "b": 30, "c": 20}
        assert top_n_share(counts, 1) == 0.5

    def test_top_3_covers_all(self):
        counts = {"a": 50, "b": 30, "c": 20}
        assert top_n_share(counts, 3) == 1.0

    def test_empty(self):
        assert top_n_share({}, 3) == 0.0


class TestBusFactor:
    def test_one_dominant(self):
        # a alone covers 60% — bus factor 1.
        assert bus_factor({"a": 60, "b": 20, "c": 20}, threshold=0.5) == 1

    def test_two_needed(self):
        # a=40, b=30, c=30. a alone = 40% (< 50%); a+b = 70% → bus factor 2.
        assert bus_factor({"a": 40, "b": 30, "c": 30}, threshold=0.5) == 2

    def test_empty(self):
        assert bus_factor({}, threshold=0.5) == 0


class TestRoutingBreakdown:
    def test_breakdown(self):
        commits = [
            _C([_r(GROUP, True), _r("padenot")]),       # group + indiv
            _C([_r(GROUP, True)]),                       # group only
            _C([_r("emilio")]),                          # no group
            _C([_r("webrtc-reviewers", True), _r("bwc")]),  # other group
        ]
        result = routing_breakdown(commits, group=GROUP)
        assert result["total"] == 4
        assert result["group_tagged"] == 2
        assert result["group_with_individual"] == 1
        assert result["group_only"] == 1


class TestSoleReviewerCounts:
    def test_only_one_reviewer_and_no_group(self):
        commits = [
            _C([_r("padenot")]),  # sole-reviewer
            _C([_r("padenot")]),  # sole-reviewer
            _C([_r("padenot"), _r("alwu")]),  # not sole
            _C([_r("padenot"), _r(GROUP, True)]),  # has group → not sole
        ]
        result = sole_reviewer_counts(commits)
        assert result == {"padenot": 2}

    def test_group_only_is_not_sole(self):
        commits = [_C([_r(GROUP, True)])]
        assert sole_reviewer_counts(commits) == {}


class TestWeeklyCountsPerReviewer:
    def test_buckets_by_week(self):
        commits = [
            _C([_r("padenot"), _r(GROUP, True)],
               date=datetime(2026, 5, 11, tzinfo=timezone.utc)),  # W20
            _C([_r("padenot"), _r(GROUP, True)],
               date=datetime(2026, 5, 15, tzinfo=timezone.utc)),  # W20
            _C([_r("alwu"), _r(GROUP, True)],
               date=datetime(2026, 5, 4, tzinfo=timezone.utc)),   # W19
        ]
        result = weekly_counts_per_reviewer(commits, group=GROUP)
        assert result["2026-W20"]["padenot"] == 2
        assert result["2026-W19"]["alwu"] == 1


