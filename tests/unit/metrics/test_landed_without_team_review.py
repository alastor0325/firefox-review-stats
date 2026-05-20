"""Tests for `landed_without_team_review`.

Surfaces the count of dom/media patches that landed with neither
the team's review group tag nor any listed-member individual
reviewer — i.e. nobody on the listed-member roster reviewed the
change. A non-zero value is a queue-health red flag.
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.metrics import landed_without_team_review
from reviewstats.parse import Reviewer
from reviewstats.report import build_report
from reviewstats.render import render_html


GROUP = "media-playback-reviewers"
MEMBERS = frozenset({"alwu", "padenot", "kinetik"})


def _c(reviewers, sha="x" * 12):
    return Commit(
        sha=sha,
        date=datetime(2026, 5, 12, tzinfo=timezone.utc),
        author="Some Author",
        subject="Bug 1 - thing",
        reviewers=reviewers,
        differential_revision="D" + sha[:5],
    )


def test_group_tagged_patch_is_not_counted():
    commits = [_c([Reviewer(GROUP, True), Reviewer("padenot", False)])]
    assert landed_without_team_review(commits, group=GROUP, members=MEMBERS) == 0


def test_named_member_without_group_is_not_counted():
    """A patch reviewed by a listed member directly (no group tag)
    still gets team oversight — must not count as 'without review'."""
    commits = [_c([Reviewer("alwu", False)])]
    assert landed_without_team_review(commits, group=GROUP, members=MEMBERS) == 0


def test_patch_with_neither_group_nor_member_is_counted():
    """The exact bad case: landed with reviewers, but none from the
    team roster and no group tag."""
    commits = [_c([Reviewer("outsider", False)])]
    assert landed_without_team_review(commits, group=GROUP, members=MEMBERS) == 1


def test_patch_with_no_reviewers_is_counted():
    """No reviewers at all = no team oversight."""
    commits = [_c([])]
    assert landed_without_team_review(commits, group=GROUP, members=MEMBERS) == 1


def test_patch_with_only_other_team_group_is_counted():
    """Sibling-team group tags (e.g. webrtc-reviewers) don't satisfy
    'team review' for this team."""
    commits = [
        _c([Reviewer("webrtc-reviewers", True), Reviewer("someone-else", False)])
    ]
    assert landed_without_team_review(commits, group=GROUP, members=MEMBERS) == 1


def test_summary_carries_count_and_pct():
    """End-to-end: build_report exposes landed_without_team_review +
    landed_without_team_review_pct on the summary dict."""
    commits = [
        _c([Reviewer(GROUP, True), Reviewer("padenot", False)], sha="a" * 12),
        _c([Reviewer("alwu", False)], sha="b" * 12),
        _c([Reviewer("outsider", False)], sha="c" * 12),
        _c([], sha="d" * 12),
    ]
    # Use MEMBER_IDS from the real members module via build_report.
    # alwu/padenot are real listed members; "outsider" + empty = 2 bad.
    report = build_report(
        commits,
        group=GROUP,
        path="dom/media",
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
    )
    s = report["summary"]
    assert s["landed_without_team_review"] == 2
    assert s["landed_without_team_review_pct"] == 2 / 4


def test_template_renders_the_tile():
    minimal = {
        "meta": {"path": "x", "group": "g",
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 4, "group_tagged_patches": 1,
                    "group_tagged_pct": 0.25,
                    "landed_without_team_review": 2,
                    "landed_without_team_review_pct": 0.5,
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
    assert "Landed without team review" in html
    assert "s.landed_without_team_review" in html
