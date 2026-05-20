#!/usr/bin/env python3
"""Fetch + parse Phab revision timelines for every in-scope commit.

Per-revision raw event data is committed under `raw_data/D<N>.json` so it
stays around for future analyses (the Conduit API rate-limits make
re-fetching painful, and the timeline data is already public on
phabricator.services.mozilla.com).

This script writes:
  * raw_data/D<N>.json           — one per revision
  * raw_data/_failures.json      — list of D-numbers whose fetch/parse failed
  * data_phab.json               — aggregated wait-time data for the report
"""

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reviewstats.github_commits import fetch_commits
from reviewstats.members import MEMBER_IDS
from reviewstats.metrics import iso_week
from reviewstats.teams import PLAYBACK_TEAM
from reviewstats.patch_list import build_patch_list
from reviewstats.phab_html import (
    Event,
    bulk_fetch_async,
    extract_author_handle,
    first_member_review_action,
    first_review_action,
    parse_timeline,
)
from reviewstats.wait_time import (
    aggregate_wait_times,
    member_authored_wait_revisions,
)


# Path / excludes flow from the team registry — see analyze_git.py
# for the same pattern. Adding a second team is a config-only change.
_DEFAULT_TEAM = PLAYBACK_TEAM
_DEFAULT_REPO = "mozilla-firefox/firefox"
_DEFAULT_MONTHS = 6
_OUT_DIR = Path(__file__).resolve().parent
_RAW_DIR = _OUT_DIR / "raw_data"
_HTML_CACHE_DIR = _OUT_DIR / ".phab_html_cache"
_FAILURES_PATH = _RAW_DIR / "_failures.json"


def _raw_path(d_number: str) -> Path:
    return _RAW_DIR / f"{d_number}.json"


def _html_cache_path(d_number: str) -> Path:
    return _HTML_CACHE_DIR / f"{d_number}.html"


