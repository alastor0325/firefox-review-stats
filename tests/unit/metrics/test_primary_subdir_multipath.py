"""Tests for the multi-root mode of `primary_subdir` and the
matching classifier.

Single-path teams (Playback) get fine-grained subdir buckets
(`webaudio`, `gtest`, `mediacapabilities`, etc.). Multi-path teams
(WebRTC owns dom/media/webrtc + dom/media/systemservices) need a
different bucketing strategy: the meaningful question for a WebRTC
patch is "which root did this land in", not "which audio sub-dir
under dom/media/webrtc".

So `paths=(...)` mode buckets by root path. The longest matching
prefix wins so that `dom/media/webrtc/audio/x.cpp` doesn't get
mis-attributed to a `dom/media` root if both happen to be passed.
"""

import pytest

from reviewstats.metrics import (
    classify_landed_without_team_review_by_subdir,
    primary_subdir,
)


WEBRTC_ROOTS = ("dom/media/webrtc", "dom/media/systemservices")


class _Commit:
    def __init__(self, sha: str):
        self.sha = sha


def test_multi_root_picks_root_with_most_files():
    files = [
        "dom/media/webrtc/audio/a.cpp",
        "dom/media/webrtc/video/b.cpp",
        "dom/media/systemservices/c.cpp",
    ]
    assert primary_subdir(files, paths=WEBRTC_ROOTS) == "dom/media/webrtc"


def test_multi_root_ignores_files_outside_all_roots():
    files = [
        "accessible/x.cpp",
        "layout/y.cpp",
        "dom/media/systemservices/z.cpp",
    ]
    assert primary_subdir(files, paths=WEBRTC_ROOTS) == "dom/media/systemservices"


def test_multi_root_returns_none_when_no_file_matches():
    files = ["accessible/x.cpp"]
    assert primary_subdir(files, paths=WEBRTC_ROOTS) is None


def test_multi_root_longest_prefix_wins_for_overlapping_roots():
    """If a hypothetical team owned both 'dom/media' and
    'dom/media/webrtc', a webrtc file should count toward the more
    specific root — not both, not just the lexically-first."""
    files = ["dom/media/webrtc/audio/a.cpp"]
    result = primary_subdir(files, paths=("dom/media", "dom/media/webrtc"))
    assert result == "dom/media/webrtc"


def test_multi_root_tie_broken_alphabetically():
    files = [
        "dom/media/webrtc/a.cpp",
        "dom/media/systemservices/b.cpp",
    ]
    # 1 file each — tie. Alphabetically: 'dom/media/systemservices' < 'dom/media/webrtc'.
    assert primary_subdir(files, paths=WEBRTC_ROOTS) == "dom/media/systemservices"


def test_primary_subdir_rejects_both_path_and_paths():
    """Pass exactly one of `path` or `paths` — both is a programming
    error and must fail loud rather than silently picking one."""
    with pytest.raises(TypeError, match="exactly one"):
        primary_subdir(
            ["dom/media/webrtc/a.cpp"],
            path="dom/media",
            paths=WEBRTC_ROOTS,
        )


def test_primary_subdir_rejects_neither_path_nor_paths():
    with pytest.raises(TypeError, match="exactly one"):
        primary_subdir(["dom/media/webrtc/a.cpp"])


def test_classifier_multi_root_aggregates_by_root_path():
    pairs = [
        (_Commit("a"), ["dom/media/webrtc/a.cpp", "dom/media/webrtc/b.cpp"]),
        (_Commit("b"), ["dom/media/systemservices/c.cpp"]),
        (_Commit("c"), ["dom/media/webrtc/d.cpp"]),
        (_Commit("d"), ["accessible/x.cpp"]),  # outside all roots
    ]
    counts = classify_landed_without_team_review_by_subdir(
        pairs, paths=WEBRTC_ROOTS,
    )
    assert counts == {
        "dom/media/webrtc": 2,
        "dom/media/systemservices": 1,
        "(unknown)": 1,
    }
