"""Tests for recent-changes assembly in report.py."""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.report import build_recent_changes, build_report


WINDOW_END = datetime(2026, 6, 3, tzinfo=timezone.utc)


def _row(subdir, date, *, sha="s", dr=None, subject="Bug 1 - x"):
    return {
        "primary_subdir": subdir,
        "sha": sha,
        "short_sha": sha[:12],
        "date": date,
        "differential_revision": dr,
        "subject": subject,
        "author": "Tester",
        "bug": "1",
    }


class TestBuildRecentChanges:
    def test_has_both_windows(self):
        rc = build_recent_changes([], window_end=WINDOW_END)
        assert set(rc.keys()) == {"1w", "1m"}
        for w in rc.values():
            assert set(w.keys()) == {
                "window_start", "window_end", "total", "features",
            }

    def test_window_bounds(self):
        rc = build_recent_changes([], window_end=WINDOW_END)
        assert rc["1w"]["window_end"] == "2026-06-03"
        assert rc["1w"]["window_start"] == "2026-05-27"  # 7 days back
        assert rc["1m"]["window_start"] == "2026-05-04"  # 30 days back

    def test_week_excludes_older_than_seven_days(self):
        rows = [
            _row("eme", "2026-06-02", sha="recent", dr="D1"),
            _row("eme", "2026-05-20", sha="old", dr="D2"),  # >7d, within 30d
        ]
        rc = build_recent_changes(rows, window_end=WINDOW_END)
        assert rc["1w"]["total"] == 1
        assert rc["1m"]["total"] == 2

    def test_total_matches_feature_counts(self):
        rows = [
            _row("eme", "2026-06-01", sha="a", dr="D1"),
            _row("mediasource", "2026-06-02", sha="b", dr="D2"),
        ]
        rc = build_recent_changes(rows, window_end=WINDOW_END)
        month = rc["1m"]
        assert month["total"] == sum(g["count"] for g in month["features"])
        assert month["total"] == 2

    def test_features_grouped_and_labelled(self):
        rows = [_row("mediasource", "2026-06-01", sha="a", dr="D1")]
        rc = build_recent_changes(rows, window_end=WINDOW_END)
        feats = rc["1m"]["features"]
        assert feats[0]["feature"] == "mediasource"
        assert feats[0]["label"] == "Media Source Extensions (MSE)"


GROUP = "media-playback-reviewers"


def _commit(date):
    return Commit(
        sha="x" * 7, date=date, author="Tester",
        subject="Bug 1 - x. r=...", reviewers=[Reviewer(GROUP, True)],
    )


class TestBuildReportIntegration:
    def _build(self, **kwargs):
        return build_report(
            [_commit(datetime(2026, 5, 15, tzinfo=timezone.utc))],
            group=GROUP,
            path="dom/media",
            window_start=datetime(2025, 12, 3, tzinfo=timezone.utc),
            window_end=WINDOW_END,
            generated_at=WINDOW_END,
            **kwargs,
        )

    def test_recent_changes_present_when_rows_given(self):
        report = self._build(
            recent_rows=[_row("eme", "2026-06-01", sha="a", dr="D1")]
        )
        assert "recent_changes" in report
        assert report["recent_changes"]["1m"]["total"] == 1

    def test_recent_changes_omitted_when_no_rows(self):
        # Legacy-safe: no key at all when the caller doesn't supply rows,
        # so the template's `if (!DATA.recent_changes)` guard hides the tab.
        report = self._build()
        assert "recent_changes" not in report
