"""Tests for the Team-view summary-grid contract.

The 'Group-only patches' tile was deadweight in dom/media — the
team's tagging convention always names a specific reviewer, so the
metric was pinned at 0 across the entire 6-month window. Its sister
'% with named individual' was pinned at 100% for the same reason.
Both are removed; the report dict no longer carries those fields.
"""

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.render import render_html
from reviewstats.report import build_report
from datetime import datetime, timezone


_MINIMAL_DATA = {
    "meta": {"path": "x", "group": "g",
             "window_start": "2026-05-01", "window_end": "2026-05-15",
             "generated_at": "2026-05-15T00:00:00Z"},
    "summary": {"total_patches": 0, "group_tagged_patches": 0,
                "group_tagged_pct": 0, "unique_individuals": 0,
                "avg_per_week": 0},
    "concentration": {"top1_share": 0, "top3_share": 0, "top5_share": 0,
                       "gini": 0, "bus_factor": 0},
    "within_group_total": [], "sole_reviewer": [],
    "total_reviews_per_member": [],
    "weekly_trend": {"weeks": [], "top_reviewers": [],
                      "all_members": {}, "authored_per_member": {}},
    "members": {}, "authors": {"top_total": [], "reviewer_matrix": {}},
    "per_member_authors": {}, "member_authored_counts": {},
}


def test_group_only_tile_removed_from_template():
    """The 'Group-only patches' tile must not render in the
    summary grid."""
    html = render_html(_MINIMAL_DATA)
    assert "Group-only patches" not in html, (
        "'Group-only patches' tile was always 0 for dom/media — "
        "drop it from the summary grid."
    )


def test_summary_does_not_reference_group_only_fields_in_js():
    """The JS must not reference s.group_only / s.group_only_pct
    anymore — those fields no longer exist on the summary."""
    html = render_html(_MINIMAL_DATA)
    assert "s.group_only" not in html
    assert "s.group_only_pct" not in html


def test_report_summary_omits_group_only_and_with_individual_fields():
    """End-to-end: build_report must not emit fields that have no UI."""
    commits = [
        Commit(
            sha="a" * 12,
            date=datetime(2026, 5, 12, tzinfo=timezone.utc),
            author="Alastor Wu",
            subject="Bug 1 - x. r=padenot,media-playback-reviewers",
            reviewers=[
                Reviewer("padenot", False),
                Reviewer("media-playback-reviewers", True),
            ],
            differential_revision="D9999",
        ),
    ]
    report = build_report(
        commits,
        group="media-playback-reviewers",
        path="dom/media",
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
    )
    summary_keys = set(report["summary"].keys())
    assert "group_only" not in summary_keys
    assert "group_only_pct" not in summary_keys
    assert "with_individual_named" not in summary_keys
    assert "with_individual_pct" not in summary_keys

    # And the kept fields still resolve as expected.
    assert summary_keys == {
        "total_patches",
        "group_tagged_patches",
        "group_tagged_pct",
        "landed_without_team_review",
        "landed_without_team_review_pct",
        "unique_individuals",
        "avg_per_week",
    }
