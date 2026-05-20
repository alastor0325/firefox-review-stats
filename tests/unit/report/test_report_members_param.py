"""Tests for the new `members=` parameter on build_report.

Pre-refactor, build_report imported MEMBER_IDS at module load and
used it everywhere — the team was a hidden global. Now the caller
passes a {handle: display_name} dict explicitly so a multi-team
future can run reports for different rosters side by side.

These tests pin the new contract:
* Caller can pass an arbitrary roster and it flows through every
  member-keyed metric.
* Omitting `members` falls back to the playback roster so existing
  callers (and the GH Action) keep working unchanged.
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.members import MEMBERS as DEFAULT_MEMBERS
from reviewstats.parse import Reviewer
from reviewstats.report import build_report


GROUP = "media-playback-reviewers"
WINDOW_START = datetime(2026, 5, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 5, 15, tzinfo=timezone.utc)
GENERATED_AT = datetime(2026, 5, 15, tzinfo=timezone.utc)


def _commit(reviewer_name: str, *, author: str = "X", sha: str = "a" * 12):
    return Commit(
        sha=sha,
        date=datetime(2026, 5, 12, tzinfo=timezone.utc),
        author=author,
        subject="Bug 1 - thing",
        reviewers=[Reviewer(GROUP, True), Reviewer(reviewer_name, False)],
        differential_revision="D" + sha[:5],
    )


def _build(commits, *, members=None):
    return build_report(
        commits,
        group=GROUP,
        path="dom/media",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        generated_at=GENERATED_AT,
        members=members,
    )


def test_custom_roster_drives_within_group_count():
    """Reviewers outside the supplied roster don't appear in the
    Within-group-total table even though they're on the patch."""
    custom = {"alice": "Alice A", "bob": "Bob B"}
    commits = [
        _commit("alice", sha="a" * 12),
        _commit("alice", sha="b" * 12),
        _commit("padenot", sha="c" * 12),  # not in `custom`
    ]
    report = _build(commits, members=custom)
    by_name = {r["name"]: r["count"] for r in report["within_group_total"]}
    assert by_name == {"alice": 2}


def test_custom_roster_appears_in_members_field():
    """`report.members` is the roster the JS dropdown reads — must
    reflect the caller's roster verbatim, not the default one."""
    custom = {"alice": "Alice A"}
    report = _build([], members=custom)
    assert report["members"] == {"alice": "Alice A"}


def test_member_authored_counts_keyed_by_supplied_handles():
    custom = {"alice": "Alice A"}
    commits = [_commit("alice", author="Alice A", sha="a" * 12)]
    report = _build(commits, members=custom)
    assert report["member_authored_counts"] == {"alice": 1}


def test_omitting_members_falls_back_to_default_playback_roster():
    """Existing callers (analyze_phab, third-party tests) don't pass
    `members`. They must see the same report shape as before — the
    8-name playback roster baked in."""
    report = _build([])
    assert report["members"] == DEFAULT_MEMBERS


def test_weekly_trend_all_members_uses_supplied_roster():
    """All-members weekly trend dict is keyed by every roster handle,
    even those with zero activity in the window."""
    custom = {"alice": "Alice A", "bob": "Bob B"}
    report = _build([], members=custom)
    assert set(report["weekly_trend"]["all_members"].keys()) == {"alice", "bob"}
