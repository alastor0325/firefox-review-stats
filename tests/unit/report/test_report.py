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

    def test_member_authored_counts_match_top_authors(self):
        """For every member who shows up in `top_total`, the count in
        `member_authored_counts` must equal the count in the chart's
        row — same source, same alias collapse, no drift between the
        Top Authors chart and the Member Profile tile.
        """
        commits = [
            _commit(
                datetime(2026, 5, 15, tzinfo=timezone.utc),
                [_r(GROUP, True), _r("padenot")],
                author="Paul Adenot",
            ),
        ] * 3 + [
            _commit(
                datetime(2026, 5, 10, tzinfo=timezone.utc),
                [_r("padenot")],
                author="Alastor Wu",
            ),
        ] * 7
        report = build_report(
            commits,
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        # Verify the consistency invariant.
        members = report["members"]
        top_by_name = {r["name"]: r["count"] for r in report["authors"]["top_total"]}
        for member, count in report["member_authored_counts"].items():
            canonical = members[member]
            if canonical in top_by_name:
                assert count == top_by_name[canonical], (
                    f"member_authored_counts[{member!r}] = {count}, "
                    f"but Top Authors row {canonical!r} = {top_by_name[canonical]}"
                )

    def test_team_views_keys(self):
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        assert set(report["team_views"].keys()) == {"1m", "3m", "6m"}

    def test_six_month_view_matches_top_level(self):
        # Top-level fields alias `team_views["6m"]` — the 6-Month
        # period toggle reads from there, so any drift would mean the
        # default page render and the 6-Month button show different
        # numbers for the same data. Anchoring the 6m slot at the
        # caller's window_start (not a strict 180-day cap) is what
        # makes this invariant hold.
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        six_m = report["team_views"]["6m"]
        assert six_m["summary"] == report["summary"]
        assert six_m["concentration"] == report["concentration"]
        assert six_m["within_group_total"] == report["within_group_total"]
        assert six_m["sole_reviewer"] == report["sole_reviewer"]
        assert six_m["total_reviews_per_member"] == report["total_reviews_per_member"]
        assert six_m["authors"] == report["authors"]

    def test_one_month_view_is_narrower_than_six(self):
        # 1m slot drops the older `2026-04-01` commits — verifying the
        # narrowing actually fires, not just that the field exists.
        report = build_report(
            _make_commits(),
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 11, 15, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        one_m = report["team_views"]["1m"]
        six_m = report["team_views"]["6m"]
        # 6m sees all 5 commits; 1m only the three from May.
        assert six_m["summary"]["total_patches"] == 5
        assert one_m["summary"]["total_patches"] == 3

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
