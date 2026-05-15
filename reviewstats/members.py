"""Hardcoded membership of the media-playback-reviewers Phabricator project.

Source: https://phabricator.services.mozilla.com/project/members/<project>/
Update by hand when membership changes.
"""

MEMBERS: dict[str, str] = {
    "alwu": "Alastor Wu",
    "chunmin": "C.M.Chang",
    "jolin": "John Lin",
    "padenot": "Paul Adenot",
    "stransky": "Martin Stránský",
    "azebrowski": "azebrowski",
    "kinetik": "Matthew Gregan",
    "karlt": "Karl Tomlinson",
    "aosmond": "Andrew Osmond",
}

MEMBER_IDS: frozenset[str] = frozenset(MEMBERS.keys())
