from datetime import datetime, timezone

from reviewstats.metrics import (
    author_patch_counts,
    author_reviewer_pairs,
    reviewer_to_authors,
)
from reviewstats.parse import Reviewer


GROUP = "media-playback-reviewers"
MEMBERS = frozenset({"padenot", "alwu", "kinetik"})


class _C:
    def __init__(self, author, reviewers, date=None):
        self.author = author
        self.reviewers = reviewers
        self.date = date or datetime(2026, 5, 15, tzinfo=timezone.utc)


def _r(name, is_group=False):
    return Reviewer(name, is_group=is_group)


class TestAuthorPatchCounts:
    def test_counts_per_author(self):
        commits = [
            _C("Alastor Wu", [_r("padenot")]),
            _C("Alastor Wu", [_r("padenot")]),
            _C("Paul Adenot", [_r("alwu")]),
        ]
        assert author_patch_counts(commits) == {
            "Alastor Wu": 2,
            "Paul Adenot": 1,
        }

    def test_empty(self):
        assert author_patch_counts([]) == {}

    def test_collapses_known_aliases(self):
        commits = [
            _C("Alastor Wu", [_r("padenot")]),
            _C("alastor0325", [_r("padenot")]),
            _C("alwu", [_r("padenot")]),
            _C("Paul Adenot", [_r("alwu")]),
        ]
        assert author_patch_counts(commits) == {
            "Alastor Wu": 3,
            "Paul Adenot": 1,
        }


class TestReviewerToAuthors:
    def test_inverse_of_author_reviewer_pairs(self):
        commits = [
            _C("Alastor Wu", [_r("padenot")]),
            _C("Alastor Wu", [_r("padenot")]),
            _C("Paul Adenot", [_r("alwu")]),
            _C("Paul Adenot", [_r("padenot"), _r("alwu")]),
        ]
        result = reviewer_to_authors(
            commits, members=frozenset({"padenot", "alwu"})
        )
        assert result["padenot"] == [
            {"name": "Alastor Wu", "count": 2},
            {"name": "Paul Adenot", "count": 1},
        ]
        assert result["alwu"] == [
            {"name": "Paul Adenot", "count": 2},
        ]

    def test_collapses_author_aliases(self):
        commits = [
            _C("alastor0325", [_r("padenot")]),
            _C("Alastor Wu", [_r("padenot")]),
        ]
        result = reviewer_to_authors(
            commits, members=frozenset({"padenot"})
        )
        assert result["padenot"] == [
            {"name": "Alastor Wu", "count": 2},
        ]

    def test_skips_non_member_reviewers(self):
        commits = [_C("Author", [_r("emilio")])]
        assert reviewer_to_authors(
            commits, members=frozenset({"padenot"})
        ) == {}


class TestAuthorReviewerPairsAliases:
    def test_pairs_collapse_author_aliases(self):
        commits = [
            _C("Alastor Wu", [_r("padenot")]),
            _C("alastor0325", [_r("padenot")]),
            _C("alwu", [_r("alwu")]),
        ]
        result = author_reviewer_pairs(commits, members=None)
        assert result == {"Alastor Wu": {"padenot": 2, "alwu": 1}}


class TestAuthorReviewerPairs:
    def test_pairs_with_member_filter(self):
        commits = [
            _C("Alastor Wu", [_r(GROUP, True), _r("padenot")]),
            _C("Alastor Wu", [_r(GROUP, True), _r("padenot")]),
            _C("Alastor Wu", [_r(GROUP, True), _r("emilio")]),  # filtered out
            _C("Paul Adenot", [_r(GROUP, True), _r("alwu")]),
        ]
        result = author_reviewer_pairs(commits, members=MEMBERS)
        assert result == {
            "Alastor Wu": {"padenot": 2},
            "Paul Adenot": {"alwu": 1},
        }

    def test_pairs_without_member_filter(self):
        commits = [
            _C("Alastor Wu", [_r("padenot")]),
            _C("Alastor Wu", [_r("emilio")]),
        ]
        result = author_reviewer_pairs(commits, members=None)
        assert result == {"Alastor Wu": {"padenot": 1, "emilio": 1}}

    def test_skips_authors_with_no_individual_reviewers(self):
        commits = [_C("Someone", [_r(GROUP, True)])]
        assert author_reviewer_pairs(commits, members=MEMBERS) == {}
