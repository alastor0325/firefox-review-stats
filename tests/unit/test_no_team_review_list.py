"""Tests for the patch-list sub-section inside the 'Landed without
team review' nested-detail panel.

The pie chart told users the *shape* of the bypass — which subdirs
were affected. The list adds the *contents*: actual patches, with
their D-numbers, authors, reviewers, and primary subdir, so the
team can drill into specific landings worth following up on.

The list is one level deeper than the pie (foldable inside the
already-expanded panel) to keep the Team view uncluttered.
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.render import render_html
from reviewstats.report import build_report


GROUP = "media-playback-reviewers"


def _c(reviewers):
    return Commit(
        sha="a" * 40,
        date=datetime(2026, 5, 12, tzinfo=timezone.utc),
        author="X",
        subject="Bug 1 - thing",
        reviewers=reviewers,
        differential_revision="D9999",
    )


def test_report_exposes_no_team_review_list():
    """build_report must surface the structured list — not just the
    count and the by-subdir breakdown — so the frontend can render a
    drill-down table."""
    rows = [
        {
            "sha": "a" * 40,
            "short_sha": "a" * 12,
            "date": "2026-05-12",
            "author": "X",
            "subject": "Bug 1 - thing",
            "reviewers": [{"name": "outsider", "is_group": False}],
            "differential_revision": "D9999",
            "primary_subdir": "(top-level)",
        },
    ]
    report = build_report(
        [],
        group=GROUP,
        path="dom/media",
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        no_team_review_list=rows,
    )
    assert report["summary"]["landed_without_team_review_list"] == rows


def test_report_defaults_to_empty_list():
    """Callers that don't pass `no_team_review_list` should still
    get a valid summary — empty list, not missing key."""
    report = build_report(
        [_c([Reviewer(GROUP, True), Reviewer("padenot", False)])],
        group=GROUP,
        path="dom/media",
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
    )
    assert report["summary"]["landed_without_team_review_list"] == []


def _minimal_data():
    return {
        "meta": {"path": "dom/media", "group": "g", "excludes": [],
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 0, "group_tagged_patches": 0,
                    "group_tagged_pct": 0,
                    "landed_without_team_review": 0,
                    "landed_without_team_review_pct": 0,
                    "landed_without_team_review_by_subdir": {},
                    "landed_without_team_review_list": [],
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


def test_template_has_foldable_sub_details_block():
    """The list lives inside a native <details> so folding is
    keyboard-accessible and works without JS — the JS only lazy-
    builds the table on first open."""
    html = render_html(_minimal_data())
    assert '<details class="sub-details"' in html
    assert 'id="no-team-review-list-details"' in html
    assert "<summary>Full patch list" in html


def test_template_lazily_builds_table_on_first_open():
    """The toggle listener must call the build function only on
    open (not on close), and the function must be idempotent so
    repeated opens don't re-render."""
    html = render_html(_minimal_data())
    assert "function buildNoTeamReviewTable()" in html
    assert "if (noTeamReviewTableBuilt) return;" in html
    assert ".addEventListener('toggle'" in html
    assert "if (e.target.open) buildNoTeamReviewTable();" in html


def test_template_visually_nests_list_under_detail_panel():
    """The list block must wear `.sub-details` styling (one indent
    deeper than `.nested-detail`) so the hierarchy reads as
    summary → detail panel → list, not as three peer sections."""
    html = render_html(_minimal_data())
    assert ".sub-details {" in html
    # border-left thinner than the parent's 3px accent border so
    # the visual hierarchy is unambiguous.
    assert "border-left: 2px solid #cbd5e1;" in html
