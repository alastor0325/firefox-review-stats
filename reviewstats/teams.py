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
* `has_roadmap` — whether this team maintains a curated roadmap, which
  gates the Media Health view. Unlike the other four views, that one is
  not a lens on review process (which is generic across teams) but on
  the product itself, so it legitimately exists for one team only.

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
    has_roadmap: bool = False


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
    # The media roadmap is curated in the investigation repo; this is the
    # only team with one, so the Media Health view is playback-only.
    has_roadmap=True,
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


LAYOUT_TEAM = Team(
    slug="layout",
    display_name="layout-reviewers",
    group="layout-reviewers",
    # All of layout/, including layout/style. The style system has its
    # own group (firefox-style-system-reviewers is the more common tag
    # there, 251 uses vs 69 over 6 months), but this roster reviews
    # style work as individuals — keeping it in scope measures 74%
    # team review against 68% without it. servo/ (Stylo) is the style
    # system's own tree and stays out of scope entirely.
    paths=("layout",),
    excludes=(),
    # Source: https://phabricator.services.mozilla.com/project/members/126/
    # tnikkel also appears in GFX_TEAM — same independent-roster
    # arrangement as aosmond across playback/gfx.
    members={
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
    },
)


DOM_CORE_TEAM = Team(
    slug="dom-core",
    display_name="dom-core-reviewers",
    group="dom-core-reviewers",
    # An ALLOW-LIST, not `dom/` minus excludes. dom/ is a federation of
    # review groups and dom-core is not the dominant reviewer in most
    # of it: scoping to all of dom/ measures 27% team review, so 73% of
    # patches would land in the "no team review" bucket and the
    # headline risk metric would be noise. These 8 paths measure 58%.
    #
    # Measured owners of the subtrees deliberately left out:
    #   dom/media                 media-playback-reviewers / webrtc
    #   dom/canvas, dom/webgpu    gfx-reviewers / webgpu-reviewers
    #   dom/quota, dom/indexedDB,
    #     dom/localstorage        dom-storage-reviewers
    #   dom/workers,
    #     dom/serviceworkers,
    #     dom/cache               dom-worker-reviewers
    #   dom/svg                   firefox-svg-reviewers
    #   dom/animation             layout-scroll-driven-animation-reviewers
    #   dom/webtransport,
    #     dom/network, dom/fetch  necko-reviewers
    #
    # An allow-list also fails safe. A new dom/ subdirectory owned by
    # another group stays out of scope until someone opts it in, where
    # an exclude-list would silently pull it in and need chasing.
    paths=(
        "dom/base",
        "dom/html",
        "dom/events",
        "dom/bindings",
        "dom/webidl",
        "dom/ipc",
        "docshell",
        "parser",
    ),
    excludes=(),
    # Source: https://phabricator.services.mozilla.com/project/members/178/
    members={
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
    },
    # The highest-volume non-roster reviewers inside these paths.
    # Adjacent-team peers do a lot of the reviewing here; without them
    # "landed without team review" reads ~42% for reasons that have
    # nothing to do with queue health.
    approved_reviewers=frozenset(
        {"emilio", "nika", "asuth", "saschanaz", "tschuster"}
    ),
)


TEAMS: dict[str, Team] = {
    PLAYBACK_TEAM.slug: PLAYBACK_TEAM,
    WEBRTC_TEAM.slug: WEBRTC_TEAM,
    GFX_TEAM.slug: GFX_TEAM,
    LAYOUT_TEAM.slug: LAYOUT_TEAM,
    DOM_CORE_TEAM.slug: DOM_CORE_TEAM,
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
