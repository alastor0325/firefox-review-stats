"""Team configuration registry.

Each `Team` bundles the four knobs every report needs:

* `group`     — the Phabricator review group tag we scan for
  (e.g. `media-playback-reviewers`).
* `paths`     — the source directories the team owns. A tuple
  because some teams (e.g. WebRTC) span multiple top-level trees.
* `excludes`  — sub-paths under any of `paths` to drop from the
  scan (sibling-team territory that happens to live alongside).
* `members`   — `{handle: display_name}` for the team's listed
  reviewers (sourced from the Phab project membership page).
* `approved_reviewers` — extra handles that are NOT on the roster but
  whose review still counts as valid team oversight (so patches they
  review don't count as "landed without team review"). Unlike
  `members`, these never appear in any load-distribution view — they
  are not treated as team members, only as trusted approvers.

The slug is used as the output subdirectory name (each team gets
its own /<slug>/index.html under the site root).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Team:
    slug: str
    display_name: str
    group: str
    paths: tuple[str, ...]
    excludes: tuple[str, ...]
    members: dict[str, str]
    approved_reviewers: frozenset[str] = field(default_factory=frozenset)


PLAYBACK_TEAM = Team(
    slug="playback",
    display_name="media-playback-reviewers",
    group="media-playback-reviewers",
    paths=("dom/media",),
    # dom/media/webrtc and dom/media/systemservices live in dom/media/
    # but are owned by the WebRTC team — review there goes to
    # pehrsons/jib, not the playback roster.
    excludes=("dom/media/webrtc", "dom/media/systemservices"),
    members={
        "alwu": "Alastor Wu",
        "chunmin": "Chun-Min Chang",
        "jolin": "John Lin",
        "padenot": "Paul Adenot",
        "azebrowski": "azebrowski",
        "kinetik": "Matthew Gregan",
        "karlt": "Karl Tomlinson",
        "aosmond": "Andrew Osmond",
    },
    # Trusted reviewers who aren't on the media-playback-reviewers Phab
    # roster but whose review still counts as valid team oversight.
    approved_reviewers=frozenset({"pehrsons", "stransky"}),
)


WEBRTC_TEAM = Team(
    slug="webrtc",
    display_name="webrtc-reviewers",
    group="webrtc-reviewers",
    # WebRTC code lives in two trees under dom/media. third_party/
    # libwebrtc is a synced upstream and intentionally out of scope
    # — its commits are mostly bulk-import noise.
    paths=("dom/media/webrtc", "dom/media/systemservices"),
    excludes=(),
    # Source: https://phabricator.services.mozilla.com/project/members/155/
    members={
        "ng": "Nico Grunbaum",
        "bwc": "Byron Campen",
        "mjf": "Michael Froman",
        "pehrsons": "Andreas Pehrson",
        "jib": "Jan-Ivar Bruaroey",
        "dbaker": "Daniel Baker",
    },
)


GFX_TEAM = Team(
    slug="gfx",
    display_name="gfx-reviewers",
    group="gfx-reviewers",
    # Scope matches what the gfx team actually reviews day-to-day:
    # the gfx tree plus image (decoders), dom/canvas, and dom/webgpu.
    # Restricting to gfx/ alone would miss image (aosmond, tnikkel),
    # canvas, and WebGPU (ErichDonGubler, teoxoy) work that this
    # roster regularly approves.
    paths=("gfx", "image", "dom/canvas", "dom/webgpu"),
    # Vendored upstreams: bulk auto-sync, not really reviewed in the
    # usual sense — same reasoning as `third_party/libwebrtc` for
    # the WebRTC team. qcms intentionally kept in scope (maintained
    # in-tree, not bulk-synced).
    excludes=(
        "gfx/angle",
        "gfx/cairo",
        "gfx/skia",
        "gfx/harfbuzz",
        "gfx/ots",
        "gfx/sfntly",
        "gfx/graphite2",
    ),
    # Source: Phab project members page (13 active members; 14th is
    # inactive and intentionally not listed). aosmond also appears
    # in PLAYBACK_TEAM — the two rosters are independent dicts; each
    # dashboard counts his reviews only within its own paths.
    members={
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
    },
)


TEAMS: dict[str, Team] = {
    PLAYBACK_TEAM.slug: PLAYBACK_TEAM,
    WEBRTC_TEAM.slug: WEBRTC_TEAM,
    GFX_TEAM.slug: GFX_TEAM,
}


def get_team(slug: str) -> Team:
    """Look up a team by slug. Raises KeyError with a helpful message
    if the slug isn't registered — surfaces typos in CLI args early."""
    try:
        return TEAMS[slug]
    except KeyError as e:
        known = ", ".join(sorted(TEAMS))
        raise KeyError(
            f"Unknown team slug {slug!r}. Registered teams: {known}."
        ) from e
