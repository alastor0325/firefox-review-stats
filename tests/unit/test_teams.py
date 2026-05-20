"""Tests for the team config registry.

These pin two contracts:

1. The shape of the `Team` dataclass — slug, display_name, group,
   path, excludes (tuple), members (dict).
2. The PLAYBACK_TEAM entry mirrors today's hardcoded values so the
   refactor from inline constants to the registry doesn't change
   any output.

If a future commit adds a second team, that team gets its own
test file — this one only certifies the playback team didn't drift.
"""

import pytest

from reviewstats.teams import (
    PLAYBACK_TEAM,
    TEAMS,
    Team,
    WEBRTC_TEAM,
    get_team,
)


def test_team_is_frozen_dataclass():
    """Frozen so analyzer code can't mutate the registry by accident
    (e.g. patching excludes in one code path leaking to others)."""
    with pytest.raises(Exception):
        PLAYBACK_TEAM.paths = ("somewhere/else",)  # type: ignore[misc]


def test_playback_team_matches_existing_constants():
    """Pre-refactor analyze_git.py / analyze_phab.py had these exact
    values. Pinning them here means swapping the analyzers to read
    from PLAYBACK_TEAM in Task C can't silently change behavior."""
    assert PLAYBACK_TEAM.slug == "playback"
    assert PLAYBACK_TEAM.group == "media-playback-reviewers"
    assert PLAYBACK_TEAM.paths == ("dom/media",)
    assert PLAYBACK_TEAM.excludes == (
        "dom/media/webrtc",
        "dom/media/systemservices",
    )


def test_team_paths_is_a_tuple_not_a_string():
    """Catch the common mistake of writing `paths="dom/media"` —
    Python would iterate it char-by-char and the analyzer would
    fetch `d`, `o`, `m`, … as separate path filters."""
    assert isinstance(PLAYBACK_TEAM.paths, tuple)


def test_playback_team_member_roster_matches_existing_members():
    """The 8 listed members must match members.py exactly so the
    Team Profile dropdown and the 'Listed members reviewing' tile
    don't change."""
    expected = {
        "alwu": "Alastor Wu",
        "chunmin": "Chun-Min Chang",
        "jolin": "John Lin",
        "padenot": "Paul Adenot",
        "azebrowski": "azebrowski",
        "kinetik": "Matthew Gregan",
        "karlt": "Karl Tomlinson",
        "aosmond": "Andrew Osmond",
    }
    assert PLAYBACK_TEAM.members == expected


def test_registry_indexes_team_by_slug():
    assert TEAMS["playback"] is PLAYBACK_TEAM


def test_get_team_returns_registered_team():
    assert get_team("playback") is PLAYBACK_TEAM


def test_get_team_raises_keyerror_for_unknown_slug():
    """A typo at the CLI ('--team playbck') should fail loud rather
    than silently fall through to an unintended team."""
    with pytest.raises(KeyError, match="Unknown team slug"):
        get_team("nonexistent")


def test_webrtc_team_matches_user_spec():
    """The WebRTC team owns dom/media/webrtc + dom/media/systemservices.
    third_party/libwebrtc is intentionally out of scope (bulk-import
    noise). Pinned values per the design discussion."""
    assert WEBRTC_TEAM.slug == "webrtc"
    assert WEBRTC_TEAM.group == "webrtc-reviewers"
    assert WEBRTC_TEAM.paths == (
        "dom/media/webrtc",
        "dom/media/systemservices",
    )
    assert WEBRTC_TEAM.excludes == ()


def test_webrtc_team_roster_matches_phab_project_155():
    """Roster sourced from the Phab project-members page (project 155).
    6 names; pinning prevents accidental drift on edits."""
    assert WEBRTC_TEAM.members == {
        "ng": "Nico Grunbaum",
        "bwc": "Byron Campen",
        "mjf": "Michael Froman",
        "pehrsons": "Andreas Pehrson",
        "jib": "Jan-Ivar Bruaroey",
        "dbaker": "Daniel Baker",
    }


def test_webrtc_is_registered():
    assert TEAMS["webrtc"] is WEBRTC_TEAM
    assert get_team("webrtc") is WEBRTC_TEAM


def test_playback_and_webrtc_paths_are_disjoint():
    """A commit touching only dom/media/webrtc must not appear in the
    playback report — playback's excludes drop it. Conversely, a
    commit touching only dom/media (e.g. mediacapabilities) doesn't
    land in the webrtc report because webrtc's paths don't include
    that root. Pin both ends so a future config edit can't quietly
    overlap the teams."""
    # Playback owns dom/media but excludes the webrtc-owned subtrees.
    assert PLAYBACK_TEAM.paths == ("dom/media",)
    for ex in WEBRTC_TEAM.paths:
        assert ex in PLAYBACK_TEAM.excludes, (
            f"Playback should exclude every WebRTC root ({ex!r}) "
            "to avoid double-counting."
        )
    # WebRTC's paths don't include the bare dom/media root.
    assert "dom/media" not in WEBRTC_TEAM.paths


def test_members_dict_is_a_plain_dict_for_easy_consumption():
    """Some callers iterate `.items()`, others do `name in members`.
    A bare dict satisfies both — locking the type prevents a future
    "I'll use a CustomMembers class" refactor that breaks them."""
    assert isinstance(PLAYBACK_TEAM.members, dict)
