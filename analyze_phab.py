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
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.git_log import parse_git_log_output, run_git_log
from reviewstats.members import MEMBER_IDS
from reviewstats.metrics import iso_week
from reviewstats.phab_html import (
    fetch_revision_page,
    first_member_review_action,
    parse_timeline,
)
from reviewstats.wait_time import aggregate_wait_times


_DEFAULT_REPO = str(Path.home() / "firefox")
_DEFAULT_PATH = "dom/media"
_DEFAULT_SINCE = "6 months ago"
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


def _process_one(
    d_number: str, *, members: frozenset[str], polite_sleep: float
) -> dict:
    cached_html = _html_cache_path(d_number)
    if cached_html.exists():
        html = cached_html.read_text(encoding="utf-8")
    else:
        time.sleep(polite_sleep)
        html = fetch_revision_page(d_number)
        _HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached_html.write_text(html, encoding="utf-8")
    events = parse_timeline(html)
    # Use the create event's actor as the canonical author handle. Git's
    # display name (`%an`) is "Alastor Wu" but Phab's actor handle is
    # "alwu" — using the create event keeps the namespace consistent.
    create = next((e for e in events if e.action == "create"), None)
    author = create.actor if create else None
    first = first_member_review_action(events, members=members, author=author)
    created_at = create.timestamp if create else None
    wait_seconds = (
        int((first.timestamp - created_at).total_seconds())
        if (first and created_at)
        else None
    )

    # Queue time = first member reaction − latest `add-reviewer:
    # media-playback-reviewers` event preceding that reaction. This is
    # the answer to "once the team was put on the patch, how long until
    # somebody on the rotation reacted?"
    queue_added_at = None
    queue_seconds = None
    if first:
        for e in events:
            if e.timestamp > first.timestamp:
                break
            if e.action == "add-reviewer" and e.target == "media-playback-reviewers":
                queue_added_at = e.timestamp
        if queue_added_at:
            queue_seconds = int(
                (first.timestamp - queue_added_at).total_seconds()
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
    parser.add_argument("--repo", default=_DEFAULT_REPO)
    parser.add_argument("--path", default=_DEFAULT_PATH)
    parser.add_argument("--since", default=_DEFAULT_SINCE)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.5,
        help="Per-request polite sleep before each fetch (seconds).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even revisions that already have raw_data entries.",
    )
    args = parser.parse_args()

    raw_log = run_git_log(
        args.repo, args.path, args.since, exclude_paths=_DEFAULT_EXCLUDE
    )
    commits = parse_git_log_output(raw_log)
    commits_by_d = {
        c.differential_revision: c
        for c in commits
        if c.differential_revision
    }
    d_numbers = sorted(commits_by_d.keys())
    print(f"Found {len(d_numbers)} commits with Differential Revision links.")

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    to_fetch = [
        d for d in d_numbers
        if args.force or _load_existing(d) is None
    ]
    print(
        f"Already cached: {len(d_numbers) - len(to_fetch)}.  "
        f"Will fetch: {len(to_fetch)}."
    )

    failures: dict[str, str] = {}

    def submit(d: str) -> tuple[str, dict | None, str | None]:
        try:
            payload = _process_one(
                d, members=MEMBER_IDS, polite_sleep=args.sleep
            )
            _raw_path(d).write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            return d, payload, None
        except Exception as e:
            return d, None, f"{type(e).__name__}: {e}"

    if to_fetch:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(submit, d) for d in to_fetch]
            for i, fut in enumerate(as_completed(futures), 1):
                d, _payload, err = fut.result()
                if err:
                    failures[d] = err
                if i % 25 == 0:
                    print(
                        f"  {i}/{len(to_fetch)}  "
                        f"(ok={i - len(failures)}, fail={len(failures)})"
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

    aggregated = aggregate_wait_times(per_revision)
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
