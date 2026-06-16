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
    GFX_TEAM,
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


def test_playback_approved_reviewers_are_trusted_non_members():
    """pehrsons and stransky review playback patches but aren't on the
    roster — their review must count as oversight without making them
    team members (so they stay out of every load-distribution view)."""
    assert PLAYBACK_TEAM.approved_reviewers == frozenset(
        {"pehrsons", "stransky"}
    )
    # Trusted approvers, not roster members.
    assert PLAYBACK_TEAM.approved_reviewers.isdisjoint(PLAYBACK_TEAM.members)


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


def test_gfx_team_matches_user_spec():
    """Scope from the design discussion: gfx + image + dom/canvas +
    dom/webgpu (Option A — what gfx-reviewers actually review day to
    day). Vendored upstreams excluded; gfx/qcms kept in scope."""
    assert GFX_TEAM.slug == "gfx"
    assert GFX_TEAM.group == "gfx-reviewers"
    assert GFX_TEAM.paths == ("gfx", "image", "dom/canvas", "dom/webgpu")
    assert GFX_TEAM.excludes == (
        "gfx/angle",
        "gfx/cairo",
        "gfx/skia",
        "gfx/harfbuzz",
        "gfx/ots",
        "gfx/sfntly",
        "gfx/graphite2",
    )
    # qcms intentionally NOT excluded — maintained in-tree, not a
    # bulk-import sync.
    assert "gfx/qcms" not in GFX_TEAM.excludes


def test_gfx_team_roster_matches_phab_project_screenshot():
    """13 active members from the Phab project members page. The
    14th member is inactive and intentionally not listed."""
    assert GFX_TEAM.members == {
        "jrmuizel": "Jeff Muizelaar",
        "nical": "Nicolas Silva",
        "gw": "Glenn Watson",
        "jnicol": "Jamie Nicol",
        "aosmond": "Andrew Osmond",
        "jimb": "Jim Blandy",
        "bradwerth": "Brad Werth",
        "lsalzman": "Lee Salzman",
        "sotaro": "Sotaro Ikeda",
        "ahale": "Ashley Hale",
        "ErichDonGubler": "Erich Gubler",
        "teoxoy": "Teodor Tanasoaia",
        "tnikkel": "Timothy Nikkel",
    }
    assert len(GFX_TEAM.members) == 13


def test_gfx_is_registered():
    assert TEAMS["gfx"] is GFX_TEAM
    assert get_team("gfx") is GFX_TEAM


def test_gfx_paths_do_not_overlap_with_playback_or_webrtc():
    """gfx's roots are entirely disjoint from playback's `dom/media`
    and webrtc's `dom/media/webrtc` + `dom/media/systemservices`.
    A commit can't end up double-counted in two teams' git-side
    reports just because the path scopes overlap."""
    other_paths = set(PLAYBACK_TEAM.paths) | set(WEBRTC_TEAM.paths)
    for gp in GFX_TEAM.paths:
        for op in other_paths:
            assert not gp.startswith(op + "/"), (
                f"gfx path {gp!r} is nested under {op!r} (other team)."
            )
            assert not op.startswith(gp + "/"), (
                f"Other team path {op!r} is nested under gfx {gp!r}."
            )
            assert gp != op, (
                f"gfx and another team share root {gp!r}."
            )


def test_aosmond_listed_in_both_playback_and_gfx():
    """Documented overlap: aosmond reviews image work in both trees.
    Pin it explicitly so a future edit that drops him from one
    roster does so deliberately, not accidentally."""
    assert "aosmond" in PLAYBACK_TEAM.members
    assert "aosmond" in GFX_TEAM.members


def test_members_dict_is_a_plain_dict_for_easy_consumption():
    """Some callers iterate `.items()`, others do `name in members`.
    A bare dict satisfies both — locking the type prevents a future
    "I'll use a CustomMembers class" refactor that breaks them."""
    assert isinstance(PLAYBACK_TEAM.members, dict)
