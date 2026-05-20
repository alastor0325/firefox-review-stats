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

The slug is used as the output subdirectory name (each team gets
its own /<slug>/index.html under the site root).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Team:
    slug: str
    display_name: str
    group: str
    paths: tuple[str, ...]
    excludes: tuple[str, ...]
    members: dict[str, str]


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


TEAMS: dict[str, Team] = {
    PLAYBACK_TEAM.slug: PLAYBACK_TEAM,
    WEBRTC_TEAM.slug: WEBRTC_TEAM,
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
