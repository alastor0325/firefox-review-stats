"""Tests for `primary_subdir` and the by-subdir classifier.

`primary_subdir` answers: given a commit's file list and a root path
(e.g. `dom/media`), which immediate subdirectory of that path best
represents this commit? Used to bucket 'Landed without team review'
patches into a pie chart so users can tell apart 'real playback
bypass' from 'lives under dom/media/ but owned by an adjacent team'.
"""

from reviewstats.metrics import (
    classify_landed_without_team_review_by_subdir,
    primary_subdir,
)


class _Commit:
    def __init__(self, sha: str):
        self.sha = sha


PATH = "dom/media"


def test_picks_subdir_with_most_files():
    files = [
        "dom/media/webspeech/a.cpp",
        "dom/media/webspeech/b.cpp",
        "dom/media/gtest/c.cpp",
    ]
    assert primary_subdir(files, path=PATH) == "webspeech"


def test_top_level_files_under_path_bucket_separately():
    """Files directly under dom/media/ (no subdir) get a synthetic
    `(top-level)` bucket — they shouldn't be misclassified into the
    first subdir alphabetically."""
    files = [
        "dom/media/MediaThing.cpp",
        "dom/media/MediaOther.cpp",
        "dom/media/webspeech/x.cpp",
    ]
    assert primary_subdir(files, path=PATH) == "(top-level)"


def test_files_outside_path_are_ignored():
    """A cross-cutting refactor touching dom/media/x.cpp plus 100
    accessible/ files still belongs in the dom/media `x.cpp` bucket
    — the question is *where in dom/media* did this land."""
    files = [
        "accessible/foo.cpp",
        "accessible/bar.cpp",
        "accessible/baz.cpp",
        "dom/media/mediacapabilities/d.cpp",
    ]
    assert primary_subdir(files, path=PATH) == "mediacapabilities"


def test_returns_none_when_no_files_under_path():
    """Possible only when the GitHub `files` array got truncated past
    the 300-entry cap and dom/media files were beyond it. Caller can
    bucket as '(unknown)'."""
    files = ["accessible/x.cpp", "layout/y.cpp"]
    assert primary_subdir(files, path=PATH) is None


def test_tie_broken_alphabetically_for_determinism():
    """If two subdirs tie on file count, alphabetical first wins so
    consecutive regens produce the same data — pinned for stable
    diffs."""
    files = [
        "dom/media/webaudio/x.cpp",
        "dom/media/webaudio/y.cpp",
        "dom/media/gtest/a.cpp",
        "dom/media/gtest/b.cpp",
    ]
    assert primary_subdir(files, path=PATH) == "gtest"


def test_classifier_aggregates_by_primary_subdir():
    pairs = [
        (_Commit("a"), [
            "dom/media/systemservices/x.cpp",
            "dom/media/systemservices/y.cpp",
        ]),
        (_Commit("b"), [
            "dom/media/webspeech/a.cpp",
        ]),
        (_Commit("c"), [
            "dom/media/systemservices/n.cpp",
        ]),
        (_Commit("d"), [
            "accessible/only.cpp",  # no dom/media file at all
        ]),
    ]
    counts = classify_landed_without_team_review_by_subdir(pairs, path=PATH)
    assert counts == {
        "systemservices": 2,
        "webspeech": 1,
        "(unknown)": 1,
    }


def test_classifier_returns_empty_for_no_commits():
    assert classify_landed_without_team_review_by_subdir([], path=PATH) == {}


def test_pie_renders_when_data_present():
    """The Team view should reveal #landed-without-review-section
    and bind a doughnut chart to #chart-no-team-review when
    summary.landed_without_team_review_by_subdir has entries."""
    from reviewstats.render import render_html

    minimal = {
        "meta": {"path": "dom/media", "group": "g",
                 "excludes": [],
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 0, "group_tagged_patches": 0,
                    "group_tagged_pct": 0,
                    "landed_without_team_review": 0,
                    "landed_without_team_review_pct": 0,
                    "landed_without_team_review_by_subdir": {},
                    "unique_individuals": 0, "avg_per_week": 0},
        "concentration": {"top1_share": 0, "top3_share": 0, "top5_share": 0,
                           "gini": 0, "bus_factor": 0},
        "within_group_total": [], "sole_reviewer": [],
        "total_reviews_per_member": [],
        "weekly_trend": {"weeks": [], "top_reviewers": [],
                          "all_members": {}, "authored_per_member": {}},
        "members": {}, "authors": {"top_total": [], "reviewer_matrix": {}},
        "per_member_authors": {}, "member_authored_counts": {},
    }
    html = render_html(minimal)
    assert "chart-no-team-review" in html
    assert "landed-without-review-section" in html
    # JS short-circuits when there are no entries.
    assert "if (ntrEntries.length === 0)" in html
    # The chart is lazy — built inside the toggle function, not on
    # initial render — so the 'Landed without team review' tile is
    # tagged expandable and wires a click handler.
    assert "noTeamTile.classList.add('expandable')" in html
    assert "noTeamTile.addEventListener('click', toggleNoTeamReviewSection)" in html
    # Pie chart is created lazily; one instance only.
    assert "let noTeamReviewChart = null;" in html
