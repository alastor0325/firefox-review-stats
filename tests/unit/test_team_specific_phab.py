"""Tests for the team-agnostic / team-specific split in analyze_phab.

`parse_html_to_raw` writes a team-agnostic payload to
raw_data/D<n>.json — the same file is reusable for any team that
has the revision in scope.

`compute_team_metrics` runs at aggregation time, deriving the
team-specific fields (queue_added_at, queue_seconds, first_member_*)
from the agnostic events list + the team's group/members.

These tests pin the contract so a future refactor that leaks
playback-specific assumptions back into the raw_data shape fails
loud rather than silently breaking the multi-team setup.
"""

from datetime import datetime, timezone

import analyze_phab


_PLAYBACK_MEMBERS = frozenset({"alwu", "padenot", "kinetik"})
_WEBRTC_MEMBERS = frozenset({"jib", "pehrsons", "mjf"})


def _raw_with_events(events: list[dict], author: str = "outsider") -> dict:
    return {
        "d_number": "D9999",
        "author": author,
        "created_at": "2026-05-01T00:00:00+00:00",
        "events": events,
        "time_to_react_seconds": None,
        "time_to_accept_seconds": None,
    }


def test_compute_team_metrics_queue_anchor_uses_team_group():
    """The 'queue added' anchor is the latest add-reviewer event
    naming the team's group — different teams see different queue
    moments on the same revision."""
    events = [
        {"ts": "2026-05-01T00:00:00+00:00", "actor": "outsider", "action": "create"},
        {"ts": "2026-05-02T00:00:00+00:00", "actor": "outsider",
         "action": "add-reviewer", "target": "media-playback-reviewers"},
        {"ts": "2026-05-03T00:00:00+00:00", "actor": "outsider",
         "action": "add-reviewer", "target": "webrtc-reviewers"},
        {"ts": "2026-05-04T00:00:00+00:00", "actor": "padenot",
         "action": "comment"},
        {"ts": "2026-05-05T00:00:00+00:00", "actor": "jib",
         "action": "comment"},
    ]
    raw = _raw_with_events(events)

    pb = analyze_phab.compute_team_metrics(
        raw, group="media-playback-reviewers", members=_PLAYBACK_MEMBERS,
    )
    wr = analyze_phab.compute_team_metrics(
        raw, group="webrtc-reviewers", members=_WEBRTC_MEMBERS,
    )

    # Playback sees the May 2 add-reviewer event; webrtc sees May 3.
    assert pb["queue_added_at"].startswith("2026-05-02")
    assert wr["queue_added_at"].startswith("2026-05-03")
    # And each picks its own member's reaction.
    assert pb["first_member_review"]["actor"] == "padenot"
    assert wr["first_member_review"]["actor"] == "jib"


def test_compute_team_metrics_none_when_no_member_reacted():
    """A revision with no roster reactions has None first_member_* —
    aggregation downstream skips these."""
    events = [
        {"ts": "2026-05-01T00:00:00+00:00", "actor": "outsider", "action": "create"},
        {"ts": "2026-05-02T00:00:00+00:00", "actor": "stranger", "action": "comment"},
    ]
    raw = _raw_with_events(events)
    result = analyze_phab.compute_team_metrics(
        raw, group="media-playback-reviewers", members=_PLAYBACK_MEMBERS,
    )
    assert result["first_member_review"] is None
    assert result["first_member_accept"] is None
    assert result["queue_seconds"] is None


def test_parse_html_to_raw_does_not_carry_team_specific_fields():
    """raw_data shape must be team-agnostic so it can be shared
    across teams. Catching a team-specific field here means a future
    refactor accidentally re-coupled the persistence layer to one
    team."""
    # We can't easily construct realistic HTML here; instead we
    # verify the function's documented field set is what gets
    # returned for a minimal fixture.
    raw = analyze_phab.parse_html_to_raw("<html></html>", "D9999")
    agnostic_fields = {
        "d_number", "author", "created_at", "events",
        "time_to_react_seconds", "time_to_accept_seconds",
    }
    team_specific_fields = {
        "queue_added_at", "queue_seconds", "queue_to_accept_seconds",
        "first_member_accept", "first_member_review",
    }
    actual = set(raw.keys())
    assert actual == agnostic_fields, (
        f"raw_data shape drifted. Expected {agnostic_fields}, "
        f"got {actual}."
    )
    assert team_specific_fields.isdisjoint(actual), (
        "Team-specific fields leaked into the persisted raw_data shape."
    )


def test_process_html_legacy_combiner_still_returns_full_shape():
    """The existing main() path in analyze_phab still uses
    _process_html for backwards compatibility — it must return the
    union of agnostic + team-specific fields with no change."""
    payload = analyze_phab._process_html(
        "<html></html>",
        "D9999",
        group="media-playback-reviewers",
        members=_PLAYBACK_MEMBERS,
    )
    for key in [
        "d_number", "author", "created_at", "events",
        "queue_added_at", "queue_seconds", "queue_to_accept_seconds",
        "time_to_react_seconds", "time_to_accept_seconds",
        "first_member_accept", "first_member_review",
    ]:
        assert key in payload, f"_process_html dropped {key!r}"
