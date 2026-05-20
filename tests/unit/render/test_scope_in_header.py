"""Tests for the scope-in-header contract.

The page header shows what folder is being monitored and which
subfolders are excluded so a reader can tell at a glance whether
the metrics cover their patch. Without this, the 'Landed without
team review' bucket was confusing — readers couldn't tell whether
something like dom/media/systemservices was in or out of scope.
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.render import render_html
from reviewstats.report import build_report


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


def test_meta_carries_excludes_list():
    report = build_report(
        [_commit()],
        group=GROUP,
        path="dom/media",
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        excludes=("dom/media/webrtc", "dom/media/systemservices"),
    )
    assert report["meta"]["excludes"] == [
        "dom/media/webrtc",
        "dom/media/systemservices",
    ]


def test_meta_excludes_defaults_to_empty_list():
    """Older callers that don't pass `excludes` should still get a
    valid meta dict — empty list, not missing key."""
    report = build_report(
        [_commit()],
        group=GROUP,
        path="dom/media",
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
    )
    assert report["meta"]["excludes"] == []


def test_header_js_renders_excludes_in_scope_string():
    """When excludes are present, the meta line shows them next to
    the path so users see what folders are skipped."""
    minimal = {
        "meta": {"path": "dom/media", "group": "g",
                 "excludes": ["dom/media/webrtc", "dom/media/systemservices"],
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 0, "group_tagged_patches": 0,
                    "group_tagged_pct": 0,
                    "landed_without_team_review": 0,
                    "landed_without_team_review_pct": 0,
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
    # JS reads meta.excludes
    assert "DATA.meta.excludes" in html
    # And constructs a `path (excluding ...)` string
    assert "excluding" in html


def test_header_renders_scope_and_time_on_separate_lines():
    """Header meta is split into two child divs so the scope clause
    doesn't run into the window/generated-at clause when the exclude
    list is long. textContent on adjacent block elements gives a
    natural visual line break without needing CSS to wrap text."""
    minimal = {
        "meta": {"path": "dom/media", "group": "g",
                 "excludes": ["dom/media/webrtc"],
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 0, "group_tagged_patches": 0,
                    "group_tagged_pct": 0,
                    "landed_without_team_review": 0,
                    "landed_without_team_review_pct": 0,
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
    # Two block-level children are appended via appendChild — pin the
    # createElement('div') calls so a future refactor can't silently
    # collapse the layout back to one line.
    assert html.count("document.createElement('div')") >= 2
    assert "hdrMeta.appendChild(scopeLine)" in html
    assert "hdrMeta.appendChild(timeLine)" in html


def test_header_js_graceful_when_excludes_missing():
    """If `excludes` is undefined / empty, the header must still
    render the path cleanly — no `undefined` leaking through."""
    minimal_no_excludes = {
        "meta": {"path": "dom/media", "group": "g",
                 # excludes deliberately omitted
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 0, "group_tagged_patches": 0,
                    "group_tagged_pct": 0,
                    "landed_without_team_review": 0,
                    "landed_without_team_review_pct": 0,
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
    html = render_html(minimal_no_excludes)
    # Guard: `DATA.meta.excludes || []` so undefined is tolerated.
    assert "DATA.meta.excludes || []" in html
