"""Unit tests for the pure recent-changes aggregation helpers."""

from reviewstats.recent_changes import (
    FEATURE_LABELS,
    deep_feature_bucket,
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


class TestDeepFeatureBucket:
    GFX = ("gfx", "image", "dom/canvas", "dom/webgpu")

    def test_one_level_under_matched_root(self):
        files = ["gfx/layers/Compositor.cpp", "gfx/layers/Layer.h"]
        assert deep_feature_bucket(files, self.GFX) == "gfx/layers"

    def test_files_directly_under_root_bucket_as_root(self):
        assert deep_feature_bucket(["gfx/gfxPlatform.cpp"], self.GFX) == "gfx"

    def test_picks_root_with_most_files(self):
        files = ["gfx/wr/a.rs", "gfx/wr/b.rs", "image/test/c.cpp"]
        assert deep_feature_bucket(files, self.GFX) == "gfx/wr"

    def test_separate_top_level_roots(self):
        assert deep_feature_bucket(["dom/canvas/Canvas.cpp"], self.GFX) == "dom/canvas"

    def test_no_match_returns_none(self):
        assert deep_feature_bucket(["js/src/foo.cpp"], self.GFX) is None

    def test_path_equal_to_root_counts_as_root(self):
        # Defensive: a file path exactly equal to a root (no trailing slash)
        # buckets as that root rather than being dropped.
        assert deep_feature_bucket(["gfx"], self.GFX) == "gfx"

    def test_tie_breaks_alphabetically(self):
        files = ["gfx/layers/a.cpp", "gfx/wr/b.rs"]  # 1 each
        assert deep_feature_bucket(files, self.GFX) == "gfx/layers"

    def test_labels_resolve_for_deep_buckets(self):
        # Known deep buckets get friendly labels (not raw leaf title-case).
        assert humanize_feature("gfx/wr") == FEATURE_LABELS["gfx/wr"]
        assert humanize_feature("dom/media/webrtc/transport") == \
            FEATURE_LABELS["dom/media/webrtc/transport"]
