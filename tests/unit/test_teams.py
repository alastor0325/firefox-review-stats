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

from reviewstats.teams import PLAYBACK_TEAM, TEAMS, Team, get_team


def test_team_is_frozen_dataclass():
    """Frozen so analyzer code can't mutate the registry by accident
    (e.g. patching excludes in one code path leaking to others)."""
    with pytest.raises(Exception):
        PLAYBACK_TEAM.path = "somewhere/else"  # type: ignore[misc]


def test_playback_team_matches_existing_constants():
    """Pre-refactor analyze_git.py / analyze_phab.py had these exact
    values. Pinning them here means swapping the analyzers to read
    from PLAYBACK_TEAM in Task C can't silently change behavior."""
    assert PLAYBACK_TEAM.slug == "playback"
    assert PLAYBACK_TEAM.group == "media-playback-reviewers"
    assert PLAYBACK_TEAM.path == "dom/media"
    assert PLAYBACK_TEAM.excludes == (
        "dom/media/webrtc",
        "dom/media/systemservices",
    )


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


def test_members_dict_is_a_plain_dict_for_easy_consumption():
    """Some callers iterate `.items()`, others do `name in members`.
    A bare dict satisfies both — locking the type prevents a future
    "I'll use a CustomMembers class" refactor that breaks them."""
    assert isinstance(PLAYBACK_TEAM.members, dict)
