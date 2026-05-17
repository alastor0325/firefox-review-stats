"""Build the per-revision audit list for the Wait Queue view.

Each row = one Phab revision. Sorted longest-wait-first so the top of
the table is where investigation should start.
"""

from typing import Mapping

from reviewstats.git_log import Commit


_PHAB_BASE = "https://phabricator.services.mozilla.com"
_REVIEW_ACTIONS = frozenset({"accept", "request-changes", "reject", "comment"})
_BOTS = frozenset({"phab-bot", "Lando", "lando-bot", "Herald", "Harbormaster"})


def _seconds_to_days(s: int | None) -> float | None:
    return None if s is None else s / 86400.0


def _first_actor(
    events: list[dict],
    *,
    author: str | None,
    action_filter: frozenset[str] | str,
) -> str | None:
    """First non-author, non-bot actor whose event action matches.

    Keeps the actor in lockstep with the timing fields in the raw
    entry (which were computed with the same filter logic), so the
    table never shows a wait time without an attributable actor.
    """
    targets = (
        {action_filter} if isinstance(action_filter, str) else action_filter
    )
    for e in events:
        if e.get("action") not in targets:
            continue
        actor = e.get("actor")
        if actor == author or actor in _BOTS or actor is None:
            continue
        return actor
    return None


def build_patch_list(
    raw_entries: Mapping[str, dict],
    commits_by_d: Mapping[str, Commit],
    *,
    members: frozenset[str] | None = None,
) -> list[dict]:
    """Per-revision rows sorted by `time_to_accept_days` desc.

    Revisions without a captured accept go below the accepted ones,
    sorted internally by `time_to_react_days` desc so the slowest
    open patches surface next.

    `members` (optional): if provided, only revisions whose `author`
    (the Phab handle) is in the set are included. Used to scope the
    Wait Queue / team-level wait analysis to member-authored patches.
    """
    rows: list[dict] = []
    for d, raw in raw_entries.items():
        commit = commits_by_d.get(d)
        if commit is None:
            continue
        if members is not None and raw.get("author") not in members:
            continue
        events = raw.get("events", [])
        author = raw.get("author")
        # Resolve actors from the events array directly so they match
        # the `time_to_*` fields (which were computed with the same
        # filter — any non-author, non-bot reactor).
        accept_actor = _first_actor(events, author=author, action_filter="accept")
        react_event = next(
            (e for e in events
             if e.get("action") in _REVIEW_ACTIONS
             and e.get("actor") != author
             and e.get("actor") not in _BOTS
             and e.get("actor") is not None),
            None,
        )
        rows.append({
            "d_number": d,
            "url": f"{_PHAB_BASE}/{d}",
            "title": commit.subject,
            "author": author,
            "accept_actor": accept_actor,
            "react_actor": react_event.get("actor") if react_event else None,
            "react_action": react_event.get("action") if react_event else None,
            "time_to_react_days": _seconds_to_days(
                raw.get("time_to_react_seconds")
            ),
            "time_to_accept_days": _seconds_to_days(
                raw.get("time_to_accept_seconds")
            ),
        })

    def _key(r: dict) -> tuple[int, float, float]:
        # Accepted rows (bucket 0) sort before un-accepted (bucket 1).
        # Within each bucket, larger waits come first.
        accepted = r["time_to_accept_days"] is not None
        return (
            0 if accepted else 1,
            -(r["time_to_accept_days"] if accepted
              else r["time_to_react_days"] or 0.0),
            -(r["time_to_react_days"] or 0.0),
        )

    rows.sort(key=_key)
    return rows
