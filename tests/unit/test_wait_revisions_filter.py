"""`member_authored_wait_revisions` is the gate that keeps the
team-level Review-wait-time histogram (Team View / Phab section) and
the input to weekly-median trends from including non-member-authored
patches.

These tests pin that contract — if anyone accidentally drops the
filter, the histogram would start pulling in cross-team / drive-by
patches and skew the team-level numbers.
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.wait_time import (
    composite_wait_seconds,
    member_authored_wait_revisions,
)


MEMBERS = frozenset({"alwu", "padenot"})


def _commit(d: str) -> Commit:
    return Commit(
        sha="x" * 12,
        date=datetime(2026, 5, 15, tzinfo=timezone.utc),
        author="git-name",
        subject="Bug 1 - foo. r=padenot",
        reviewers=[Reviewer("padenot", False)],
        differential_revision=d,
    )


def _raw(
    author: str | None,
    queue_seconds: int | None = 3600,
    first_reviewer: str | None = "padenot",
) -> dict:
    return {
        "author": author,
        "queue_seconds": queue_seconds,
        "first_member_review": (
            {"actor": first_reviewer, "action": "accept"}
            if first_reviewer else None
        ),
    }


class TestMemberFilterContract:
    def test_includes_member_authored(self):
        raw = {"D1": _raw("alwu"), "D2": _raw("padenot")}
        commits = {"D1": _commit("D1"), "D2": _commit("D2")}
        result = member_authored_wait_revisions(
            ["D1", "D2"], raw, commits, members=MEMBERS,
        )
        assert {r["d_number"] for r in result} == {"D1", "D2"}

    def test_excludes_non_member_author(self):
        """The bug this test guards: a non-member-authored patch
        leaking into the team-level wait-time histogram inflates the
        denominator and biases the percentiles."""
        raw = {
            "D1": _raw("alwu"),
            "D2": _raw("emilio"),        # not in MEMBERS
            "D3": _raw("Michael Froman"),  # not in MEMBERS
        }
        commits = {d: _commit(d) for d in raw}
        result = member_authored_wait_revisions(
            list(raw), raw, commits, members=MEMBERS,
        )
        d_numbers = {r["d_number"] for r in result}
        assert d_numbers == {"D1"}, (
            f"non-member-authored revisions leaked through: {d_numbers}"
        )

    def test_excludes_unknown_author(self):
        """If raw_data's `author` is None (Phab page was a Login
        redirect for a security revision), the row must be excluded —
        we can't know it's member-authored."""
        raw = {"D1": _raw(None)}
        commits = {"D1": _commit("D1")}
        result = member_authored_wait_revisions(
            ["D1"], raw, commits, members=MEMBERS,
        )
        assert result == []

    def test_excludes_missing_queue_seconds(self):
        """No queue-time → can't measure wait, drop the row."""
        raw = {"D1": _raw("alwu", queue_seconds=None)}
        commits = {"D1": _commit("D1")}
        result = member_authored_wait_revisions(
            ["D1"], raw, commits, members=MEMBERS,
        )
        assert result == []

    def test_excludes_missing_commit(self):
        raw = {"D1": _raw("alwu")}
        commits = {}  # No commit known for D1
        result = member_authored_wait_revisions(
            ["D1"], raw, commits, members=MEMBERS,
        )
        assert result == []

    def test_accepts_callable_raw_loader(self):
        """`analyze_phab.py` passes `_load_existing` (a callable) so the
        function must accept either a Mapping or a Callable."""
        store = {"D1": _raw("alwu")}
        commits = {"D1": _commit("D1")}
        result = member_authored_wait_revisions(
            ["D1"], store.get, commits, members=MEMBERS,
        )
        assert len(result) == 1

    def test_row_fields(self):
        raw = {"D1": _raw("alwu", queue_seconds=2 * 86400,
                          first_reviewer="padenot")}
        commits = {"D1": _commit("D1")}
        result = member_authored_wait_revisions(
            ["D1"], raw, commits, members=MEMBERS,
        )
        row = result[0]
        assert row["d_number"] == "D1"
        assert row["wait_days"] == 2.0
        assert row["reviewer"] == "padenot"
        # iso_week formatting (YYYY-Www); just sanity-check the shape.
        assert row["week"].startswith("2026-W")


class TestCompositeWait:
    """The team-histogram and Wait Queue table use a composite anchor:
    prefer creation-anchored timings, fall back to queue-anchored
    when creation has paged off the timeline. This is what makes
    every long-wait patch show up in both views consistently —
    paginated-old patches don't disappear, freshly-created patches
    without group-tag don't disappear either.
    """

    def test_prefers_creation_when_available(self):
        raw = {
            "time_to_react_seconds": 3600,
            "time_to_accept_seconds": 7200,
            "queue_seconds": 999_999,           # would be selected if we fell back
            "queue_to_accept_seconds": 888_888,
        }
        react, accept, anchor = composite_wait_seconds(raw)
        assert react == 3600 and accept == 7200 and anchor == "creation"

    def test_falls_back_to_queue_when_creation_missing(self):
        raw = {
            "time_to_react_seconds": None,
            "time_to_accept_seconds": None,
            "queue_seconds": 48 * 86400,
            "queue_to_accept_seconds": 50 * 86400,
        }
        react, accept, anchor = composite_wait_seconds(raw)
        assert react == 48 * 86400
        assert accept == 50 * 86400
        assert anchor == "queue-added"

    def test_returns_none_when_neither_anchor_available(self):
        raw = {}
        react, accept, anchor = composite_wait_seconds(raw)
        assert react is None and accept is None and anchor is None

    def test_creation_anchor_with_only_react_present(self):
        """Patch reacted but not accepted yet — creation anchor still
        valid, accept is just None."""
        raw = {
            "time_to_react_seconds": 100,
            "time_to_accept_seconds": None,
        }
        react, accept, anchor = composite_wait_seconds(raw)
        assert react == 100 and accept is None and anchor == "creation"


class TestCompositeHistogramInclusion:
    """End-to-end: a revision missing `created_at` (D276526-style)
    must still surface in the team-level wait-time histogram via the
    queue-anchored fallback."""

    def test_paginated_old_revision_still_counted(self):
        raw = {
            "D-old": {
                "author": "alwu",
                # No time_to_* — create event was paginated out
                "time_to_react_seconds": None,
                "time_to_accept_seconds": None,
                # But the queue-add event was captured
                "queue_seconds": 70 * 86400,
                "queue_to_accept_seconds": 75 * 86400,
                "first_member_review": {"actor": "padenot", "action": "accept"},
            }
        }
        commits = {"D-old": _commit("D-old")}
        result = member_authored_wait_revisions(
            ["D-old"], raw, commits, members=MEMBERS,
        )
        assert len(result) == 1
        assert result[0]["wait_days"] == 70.0
        assert result[0]["reviewer"] == "padenot"


class TestEdgeCases:
    def test_empty_members_excludes_all(self):
        raw = {"D1": _raw("alwu")}
        commits = {"D1": _commit("D1")}
        result = member_authored_wait_revisions(
            ["D1"], raw, commits, members=frozenset(),
        )
        assert result == []

    def test_empty_d_numbers(self):
        result = member_authored_wait_revisions(
            [], {}, {}, members=MEMBERS,
        )
        assert result == []
