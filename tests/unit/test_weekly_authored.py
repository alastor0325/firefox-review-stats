"""Tests for `weekly_authored_per_member`.

Powers the second line in Member Profile / Weekly activity:
patches the selected member submitted that week.
"""

from datetime import datetime, timezone

from reviewstats.metrics import iso_week, weekly_authored_per_member
from reviewstats.parse import Reviewer


MEMBERS = {
    "alwu": "Alastor Wu",
    "padenot": "Paul Adenot",
    "kinetik": "Matthew Gregan",
}


class _C:
    def __init__(self, author, date, d_number=None, sha="x" * 12):
        self.author = author
        self.date = date
        self.differential_revision = d_number
        self.sha = sha
        self.reviewers = []


def test_buckets_authored_by_week():
    weeks = ["2026-W18", "2026-W19", "2026-W20"]
    commits = [
        _C("Alastor Wu", datetime(2026, 5, 11, tzinfo=timezone.utc), "D1"),  # W20
        _C("Alastor Wu", datetime(2026, 5, 12, tzinfo=timezone.utc), "D2"),  # W20
        _C("Alastor Wu", datetime(2026, 5, 4, tzinfo=timezone.utc), "D3"),   # W19
        _C("Paul Adenot", datetime(2026, 5, 11, tzinfo=timezone.utc), "D4"), # W20
    ]
    result = weekly_authored_per_member(commits, MEMBERS, weeks)
    assert result["alwu"] == [0, 1, 2]
    assert result["padenot"] == [0, 0, 1]
    assert result["kinetik"] == [0, 0, 0]


def test_alias_collapse_maps_to_member_handle():
    """alastor0325 / alwu / 'Alastor Wu' all map to the alwu handle
    via the AUTHOR_ALIASES table in reviewstats.aliases."""
    weeks = ["2026-W20"]
    commits = [
        _C("alastor0325", datetime(2026, 5, 12, tzinfo=timezone.utc), "D1"),
        _C("alwu",        datetime(2026, 5, 12, tzinfo=timezone.utc), "D2"),
        _C("Alastor Wu",  datetime(2026, 5, 12, tzinfo=timezone.utc), "D3"),
    ]
    result = weekly_authored_per_member(commits, MEMBERS, weeks)
    assert result["alwu"] == [3]


def test_dedupes_relands_by_d_number():
    """Multiple commits with the same D-number = back-out + re-land
    of the same patch. Should count as one authored patch in that
    week (or the earliest week if relands cross weeks)."""
    weeks = ["2026-W19", "2026-W20"]
    commits = [
        _C("alwu", datetime(2026, 5, 4, tzinfo=timezone.utc),  "D1"),   # W19
        _C("alwu", datetime(2026, 5, 5, tzinfo=timezone.utc),  "D1"),   # W19 (reland)
        _C("alwu", datetime(2026, 5, 11, tzinfo=timezone.utc), "D1"),   # W20 (another reland)
    ]
    result = weekly_authored_per_member(commits, MEMBERS, weeks)
    # Total should be 1 (the D1 patch), placed in the earliest landing week.
    assert sum(result["alwu"]) == 1


def test_non_member_authors_excluded():
    weeks = ["2026-W20"]
    commits = [
        _C("Andrew Osmond",  datetime(2026, 5, 12, tzinfo=timezone.utc), "D1"),
        _C("Some Outsider",  datetime(2026, 5, 12, tzinfo=timezone.utc), "D2"),
    ]
    result = weekly_authored_per_member(commits, MEMBERS, weeks)
    # MEMBERS only has alwu/padenot/kinetik; Andrew Osmond + Outsider
    # are not in the rotation.
    for handle in MEMBERS:
        assert result[handle] == [0]


def test_returns_zero_filled_for_every_week():
    """Even weeks with no activity must be present in the output so
    the chart aligns correctly with the x-axis labels."""
    weeks = ["2026-W17", "2026-W18", "2026-W19", "2026-W20"]
    commits = [
        _C("alwu", datetime(2026, 5, 12, tzinfo=timezone.utc), "D1"),
    ]
    result = weekly_authored_per_member(commits, MEMBERS, weeks)
    assert result["alwu"] == [0, 0, 0, 1]
    assert len(result["alwu"]) == len(weeks)


def test_commits_outside_week_window_are_dropped():
    """If iso_week(commit.date) isn't in the passed `weeks` list,
    the commit doesn't appear anywhere — protects against silently
    miscounting."""
    weeks = ["2026-W19", "2026-W20"]
    commits = [
        _C("alwu", datetime(2026, 1, 1, tzinfo=timezone.utc), "D1"),  # way old
        _C("alwu", datetime(2026, 5, 12, tzinfo=timezone.utc), "D2"),
    ]
    result = weekly_authored_per_member(commits, MEMBERS, weeks)
    assert sum(result["alwu"]) == 1


def test_report_exposes_authored_per_member():
    """End-to-end: build_report must surface `authored_per_member`
    inside `weekly_trend` so the Member Profile chart can render it."""
    from datetime import datetime, timezone
    from reviewstats.git_log import Commit
    from reviewstats.parse import Reviewer
    from reviewstats.report import build_report

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
    assert "authored_per_member" in report["weekly_trend"]
    series = report["weekly_trend"]["authored_per_member"]["alwu"]
    assert sum(series) == 1


def test_template_references_authored_per_member():
    """The Member Profile renderer must consume the new series."""
    from reviewstats.render import render_html
    minimal = {
        "meta": {"path": "x", "group": "g",
                 "window_start": "2026-05-01", "window_end": "2026-05-15",
                 "generated_at": "2026-05-15T00:00:00Z"},
        "summary": {"total_patches": 0, "group_tagged_patches": 0,
                    "group_tagged_pct": 0, "with_individual_named": 0,
                    "with_individual_pct": 0, "group_only": 0,
                    "group_only_pct": 0, "unique_individuals": 0,
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
    html = render_html(minimal)
    assert "authored_per_member" in html, (
        "Member Profile chart JS should read authored_per_member"
    )
    assert "Patches submitted / week" in html
    assert "Submitted — 4-week avg" in html
