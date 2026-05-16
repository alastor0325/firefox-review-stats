#!/usr/bin/env python3
"""Phase 2: fetch Phabricator wait-time data for dom/media commits.

Reads the same set of commits as analyze_git.py, looks up each commit's
Differential Revision via Conduit, computes wait time (submit → first
review action), and writes data_phab.json.

Cached per-revision in .phab_cache/ to keep weekly re-runs cheap.
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from reviewstats.git_log import parse_git_log_output, run_git_log
from reviewstats.members import MEMBER_IDS
from reviewstats.metrics import iso_week
from reviewstats.phab import (
    fetch_revisions,
    fetch_transactions,
    read_token,
)
from reviewstats.wait_time import (
    aggregate_wait_times,
    first_review_timestamp,
    wait_time_days,
)


REPO = str(Path.home() / "firefox")
PATH = "dom/media"
EXCLUDE_PATHS = ("dom/media/webrtc",)
SINCE = "6 months ago"
OUT_DIR = Path(__file__).resolve().parent
CACHE_DIR = OUT_DIR / ".phab_cache"


def _cache_path(d_number: str) -> Path:
    return CACHE_DIR / f"{d_number}.json"


def _load_cached(d_number: str, date_modified: int | None) -> dict | None:
    path = _cache_path(d_number)
    if not path.exists():
        return None
    cached = json.loads(path.read_text(encoding="utf-8"))
    if date_modified is None:
        return cached
    if cached.get("date_modified") != date_modified:
        return None
    return cached


def _save_cache(d_number: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(d_number).write_text(
        json.dumps(payload), encoding="utf-8"
    )


def main() -> int:
    token = read_token()

    raw_log = run_git_log(REPO, PATH, SINCE, exclude_paths=EXCLUDE_PATHS)
    commits = parse_git_log_output(raw_log)
    commits_by_d = {
        c.differential_revision: c
        for c in commits
        if c.differential_revision
    }
    d_numbers = sorted(commits_by_d.keys())
    print(f"Found {len(d_numbers)} commits with Differential Revision links.")

    # 1) Load cached metadata if any (full entries: meta + transactions).
    cached_full: dict[str, dict] = {}
    for d in d_numbers:
        path = _cache_path(d)
        if path.exists():
            entry = json.loads(path.read_text(encoding="utf-8"))
            if "author_phid" in entry:
                cached_full[d] = entry

    missing_meta = [d for d in d_numbers if d not in cached_full]
    if missing_meta:
        print(f"Fetching metadata for {len(missing_meta)} new revisions...")
        metadata = fetch_revisions(missing_meta, token=token)
    else:
        metadata = {}
    print(f"Cached: {len(cached_full)}  New meta fetched: {len(metadata)}")

    # 2) Per-revision transactions (extending cache).
    per_revision: list[dict] = []
    new_calls = 0
    for i, d in enumerate(d_numbers, 1):
        if d in cached_full:
            entry = cached_full[d]
        else:
            meta = metadata.get(d)
            if not meta:
                continue
            txs = fetch_transactions(meta["phid"], token=token)
            new_calls += 1
            entry = {**meta, "transactions": txs}
            _save_cache(d, entry)
            time.sleep(0.3)
        first = first_review_timestamp(
            entry["transactions"], author_phid=entry["author_phid"]
        )
        wait_days = wait_time_days(
            date_created=entry["date_created"], first_review=first
        )
        commit = commits_by_d[d]
        # Reviewer attribution: in this Phase-1 view, pick the first
        # member from the commit's `r=` list (if any).
        reviewer = next(
            (r.name for r in commit.reviewers
             if not r.is_group and r.name in MEMBER_IDS),
            None,
        )
        per_revision.append({
            "d_number": d,
            "wait_days": wait_days,
            "reviewer": reviewer,
            "week": iso_week(commit.date),
        })
        if i % 50 == 0:
            print(f"  {i}/{len(d_numbers)}  (new API calls: {new_calls})")

    print(f"Finished. {new_calls} new transaction calls (rest cached).")

    aggregated = aggregate_wait_times(per_revision)
    aggregated["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_commits": len(commits),
        "n_with_revision": len(d_numbers),
        "n_with_wait_time": aggregated["n"],
    }

    out_path = OUT_DIR / "data_phab.json"
    out_path.write_text(
        json.dumps(aggregated, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
