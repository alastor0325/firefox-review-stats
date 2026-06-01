"""The header's "generated <time>" stamp is shown in Pacific time.

The refresh runs in CI (UTC), but the dashboard's audience works out of
Portland, so the human-readable timestamp is converted to
America/Los_Angeles at generation time — deterministic and DST-aware
(PDT in summer, PST in winter) rather than relying on the viewer's
browser locale. The machine-readable `generated_at` ISO string is kept
untouched for provenance.
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.report import build_report, format_generated_at


GROUP = "media-playback-reviewers"


def _commit():
    return Commit(
        sha="a" * 12,
        date=datetime(2026, 5, 12, tzinfo=timezone.utc),
        author="A",
        subject="Bug 1 - thing. r=media-playback-reviewers,padenot",
        reviewers=[Reviewer(GROUP, True), Reviewer("padenot", False)],
        differential_revision="D9999",
    )


class TestFormatGeneratedAt:
    def test_summer_instant_is_pdt(self):
        # 2026-06-01 17:30 UTC → 10:30 AM Pacific Daylight Time (UTC-7).
        dt = datetime(2026, 6, 1, 17, 30, tzinfo=timezone.utc)
        assert format_generated_at(dt) == "Jun 1, 2026, 10:30 AM PDT"

    def test_winter_instant_is_pst(self):
        # 2026-01-15 18:00 UTC → 10:00 AM Pacific Standard Time (UTC-8).
        dt = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
        assert format_generated_at(dt) == "Jan 15, 2026, 10:00 AM PST"

    def test_naive_datetime_assumed_utc(self):
        """A tz-naive datetime is treated as UTC, not local, so CI and a
        dev box produce the same string."""
        naive = datetime(2026, 6, 1, 17, 30)
        aware = datetime(2026, 6, 1, 17, 30, tzinfo=timezone.utc)
        assert format_generated_at(naive) == format_generated_at(aware)

    def test_non_utc_input_is_converted(self):
        """Input already in another zone is normalised to Pacific, not
        printed verbatim."""
        from datetime import timedelta
        plus2 = timezone(timedelta(hours=2))
        # 19:30 +02:00 == 17:30 UTC == 10:30 PDT.
        dt = datetime(2026, 6, 1, 19, 30, tzinfo=plus2)
        assert format_generated_at(dt) == "Jun 1, 2026, 10:30 AM PDT"


class TestMetaCarriesPacificDisplay:
    def test_meta_has_generated_at_display_in_pacific(self):
        report = build_report(
            [_commit()],
            group=GROUP,
            path="dom/media",
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=datetime(2026, 6, 1, 17, 30, tzinfo=timezone.utc),
        )
        assert report["meta"]["generated_at_display"] == (
            "Jun 1, 2026, 10:30 AM PDT"
        )

    def test_iso_generated_at_is_preserved(self):
        """The raw ISO instant stays for provenance / machine use."""
        gen = datetime(2026, 6, 1, 17, 30, tzinfo=timezone.utc)
        report = build_report(
            [_commit()],
            group=GROUP,
            path="dom/media",
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
            generated_at=gen,
        )
        assert report["meta"]["generated_at"] == gen.isoformat()
