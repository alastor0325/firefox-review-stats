from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.report import build_report


GROUP = "media-playback-reviewers"


def _commit(
    date: datetime, reviewers: list[Reviewer], author: str = "Tester"
) -> Commit:
    return Commit(
        sha="x" * 7,
        date=date,
        author=author,
        subject="Bug 1 - x. r=...",
        reviewers=reviewers,
    )


def _r(name, is_group=False):
    return Reviewer(name, is_group=is_group)


def _make_commits():
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
            datetime(2026, 4, 1, tzinfo=timezone.utc),
            [_r(GROUP, True)],  # group-only
        ),
        _commit(
            datetime(2026, 4, 1, tzinfo=timezone.utc),
            [_r("emilio")],  # not group-tagged
        ),
    ]


class TestBuildReport:
    def test_meta_window(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, 9, 0, tzinfo=timezone.utc),
        )
        assert report["meta"]["path"] == "dom/media"
        assert report["meta"]["group"] == GROUP
        assert report["meta"]["window_start"] == "2025-11-15"
        assert report["meta"]["window_end"] == "2026-05-15"

    def test_summary_counts(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        s = report["summary"]
        assert s["total_patches"] == 5
        assert s["group_tagged_patches"] == 4
        assert s["with_individual_named"] == 3
        assert s["group_only"] == 1
        assert s["unique_individuals"] == 2

    def test_within_group_distribution(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        dist = {row["name"]: row["count"] for row in report["within_group_total"]}
        assert dist == {"padenot": 2, "alwu": 1}

    def test_concentration_present(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        c = report["concentration"]
        for key in ("top1_share", "top3_share", "top5_share", "gini", "bus_factor"):
            assert key in c

    def test_weekly_trend_keys(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        trend = report["weekly_trend"]
        assert "weeks" in trend
        assert "top_reviewers" in trend
        assert "all_members" in trend
        assert trend["top_reviewers"][0] == "padenot"

    def test_per_member_authors_present(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        assert "per_member_authors" in report
        # padenot reviewed 2 patches by 'Tester' in our fixture.
        padenot_authors = report["per_member_authors"].get("padenot", [])
        assert any(a["name"] == "Tester" for a in padenot_authors)
