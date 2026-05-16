#!/usr/bin/env python3
"""Generate a per-revision audit table from raw_data/D*.json.

Output: raw_data/verification.md — one row per revision with the three
timestamps the user wants to audit manually:

  * Created at        — when the revision was first submitted
  * Reacted by member — first comment / accept / request-changes / reject
                        by a media-playback-reviewers member
  * Accepted by member — first accept by a member (subset of reacted)

Use this to spot-check the computed metrics against the live Phab page.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.members import MEMBER_IDS


RAW = Path(__file__).resolve().parent / "raw_data"
OUT = RAW / "verification.md"

_REVIEW_ACTIONS = frozenset({"accept", "request-changes", "reject", "comment"})
_BOTS = frozenset({"phab-bot", "Lando", "lando-bot", "Herald"})


def _fmt(ts_iso: str | None) -> str:
    if not ts_iso:
        return "—"
    return ts_iso.replace("T", " ").replace("+00:00", " UTC")


def main() -> None:
    files = sorted(
        RAW.glob("D*.json"),
        key=lambda p: int(p.stem[1:]),
    )
    rows: list[dict] = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        d_number = d["d_number"]
        author = d.get("author")
        created_at = d.get("created_at")
        events = d.get("events", [])

        first_react = None
        first_accept = None
        for e in events:
            actor = e.get("actor")
            action = e.get("action")
            if actor in _BOTS or actor == author or actor not in MEMBER_IDS:
                continue
            if action in _REVIEW_ACTIONS and first_react is None:
                first_react = e
            if action == "accept" and first_accept is None:
                first_accept = e
            if first_react and first_accept:
                break

        rows.append({
            "d_number": d_number,
            "author": author or "—",
            "created_at": created_at,
            "queue_added_at": d.get("queue_added_at"),
            "queue_seconds": d.get("queue_seconds"),
            "react_actor": first_react["actor"] if first_react else None,
            "react_action": first_react["action"] if first_react else None,
            "react_at": first_react["ts"] if first_react else None,
            "accept_actor": first_accept["actor"] if first_accept else None,
            "accept_at": first_accept["ts"] if first_accept else None,
        })

    # Summary
    n_total = len(rows)
    n_with_create = sum(1 for r in rows if r["created_at"])
    n_with_react = sum(1 for r in rows if r["react_at"])
    n_with_accept = sum(1 for r in rows if r["accept_at"])

    lines: list[str] = []
    lines.append("# Per-revision audit table")
    lines.append("")
    lines.append(
        "Use this table to manually spot-check the wait-time numbers against "
        "the live Phab revision page (`https://phabricator.services.mozilla.com/D<n>`)."
    )
    lines.append("")
    lines.append(f"- Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Revisions in raw_data/: **{n_total}**")
    lines.append(f"- Have a `created` timestamp: **{n_with_create}**")
    lines.append(
        f"- Have a first reaction (comment/accept/request-changes/reject) "
        f"by a listed member: **{n_with_react}**"
    )
    lines.append(
        f"- Have an explicit `accept` by a listed member: **{n_with_accept}**"
    )
    n_with_queue = sum(1 for r in rows if r.get("queue_seconds") is not None)
    lines.append(
        f"- Have a computable **queue wait** (group added then member reacted): "
        f"**{n_with_queue}**"
    )
    lines.append("")
    lines.append(
        "Member set (from `reviewstats/members.py`): "
        + ", ".join(sorted(MEMBER_IDS))
    )
    lines.append("")
    lines.append(
        "Bots filtered out: `phab-bot`, `Lando`, `lando-bot`, `Herald`. "
        "The author of the revision is also skipped (self-reaction doesn't "
        "count)."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "| # | Revision | Author | Created | Group added to queue "
        "| First member reaction | First member accept | Queue wait |"
    )
    lines.append("|--:|---|---|---|---|---|---|--:|")

    for i, r in enumerate(rows, 1):
        react = "—"
        if r["react_at"]:
            react = f"{_fmt(r['react_at'])} by **{r['react_actor']}** ({r['react_action']})"
        accept = "—"
        if r["accept_at"]:
            accept = f"{_fmt(r['accept_at'])} by **{r['accept_actor']}**"
        queue_wait = "—"
        if r.get("queue_seconds") is not None:
            hours = r["queue_seconds"] / 3600
            queue_wait = (
                f"{hours/24:.1f} d" if hours >= 24 else f"{hours:.1f} h"
            )
        lines.append(
            f"| {i} "
            f"| [{r['d_number']}](https://phabricator.services.mozilla.com/{r['d_number']}) "
            f"| {r['author']} "
            f"| {_fmt(r['created_at'])} "
            f"| {_fmt(r.get('queue_added_at'))} "
            f"| {react} "
            f"| {accept} "
            f"| {queue_wait} |"
        )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Wrote {OUT}  ({n_total} revisions; "
        f"{n_with_react} with a member reaction, "
        f"{n_with_accept} with a member accept)"
    )


if __name__ == "__main__":
    main()
