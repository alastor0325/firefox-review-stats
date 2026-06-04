"""Unit tests for the pure recent-changes aggregation helpers."""

from reviewstats.recent_changes import (
    FEATURE_LABELS,
    group_by_feature,
    humanize_feature,
)


class TestHumanizeFeature:
    def test_known_label(self):
        assert humanize_feature("mediasource") == FEATURE_LABELS["mediasource"]

    def test_top_level_bucket(self):
        assert humanize_feature("(top-level)") == "General / top-level"

    def test_unknown_bucket(self):
        assert humanize_feature("(unknown)") == "Other"

    def test_fallback_humanizes_leaf(self):
        # Not in the table — title-case the leaf, splitting on separators.
        assert humanize_feature("some_new-dir") == "Some New Dir"

    def test_fallback_uses_leaf_of_path(self):
        # A full multi-root path with no exact entry falls back to its leaf.
        assert humanize_feature("dom/media/somethingnew") == "Somethingnew"

    def test_full_path_label_wins_over_leaf(self):
        # Multi-root buckets carry full paths; an exact entry takes priority.
        assert "dom/media/systemservices" in FEATURE_LABELS
        assert (
            humanize_feature("dom/media/systemservices")
            == FEATURE_LABELS["dom/media/systemservices"]
        )


def _row(subdir, *, sha, date, dr=None, subject="x", author="a"):
    return {
        "primary_subdir": subdir,
        "sha": sha,
        "short_sha": sha[:12],
        "date": date,
        "differential_revision": dr,
        "subject": subject,
        "author": author,
        "bug": None,
    }


class TestGroupByFeature:
    def test_buckets_and_counts(self):
        rows = [
            _row("mediasource", sha="a1", date="2026-06-01"),
            _row("mediasource", sha="a2", date="2026-06-02"),
            _row("eme", sha="b1", date="2026-06-03"),
        ]
        groups = group_by_feature(rows)
        by_feature = {g["feature"]: g for g in groups}
        assert by_feature["mediasource"]["count"] == 2
        assert by_feature["eme"]["count"] == 1
        assert by_feature["mediasource"]["label"] == FEATURE_LABELS["mediasource"]

    def test_sorted_by_count_then_label(self):
        rows = [
            _row("eme", sha="b1", date="2026-06-03"),
            _row("mediasource", sha="a1", date="2026-06-01"),
            _row("mediasource", sha="a2", date="2026-06-02"),
        ]
        groups = group_by_feature(rows)
        # mediasource (2) before eme (1)
        assert [g["feature"] for g in groups] == ["mediasource", "eme"]

    def test_tie_count_breaks_alphabetically_by_label(self):
        rows = [
            _row("webaudio", sha="w1", date="2026-06-01"),
            _row("eme", sha="e1", date="2026-06-02"),
        ]
        groups = group_by_feature(rows)
        labels = [g["label"] for g in groups]
        assert labels == sorted(labels)

    def test_dedups_relands_by_differential_revision(self):
        # Same D-number landed twice (backout + reland) → one patch item,
        # keeping the most recent landing date.
        rows = [
            _row("eme", sha="old", date="2026-06-01", dr="D100"),
            _row("eme", sha="new", date="2026-06-05", dr="D100"),
        ]
        groups = group_by_feature(rows)
        assert len(groups) == 1
        patches = groups[0]["patches"]
        assert len(patches) == 1
        assert patches[0]["date"] == "2026-06-05"

    def test_patches_sorted_newest_first(self):
        rows = [
            _row("eme", sha="e1", date="2026-06-01", dr="D1"),
            _row("eme", sha="e2", date="2026-06-09", dr="D2"),
            _row("eme", sha="e3", date="2026-06-05", dr="D3"),
        ]
        patches = group_by_feature(rows)[0]["patches"]
        assert [p["date"] for p in patches] == [
            "2026-06-09", "2026-06-05", "2026-06-01",
        ]

    def test_empty(self):
        assert group_by_feature([]) == []

    def test_rows_without_dr_dedup_by_sha(self):
        # No D-number: each commit is its own item (keyed by sha).
        rows = [
            _row("eme", sha="e1", date="2026-06-01"),
            _row("eme", sha="e2", date="2026-06-02"),
        ]
        assert group_by_feature(rows)[0]["count"] == 2
