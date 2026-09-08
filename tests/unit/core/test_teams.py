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

from itertools import permutations, product

import pytest

from reviewstats.parse import _GROUP_ALIASES
from reviewstats.teams import (
    DOM_CORE_TEAM,
    GFX_TEAM,
    LAYOUT_TEAM,
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


def test_layout_team_matches_user_spec():
    """Pins the scope decided in teams.py — all of `layout/`, style
    included, servo/ out. See the LAYOUT_TEAM comment for why."""
    assert LAYOUT_TEAM.slug == "layout"
    assert LAYOUT_TEAM.group == "layout-reviewers"
    assert LAYOUT_TEAM.paths == ("layout",)
    assert LAYOUT_TEAM.excludes == ()


def test_layout_team_roster_matches_phab_project_126():
    """11 members sourced from Phab project 126 via Conduit
    project.search + user.search. Pinned to catch silent drift."""
    assert LAYOUT_TEAM.members == {
        "emilio": "Emilio Cobos Álvarez",
        "dholbert": "Daniel Holbert",
        "dshin": "David Shin",
        "TYLin": "Ting-Yu Lin",
        "jfkthame": "Jonathan Kew",
        "boris": "Boris Chiou",
        "hiro": "Hiroyuki Ikezoe",
        "jwatt": "Jonathan Watt",
        "tnikkel": "Timothy Nikkel",
        "AlaskanEmily": "Emily Anne McDonough",
        "tlouw": "Tiaan Louw",
    }


def test_layout_is_registered():
    assert TEAMS["layout"] is LAYOUT_TEAM
    assert get_team("layout") is LAYOUT_TEAM


def test_dom_core_team_matches_user_spec():
    """Pins the allow-list scope decided in teams.py. `dom` itself
    must never appear here — see the DOM_CORE_TEAM comment for the
    measured ownership of every subtree left out."""
    assert DOM_CORE_TEAM.slug == "dom-core"
    assert DOM_CORE_TEAM.group == "dom-core-reviewers"
    assert DOM_CORE_TEAM.paths == (
        "dom/base",
        "dom/html",
        "dom/events",
        "dom/bindings",
        "dom/webidl",
        "dom/ipc",
        "docshell",
        "parser",
    )
    assert DOM_CORE_TEAM.excludes == ()


def test_dom_core_team_roster_matches_phab_project_178():
    """15 members sourced from Phab project 178 via Conduit."""
    assert DOM_CORE_TEAM.members == {
        "smaug": "Olli Pettay",
        "peterv": "Peter Van der Beken",
        "edgar": "Edgar Chen",
        "farre": "Andreas Farre",
        "masayuki": "Masayuki Nakano",
        "hsivonen": "Henri Sivonen",
        "mccr8": "Andrew McCreight",
        "sefeng": "Sean Feng",
        "hsinyi": "Hsin-Yi Tsai",
        "jjaschke": "Jan Jaeschke [:jjaschke]",
        "avandolder": "Adam Vandolder",
        "keithamus": "Keith Cirkel",
        "zcorpan": "Simon Pieters",
        "sfarre": "Simon Farre",
        "vhilla": "Vincent Hilla",
    }


def test_dom_core_approved_reviewers_are_trusted_non_members():
    """The highest-volume non-roster reviewers inside dom-core's
    paths. Without them the dashboard reads ~42% 'landed without
    team review' purely because adjacent-team peers do the review."""
    assert DOM_CORE_TEAM.approved_reviewers == frozenset(
        {"emilio", "nika", "asuth", "saschanaz", "tschuster"}
    )
    assert DOM_CORE_TEAM.approved_reviewers.isdisjoint(DOM_CORE_TEAM.members)


def test_dom_core_is_registered():
    assert TEAMS["dom-core"] is DOM_CORE_TEAM
    assert get_team("dom-core") is DOM_CORE_TEAM


def test_no_team_path_is_nested_under_another_teams_path():
    """Generalises the old pairwise playback/webrtc/gfx checks to every
    registered team. Nesting means one commit is counted in two teams'
    git-side reports unless the outer team excludes the inner one —
    which only playback does, for the two WebRTC roots."""
    for a, b in permutations(TEAMS.values(), 2):
        for ap, bp in product(a.paths, b.paths):
            assert ap != bp, f"{a.slug} and {b.slug} share root {ap!r}"
            if bp.startswith(ap + "/"):
                assert bp in a.excludes, (
                    f"{b.slug} path {bp!r} is nested under {a.slug} path "
                    f"{ap!r} without an exclude — double-counted."
                )


def test_group_aliases_resolve_to_a_real_group():
    """`_GROUP_ALIASES` in parse.py hardcodes the canonical group name
    each hashtag maps to, duplicating `Team.group` with nothing binding
    the two. Rename a team's group and the alias silently goes dead —
    both sides stay green because each is pinned separately. This is
    that binding."""
    # Groups with no dashboard here: real Phabricator review groups we
    # must still parse as groups (else they become phantom individuals
    # in every team's non-member reviewer list), but no team owns them.
    teamless = {"webidl"}
    registered = {t.group for t in TEAMS.values()}
    for alias, canonical in _GROUP_ALIASES.items():
        assert canonical in registered or canonical in teamless, (
            f"alias {alias!r} maps to {canonical!r}, which is neither a "
            f"registered Team.group nor a known teamless group."
        )
