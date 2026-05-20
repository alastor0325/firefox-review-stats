from datetime import datetime, timezone

from reviewstats.metrics import (
    count_by_individual,
    non_member_reviewer_counts,
    weekly_counts_per_reviewer,
)
from reviewstats.parse import Reviewer


GROUP = "media-playback-reviewers"
MEMBERS = frozenset({"padenot", "alwu", "kinetik"})


class _C:
    def __init__(self, reviewers, date=None):
        self.reviewers = reviewers
        self.date = date or datetime(2026, 5, 15, tzinfo=timezone.utc)


def _r(name, is_group=False):
    return Reviewer(name, is_group=is_group)


class TestCountByIndividualWithMemberFilter:
    def test_filters_non_members(self):
        commits = [
            _C([_r(GROUP, True), _r("padenot")]),
            _C([_r(GROUP, True), _r("emilio")]),     # emilio not a member
            _C([_r(GROUP, True), _r("padenot"), _r("emilio")]),
        ]
        result = count_by_individual(commits, group=GROUP, members=MEMBERS)
        assert result == {"padenot": 2}

    def test_no_filter_when_members_none(self):
        commits = [_C([_r(GROUP, True), _r("emilio")])]
        assert count_by_individual(commits, group=GROUP, members=None) == {
            "emilio": 1
        }


class TestNonMemberReviewerCounts:
    def test_counts_outsiders(self):
        commits = [
            _C([_r(GROUP, True), _r("emilio")]),
            _C([_r(GROUP, True), _r("emilio"), _r("aosmond_not_member")]),
            _C([_r(GROUP, True), _r("padenot")]),  # member — ignored
        ]
        result = non_member_reviewer_counts(
            commits, group=GROUP, members=MEMBERS
        )
        assert result == {"emilio": 2, "aosmond_not_member": 1}

    def test_ignores_commits_without_group(self):
        commits = [_C([_r("emilio")])]
        assert (
            non_member_reviewer_counts(commits, group=GROUP, members=MEMBERS)
            == {}
        )


class TestWeeklyCountsWithMemberFilter:
    def test_filters_to_members(self):
        commits = [
            _C(
                [_r(GROUP, True), _r("padenot")],
                date=datetime(2026, 5, 11, tzinfo=timezone.utc),
            ),
            _C(
                [_r(GROUP, True), _r("emilio")],
                date=datetime(2026, 5, 11, tzinfo=timezone.utc),
            ),
        ]
        result = weekly_counts_per_reviewer(
            commits, group=GROUP, members=MEMBERS
        )
        assert "2026-W20" in result
        assert result["2026-W20"] == {"padenot": 1}
