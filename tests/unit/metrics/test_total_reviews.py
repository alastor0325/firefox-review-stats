from datetime import datetime, timezone

from reviewstats.metrics import total_reviews_per_member
from reviewstats.parse import Reviewer


GROUP = "media-playback-reviewers"
MEMBERS = frozenset({"padenot", "alwu"})


class _C:
    def __init__(self, reviewers, date=None):
        self.reviewers = reviewers
        self.date = date or datetime(2026, 5, 15, tzinfo=timezone.utc)
        self.author = "A"


def _r(name, is_group=False):
    return Reviewer(name, is_group=is_group)


def test_splits_in_group_vs_out_of_group():
    commits = [
        _C([_r(GROUP, True), _r("padenot")]),       # in-group
        _C([_r(GROUP, True), _r("padenot")]),       # in-group
        _C([_r("padenot")]),                         # out-of-group (no media-playback tag)
        _C([_r("webrtc-reviewers", True), _r("padenot")]),  # out-of-group
        _C([_r(GROUP, True), _r("alwu")]),          # in-group
        _C([_r("emilio")]),                          # non-member — ignored
    ]
    result = total_reviews_per_member(commits, group=GROUP, members=MEMBERS)
    by_name = {r["name"]: r for r in result}
    assert by_name["padenot"]["in_group"] == 2
    assert by_name["padenot"]["out_of_group"] == 2
    assert by_name["padenot"]["total"] == 4
    assert by_name["alwu"]["in_group"] == 1
    assert by_name["alwu"]["out_of_group"] == 0
    assert by_name["alwu"]["total"] == 1


def test_includes_zero_total_members():
    # Members who never reviewed should not appear (cleaner chart).
    commits = [_C([_r(GROUP, True), _r("padenot")])]
    result = total_reviews_per_member(commits, group=GROUP, members=MEMBERS)
    names = [r["name"] for r in result]
    assert names == ["padenot"]


def test_sorted_by_total_descending():
    commits = (
        [_C([_r(GROUP, True), _r("alwu")])] * 5
        + [_C([_r(GROUP, True), _r("padenot")])] * 10
    )
    result = total_reviews_per_member(commits, group=GROUP, members=MEMBERS)
    assert [r["name"] for r in result] == ["padenot", "alwu"]
