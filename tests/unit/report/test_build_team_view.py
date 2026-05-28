from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.report import build_team_view


GROUP = "media-playback-reviewers"


def _commit(
    date: datetime,
    reviewers: list[Reviewer],
    author: str = "Tester",
) -> Commit:
    return Commit(
        sha="x" * 7,
        date=date,
        author=author,
        subject="Bug 1 - x. r=...",
        reviewers=reviewers,
    )


def _r(name: str, is_group: bool = False) -> Reviewer:
    return Reviewer(name, is_group=is_group)


def _commits_in_window() -> list[Commit]:
    return [
        _commit(
            datetime(2026, 5, 15, tzinfo=timezone.utc),
            [_r(GROUP, True), _r("padenot")],
        ),
        _commit(
            datetime(2026, 5, 10, tzinfo=timezone.utc),
            [_r(GROUP, True), _r("padenot")],
        ),
        _commit(
            datetime(2026, 5, 8, tzinfo=timezone.utc),
            [_r(GROUP, True), _r("alwu")],
        ),
        _commit(
            datetime(2026, 5, 1, tzinfo=timezone.utc),
            [_r("emilio")],  # not group-tagged, no listed reviewer
        ),
    ]


class TestBuildTeamView:
    def test_returns_window_dates(self):
        view = build_team_view(
            _commits_in_window(),
            group=GROUP,
            members={"padenot": "Paul", "alwu": "Alastor"},
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert view["window_start"] == "2026-05-01"
        assert view["window_end"] == "2026-05-28"

    def test_summary_counts(self):
        view = build_team_view(
            _commits_in_window(),
            group=GROUP,
            members={"padenot": "Paul", "alwu": "Alastor"},
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        s = view["summary"]
        assert s["total_patches"] == 4
        assert s["group_tagged_patches"] == 3
        assert s["landed_without_team_review"] == 1
        # avg_per_week is total_group_tagged / weeks_in_window — keep the
        # same definition build_report uses so callers see the same number
        # for the 6m slice.
        assert s["avg_per_week"] > 0

    def test_within_group_distribution(self):
        view = build_team_view(
            _commits_in_window(),
            group=GROUP,
            members={"padenot": "Paul", "alwu": "Alastor"},
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        dist = {r["name"]: r["count"] for r in view["within_group_total"]}
        assert dist == {"padenot": 2, "alwu": 1}

    def test_concentration_keys_present(self):
        view = build_team_view(
            _commits_in_window(),
            group=GROUP,
            members={"padenot": "Paul", "alwu": "Alastor"},
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        for key in ("top1_share", "top3_share", "top5_share", "gini", "bus_factor"):
            assert key in view["concentration"]

    def test_filters_no_team_review_list_by_window(self):
        # Caller supplies the FULL 6-month bad-commit list; the view
        # for a 1-month window must include only rows dated in that
        # window. Same goes for the per-subdir bucket counts (which
        # are re-derived from the filtered list).
        full_list = [
            {"date": "2026-05-20", "primary_subdir": "webcodecs",
             "subject": "in window", "reviewers": []},
            {"date": "2026-05-20", "primary_subdir": "webcodecs",
             "subject": "in window 2", "reviewers": []},
            {"date": "2026-03-01", "primary_subdir": "platforms",
             "subject": "out of window", "reviewers": []},
        ]
        view = build_team_view(
            _commits_in_window(),
            group=GROUP,
            members={"padenot": "Paul", "alwu": "Alastor"},
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
            no_team_review_list=full_list,
        )
        in_list = view["summary"]["landed_without_team_review_list"]
        assert [r["subject"] for r in in_list] == ["in window", "in window 2"]
        # Subdir buckets are re-counted over the filtered list so a
        # bucket with all rows out of window disappears entirely.
        by_subdir = view["summary"]["landed_without_team_review_by_subdir"]
        assert by_subdir == {"webcodecs": 2}

    def test_does_not_include_weekly_trend(self):
        # weekly_trend is a 6-month view (matches the Per-Week toggle),
        # not a per-window field. Keeping it out of team_view prevents
        # the rendered JSON from duplicating it three times.
        view = build_team_view(
            _commits_in_window(),
            group=GROUP,
            members={"padenot": "Paul", "alwu": "Alastor"},
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )
        assert "weekly_trend" not in view
        assert "members" not in view
        assert "per_member_authors" not in view
        assert "member_authored_counts" not in view
