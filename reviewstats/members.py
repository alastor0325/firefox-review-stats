"""Listed members of the media-playback-reviewers Phabricator project.

The data lives in `reviewstats.teams.PLAYBACK_TEAM.members` — this
module is a thin compatibility shim so existing imports keep working
while later commits migrate callers to read the team config directly.

Update the roster by editing PLAYBACK_TEAM in `teams.py`. Source of
truth: https://phabricator.services.mozilla.com/project/members/<project>/
"""

from reviewstats.teams import PLAYBACK_TEAM


MEMBERS: dict[str, str] = PLAYBACK_TEAM.members
MEMBER_IDS: frozenset[str] = frozenset(MEMBERS.keys())
