"""Team configuration registry.

Each `Team` bundles the four knobs every report needs:

* `group`     — the Phabricator review group tag we scan for
  (e.g. `media-playback-reviewers`).
* `path`      — the source directory the team owns (e.g. `dom/media`).
* `excludes`  — sub-paths under `path` to drop from the scan
  (sibling-team territory that happens to live in the same tree).
* `members`   — `{handle: display_name}` for the team's listed
  reviewers (sourced from the Phab project membership page).

The slug is used as a CLI argument value and, in a future
multi-team layout, as an output subdirectory name.

Today the dashboard only ships data for the playback team — but
the analyzers, member lookup, and renderer all consume this
registry so adding `webrtc-reviewers` or `gfx-reviewers` later is
config-only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Team:
    slug: str
    display_name: str
    group: str
    path: str
    excludes: tuple[str, ...]
    members: dict[str, str]


PLAYBACK_TEAM = Team(
    slug="playback",
    display_name="media-playback-reviewers",
    group="media-playback-reviewers",
    path="dom/media",
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


TEAMS: dict[str, Team] = {
    PLAYBACK_TEAM.slug: PLAYBACK_TEAM,
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