def select_fetch_targets(
    d_numbers: list[str],
    *,
    raw_dir: Path,
    html_cache_dir: Path,
    force: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Split `d_numbers` into (skip, from_cache, to_fetch).

    * skip       — `raw_data/D<n>.json` already exists; do nothing.
    * from_cache — raw missing, but `.phab_html_cache/D<n>.html` exists;
                   re-parse without hitting the network.
    * to_fetch   — neither cached; need a Playwright fetch.

    With `force=True`, the raw-data check is bypassed so every D-number
    becomes a fetch (or HTML-cached re-parse) candidate. This is the
    function that guarantees weekly refreshes don't re-pay the cost of
    revisions we already have.
    """
    skip: list[str] = []
    candidates: list[str] = []
    for d in d_numbers:
        if not force and (raw_dir / f"{d}.json").exists():
            skip.append(d)
        else:
            candidates.append(d)
    from_cache = [
        d for d in candidates if (html_cache_dir / f"{d}.html").exists()
    ]
    to_fetch = [
        d for d in candidates if not (html_cache_dir / f"{d}.html").exists()
    ]
    return skip, from_cache, to_fetch


def _load_existing(d_number: str) -> dict | None:
    path = _raw_path(d_number)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_html_to_raw(html: str, d_number: str) -> dict:
    """Parse a Phab revision page into a team-agnostic dict.

    The returned shape is what we persist to raw_data/D<n>.json so
    the same file is reusable for any team that has this revision
    in scope. Team-specific metrics (queue anchor, first-member
    actions) are NOT included here — they're recomputed at
    aggregation time by `compute_team_metrics`.

    Fields are intentionally limited to:
      * d_number / author / created_at / events
      * time_to_react_seconds, time_to_accept_seconds — the
        "first ANY non-author non-bot" anchor, which doesn't
        depend on which team is asking.
    """
    events = parse_timeline(html)
    create = next((e for e in events if e.action == "create"), None)
    author = extract_author_handle(html) or (create.actor if create else None)
    created_at = create.timestamp if create else None

    first_any_react = first_review_action(events, author=author)
    first_any_accept = first_review_action(events, author=author, action="accept")
    time_to_react_seconds = (
        int((first_any_react.timestamp - created_at).total_seconds())
        if (first_any_react and created_at)
        else None
    )
    time_to_accept_seconds = (
        int((first_any_accept.timestamp - created_at).total_seconds())
        if (first_any_accept and created_at)
        else None
    )

    return {
        "d_number": d_number,
        "author": author,
        "created_at": created_at.isoformat() if created_at else None,
        "events": [
            {
                "ts": e.timestamp.isoformat(),
                "actor": e.actor,
                "action": e.action,
                **({"target": e.target} if e.target else {}),
            }
            for e in events
        ],
        "time_to_react_seconds": time_to_react_seconds,
        "time_to_accept_seconds": time_to_accept_seconds,
    }


def compute_team_metrics(raw: dict, *, group: str, members: frozenset[str]) -> dict:
    """Derive team-specific metrics from a team-agnostic raw entry.

    Returns the dict shape that the wait-time aggregator + Wait Queue
    builders consume — `queue_added_at`, `queue_seconds`,
    `queue_to_accept_seconds`, `first_member_review`, `first_member_accept`.

    Called per (revision, team) at aggregation time; the result is
    NOT persisted, so adding/removing a team or editing its roster
    only requires recomputing in memory, never refetching from Phab.
    """
    author = raw.get("author")
    created_at_iso = raw.get("created_at")
    created_at = (
        datetime.fromisoformat(created_at_iso) if created_at_iso else None
    )
    events = [
        Event(
            timestamp=datetime.fromisoformat(e["ts"]),
            actor=e.get("actor") or "",
            action=e["action"],
            raw_verb="",  # not persisted; not used by review-action helpers
            target=e.get("target"),
        )
        for e in raw.get("events", [])
    ]
    first = first_member_review_action(events, members=members, author=author)
    wait_seconds = (
        int((first.timestamp - created_at).total_seconds())
        if (first and created_at)
        else None
    )
    first_accept = None
    for e in events:
        if (
            e.action == "accept"
            and e.actor != author
            and e.actor in members
        ):
            first_accept = e
            break
    queue_added_at = None
    queue_seconds = None
    queue_to_accept_seconds = None
    if first:
        for e in events:
            if e.timestamp > first.timestamp:
                break
            if e.action == "add-reviewer" and e.target == group:
                queue_added_at = e.timestamp
        if queue_added_at:
            queue_seconds = int(
                (first.timestamp - queue_added_at).total_seconds()
            )
            if first_accept:
                queue_to_accept_seconds = int(
                    (first_accept.timestamp - queue_added_at).total_seconds()
                )
    return {
        "queue_added_at": (
            queue_added_at.isoformat() if queue_added_at else None
        ),
        "queue_seconds": queue_seconds,
        "queue_to_accept_seconds": queue_to_accept_seconds,
        "first_member_accept": (
            {
                "actor": first_accept.actor,
                "ts": first_accept.timestamp.isoformat(),
            }
            if first_accept
            else None
        ),
        "first_member_review": (
            {
                "actor": first.actor,
                "action": first.action,
                "ts": first.timestamp.isoformat(),
                "wait_seconds": wait_seconds,
            }
            if first
            else None
        ),
    }


def _process_html(html: str, d_number: str, *, group: str, members: frozenset[str]) -> dict:
    """Backwards-compatible combiner — returns the full per-revision
    dict (agnostic + team-specific) for the supplied team. Kept so
    on-disk raw_data files written before the M9 split don't have to
    be regenerated; new writes use `parse_html_to_raw` directly.
    """
    raw = parse_html_to_raw(html, d_number)
    team_metrics = compute_team_metrics(raw, group=group, members=members)
    return {**raw, **team_metrics}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=_DEFAULT_REPO,
        help='GitHub repo "owner/name" (default: mozilla-firefox/firefox).',
    )
    parser.add_argument("--path", default=_DEFAULT_TEAM.paths[0])
    parser.add_argument(
        "--months",
        type=int,
        default=_DEFAULT_MONTHS,
        help="Window size in months back from today.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Concurrent in-flight Playwright fetches.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even revisions that already have raw_data entries.",
    )
    args = parser.parse_args()

    since = (
        datetime.now(timezone.utc) - timedelta(days=30 * args.months)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Fetching commits from github.com/{args.repo} (since {since})...")
    commits = fetch_commits(
        repo=args.repo,
        path=args.path,
        since=since,
        exclude_paths=_DEFAULT_TEAM.excludes,
    )
    commits_by_d = {
        c.differential_revision: c
        for c in commits
        if c.differential_revision
    }
    d_numbers = sorted(commits_by_d.keys())
    print(f"Found {len(d_numbers)} commits with Differential Revision links.")

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    skip, from_cache, to_fetch = select_fetch_targets(
        d_numbers,
        raw_dir=_RAW_DIR,
        html_cache_dir=_HTML_CACHE_DIR,
        force=args.force,
    )
    print(
        f"Total {len(d_numbers)} revisions.  "
        f"Cached raw_data: {len(skip)}.  "
        f"Re-parse from cached HTML: {len(from_cache)}.  "
        f"Fetch via Playwright: {len(to_fetch)}."
    )

    failures: dict[str, str] = {}

    for d in from_cache:
        try:
            html = _html_cache_path(d).read_text(encoding="utf-8")
            payload = _process_html(html, d, group=_DEFAULT_TEAM.group, members=MEMBER_IDS)
            _raw_path(d).write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception as e:
            failures[d] = f"{type(e).__name__}: {e}"
    if from_cache:
        print(f"Re-parsed {len(from_cache) - len(failures)} from cached HTML.")

    progress = {"i": 0}

    def on_each(d: str, result) -> None:
        progress["i"] += 1
        i = progress["i"]
        if isinstance(result, Exception):
            failures[d] = f"{type(result).__name__}: {result}"
        else:
            _HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _html_cache_path(d).write_text(result, encoding="utf-8")
            try:
                payload = _process_html(result, d, group=_DEFAULT_TEAM.group, members=MEMBER_IDS)
                _raw_path(d).write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"
                )
            except Exception as e:
                failures[d] = f"{type(e).__name__}: {e}"
        if i % 25 == 0 or i == len(to_fetch):
            print(
                f"  {i}/{len(to_fetch)}  "
                f"(ok={i - len(failures)}, fail={len(failures)})"
            )

    if to_fetch:
        asyncio.run(
            bulk_fetch_async(
                to_fetch,
                concurrency=args.concurrency,
                on_each=on_each,
            )
        )

    if failures:
        _FAILURES_PATH.write_text(
            json.dumps(failures, indent=2), encoding="utf-8"
        )
    elif _FAILURES_PATH.exists():
        _FAILURES_PATH.unlink()

    # Aggregate from raw_data/*.json (no further API calls).
    # `queue_seconds` is our headline metric: time from when
    # `media-playback-reviewers` was added to the revision's reviewer
    # list, to when the first listed member reacted. Per-member
    # attribution is intentionally not used here — anyone in the
    # rotation could have responded; the first one's identity isn't
    # a measure of *their* responsiveness, just team responsiveness.
    # Scope: only patches authored by a listed member. Filter contract
    # pinned by test_wait_revisions_filter.py.
    per_revision = member_authored_wait_revisions(
        d_numbers, _load_existing, commits_by_d, members=MEMBER_IDS,
    )

    # Per-author wait-time breakdown (for Member Profile view).
    # "How long does this author's patch wait for review?" — only
    # meaningful when the author IS the one waiting. Filtered to
    # members so we have a single bounded set in the report.
    # Per-author wait-time uses the broader anchor: from revision
    # creation to the first reaction/accept by ANY non-author non-bot
    # reviewer. This covers all patches the author submitted, not
    # just ones that went through `media-playback-reviewers` — which
    # is what the Member Profile view shows ("my patches' wait time").
    per_author: dict[str, dict] = {}
    for d in d_numbers:
        raw = _load_existing(d)
        if raw is None:
            continue
        author = raw.get("author")
        if author not in MEMBER_IDS:
            continue
        bucket = per_author.setdefault(author, {
            "n_total": 0, "react_days": [], "accept_days": [],
        })
        bucket["n_total"] += 1
        if raw.get("time_to_react_seconds") is not None:
            bucket["react_days"].append(raw["time_to_react_seconds"] / 86400.0)
        if raw.get("time_to_accept_seconds") is not None:
            bucket["accept_days"].append(
                raw["time_to_accept_seconds"] / 86400.0
            )

    def _pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        k = (len(s) - 1) * p / 100.0
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    per_author_summary = {
        author: {
            "n_total": b["n_total"],
            "n_react": len(b["react_days"]),
            "n_accept": len(b["accept_days"]),
            "react_p50": _pct(b["react_days"], 50),
            "react_p75": _pct(b["react_days"], 75),
            "react_p90": _pct(b["react_days"], 90),
            "accept_p50": _pct(b["accept_days"], 50),
            "accept_p75": _pct(b["accept_days"], 75),
            "accept_p90": _pct(b["accept_days"], 90),
        }
        for author, b in per_author.items()
    }

    # Build the Wait Queue per-revision list (sorted longest-wait first).
    # Scoped to member-authored patches for the same reason as the
    # per_revision aggregation above.
    raw_entries_by_d: dict[str, dict] = {}
    for d in d_numbers:
        raw = _load_existing(d)
        if raw is not None:
            raw_entries_by_d[d] = raw
    patch_rows = build_patch_list(
        raw_entries_by_d, commits_by_d, members=MEMBER_IDS,
    )

    aggregated = aggregate_wait_times(per_revision)
    aggregated["per_author"] = per_author_summary
    aggregated["patch_list"] = patch_rows
    aggregated["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_commits": len(commits),
        "n_with_revision": len(d_numbers),
        "n_with_wait_time": aggregated["n"],
        "n_failures": len(failures),
        "partial": bool(failures),
    }

    # For now Phab analysis is playback-only; lands in the playback
    # subfolder so the per-team index.html picks it up. Multi-team
    # support comes in a follow-up commit that refactors
    # _process_html to compute team-specific metrics on demand.
    team_dir = _OUT_DIR / _DEFAULT_TEAM.slug
    team_dir.mkdir(parents=True, exist_ok=True)
    out_path = team_dir / "data_phab.json"
    out_path.write_text(
        json.dumps(aggregated, indent=2, default=str), encoding="utf-8"
    )
    print(
        f"Wrote {out_path}  (n={aggregated['n']}, "
        f"failures={len(failures)}, partial={aggregated['meta']['partial']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
