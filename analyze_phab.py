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
from reviewstats.phab_html import (
    bulk_fetch_async,
    extract_author_handle,
    first_member_review_action,
    first_review_action,
    parse_timeline,
)
from reviewstats.wait_time import aggregate_wait_times


_DEFAULT_REPO = "mozilla-firefox/firefox"
_DEFAULT_PATH = "dom/media"
_DEFAULT_MONTHS = 6
_DEFAULT_EXCLUDE = ("dom/media/webrtc",)
_OUT_DIR = Path(__file__).resolve().parent
_RAW_DIR = _OUT_DIR / "raw_data"
_HTML_CACHE_DIR = _OUT_DIR / ".phab_html_cache"
_FAILURES_PATH = _RAW_DIR / "_failures.json"


def _raw_path(d_number: str) -> Path:
    return _RAW_DIR / f"{d_number}.json"


def _html_cache_path(d_number: str) -> Path:
    return _HTML_CACHE_DIR / f"{d_number}.html"


def _load_existing(d_number: str) -> dict | None:
    path = _raw_path(d_number)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _process_html(html: str, d_number: str, *, members: frozenset[str]) -> dict:
    events = parse_timeline(html)
    # Author handle from the page header — always present, even for
    # older revisions whose `created` event has paged off the timeline.
    # Fall back to the create event's actor as a sanity check.
    create = next((e for e in events if e.action == "create"), None)
    author = extract_author_handle(html) or (create.actor if create else None)
    first = first_member_review_action(events, members=members, author=author)
    created_at = create.timestamp if create else None
    wait_seconds = (
        int((first.timestamp - created_at).total_seconds())
        if (first and created_at)
        else None
    )

    # First accept by a listed member (subset of review actions).
    first_accept = None
    for e in events:
        if (
            e.action == "accept"
            and e.actor != author
            and e.actor in members
        ):
            first_accept = e
            break

    # From-creation wait by ANY non-author non-bot reviewer (used in
    # Member Profile per-author wait-time tiles — answers "how long
    # does the author have to wait for a reaction on their patches,
    # regardless of which reviewer ended up looking").
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

    # Queue anchor: latest `add-reviewer: media-playback-reviewers`
    # event preceding the first member reaction. Answers "once the
    # team was put on the patch, how long until someone reacted /
    # accepted?"
    queue_added_at = None
    queue_seconds = None
    queue_to_accept_seconds = None
    if first:
        for e in events:
            if e.timestamp > first.timestamp:
                break
            if (
                e.action == "add-reviewer"
                and e.target == "media-playback-reviewers"
            ):
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
        "queue_added_at": (
            queue_added_at.isoformat() if queue_added_at else None
        ),
        "queue_seconds": queue_seconds,
        "queue_to_accept_seconds": queue_to_accept_seconds,
        "time_to_react_seconds": time_to_react_seconds,
        "time_to_accept_seconds": time_to_accept_seconds,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=_DEFAULT_REPO,
        help='GitHub repo "owner/name" (default: mozilla-firefox/firefox).',
    )
    parser.add_argument("--path", default=_DEFAULT_PATH)
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
        exclude_paths=_DEFAULT_EXCLUDE,
    )
    commits_by_d = {
        c.differential_revision: c
        for c in commits
        if c.differential_revision
    }
    d_numbers = sorted(commits_by_d.keys())
    print(f"Found {len(d_numbers)} commits with Differential Revision links.")

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [
        d for d in d_numbers
        if args.force or _load_existing(d) is None
    ]

    # Re-process anything with cached HTML synchronously — that's just
    # a parse + write, no network needed. Only the remainder goes to
    # Playwright.
    from_cache = [d for d in candidates if _html_cache_path(d).exists()]
    to_fetch = [d for d in candidates if not _html_cache_path(d).exists()]
    print(
        f"Total {len(d_numbers)} revisions.  "
        f"Cached raw_data: {len(d_numbers) - len(candidates)}.  "
        f"Re-parse from cached HTML: {len(from_cache)}.  "
        f"Fetch via Playwright: {len(to_fetch)}."
    )

    failures: dict[str, str] = {}

    for d in from_cache:
        try:
            html = _html_cache_path(d).read_text(encoding="utf-8")
            payload = _process_html(html, d, members=MEMBER_IDS)
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
                payload = _process_html(result, d, members=MEMBER_IDS)
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
    per_revision: list[dict] = []
    for d in d_numbers:
        raw = _load_existing(d)
        if raw is None:
            continue
        queue_s = raw.get("queue_seconds")
        if queue_s is None:
            continue
        commit = commits_by_d[d]
        per_revision.append({
            "d_number": d,
            "wait_days": queue_s / 86400.0,
            "reviewer": (raw.get("first_member_review") or {}).get("actor"),
            "week": iso_week(commit.date),
        })

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

    aggregated = aggregate_wait_times(per_revision)
    aggregated["per_author"] = per_author_summary
    aggregated["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_commits": len(commits),
        "n_with_revision": len(d_numbers),
        "n_with_wait_time": aggregated["n"],
        "n_failures": len(failures),
        "partial": bool(failures),
    }

    out_path = _OUT_DIR / "data_phab.json"
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
