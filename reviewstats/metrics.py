"""Pure aggregation metrics over parsed commits."""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Iterable, Protocol

from reviewstats.aliases import canonicalize_author
from reviewstats.parse import Reviewer


class _CommitLike(Protocol):
    reviewers: list[Reviewer]
    date: datetime
    author: str


def iso_week(date: datetime) -> str:
    iso = date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def filter_commits_within(
    commits: Iterable[_CommitLike],
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[_CommitLike]:
    """Return commits with `window_start <= c.date <= window_end`.

    Inclusive on both ends. Accepts any iterable so callers can pass a
    generator straight through without materialising it.
    """
    return [c for c in commits if window_start <= c.date <= window_end]


def _has_group(commit: _CommitLike, group: str) -> bool:
    return any(r.is_group and r.name == group for r in commit.reviewers)


def _individuals(commit: _CommitLike) -> list[str]:
    return [r.name for r in commit.reviewers if not r.is_group]


def _keep(name: str, members: frozenset[str] | None) -> bool:
    return members is None or name in members


def count_by_individual(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str] | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for c in commits:
        if not _has_group(c, group):
            continue
        counts.update(n for n in _individuals(c) if _keep(n, members))
    return dict(counts)


def non_member_reviewer_counts(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for c in commits:
        if not _has_group(c, group):
            continue
        counts.update(n for n in _individuals(c) if n not in members)
    return dict(counts)


def routing_breakdown(commits: Iterable[_CommitLike], *, group: str) -> dict[str, int]:
    total = 0
    group_tagged = 0
    group_with_individual = 0
    group_only = 0
    for c in commits:
        total += 1
        if _has_group(c, group):
            group_tagged += 1
            if _individuals(c):
                group_with_individual += 1
            else:
                group_only += 1
    return {
        "total": total,
        "group_tagged": group_tagged,
        "group_with_individual": group_with_individual,
        "group_only": group_only,
    }


def primary_subdir(
    files: list[str],
    *,
    path: str | None = None,
    paths: tuple[str, ...] | None = None,
) -> str | None:
    """Pick the single bucket that best represents a commit, given the
    files it touched and the root path(s) we're scoped to.

    Single-root mode (`path="dom/media"`): return the immediate
    subdirectory of `path` with the most files changed. Top-level
    files (directly under `path/`) bucket as '(top-level)'.

    Multi-root mode (`paths=("dom/media/webrtc", "...")`): return the
    root path itself (e.g. "dom/media/webrtc") that the commit
    touches most. Coarser than splitting by subdir-within-each-root,
    intentional — for a multi-path team like WebRTC the more useful
    question is "did this land in webrtc proper, systemservices, or
    libwebrtc?", not "which audio sub-subdir".

    Ties broken alphabetically for determinism. Returns None when no
    file lies under any of the supplied path(s).

    Pass exactly one of `path` or `paths` — both is a programming
    error (TypeError).
    """
    if (path is None) == (paths is None):
        raise TypeError("Pass exactly one of `path` or `paths`")
    if path is not None:
        return _primary_subdir_single(files, path=path)
    return _primary_root(files, paths=paths)


def _primary_subdir_single(files: list[str], *, path: str) -> str | None:
    counts: Counter[str] = Counter()
    prefix = path.rstrip("/") + "/"
    for fn in files:
        if not fn.startswith(prefix):
            continue
        rest = fn[len(prefix):]
        bucket = rest.split("/")[0] if "/" in rest else "(top-level)"
        counts[bucket] += 1
    if not counts:
        return None
    best_count = max(counts.values())
    candidates = sorted(b for b, c in counts.items() if c == best_count)
    return candidates[0]


def _primary_root(files: list[str], *, paths: tuple[str, ...]) -> str | None:
    # Sort longer prefixes first so 'dom/media/webrtc' wins over
    # 'dom/media' when both are in the team's paths.
    prefixes = sorted(paths, key=len, reverse=True)
    counts: Counter[str] = Counter()
    for fn in files:
        for p in prefixes:
            prefix = p.rstrip("/") + "/"
            if fn.startswith(prefix) or fn == p:
                counts[p] += 1
                break
    if not counts:
        return None
    best_count = max(counts.values())
    candidates = sorted(b for b, c in counts.items() if c == best_count)
    return candidates[0]


def classify_landed_without_team_review_by_subdir(
    bad_commits: list[tuple[_CommitLike, list[str]]],
    *,
    path: str | None = None,
    paths: tuple[str, ...] | None = None,
) -> dict[str, int]:
    """Aggregate (commit, files_changed) pairs into {bucket: count}.

    Bucket scheme follows `primary_subdir`: single-root mode buckets
    by immediate subdir; multi-root mode buckets by which root path
    each commit touches most.
    """
    out: Counter[str] = Counter()
    for _commit, files in bad_commits:
        sub = primary_subdir(files, path=path, paths=paths)
        if sub is None:
            out["(unknown)"] += 1
        else:
            out[sub] += 1
    return dict(out)


def has_team_review(
    commit: _CommitLike,
    *,
    group: str,
    members: frozenset[str],
    approved: frozenset[str] = frozenset(),
) -> bool:
    """True if a patch had valid team oversight: the team group tag, a
    listed-member individual reviewer, or an `approved` reviewer.

    `approved` reviewers are trusted handles that are NOT on the team
    roster (so they never appear in any load-distribution view) but whose
    review still counts as approval. The single source of truth for the
    "landed without team review" classification — used both by the count
    below and by the per-commit bad-list builder in analyze_git.
    """
    if _has_group(commit, group):
        return True
    return any(name in members or name in approved for name in _individuals(commit))


def landed_without_team_review(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str],
    approved: frozenset[str] = frozenset(),
) -> int:
    """Count patches that landed with neither the team group tag, a
    listed-member individual reviewer, nor an `approved` reviewer.

    A non-zero value signals patches reaching dom/media without anyone
    trusted by the team checking the work — usually a queue health red
    flag.
    """
    return sum(
        1
        for c in commits
        if not has_team_review(
            c, group=group, members=members, approved=approved
        )
    )


def sole_reviewer_counts(
    commits: Iterable[_CommitLike],
    *,
    members: frozenset[str] | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for c in commits:
        if len(c.reviewers) != 1:
            continue
        only = c.reviewers[0]
        if only.is_group or not _keep(only.name, members):
            continue
        counts[only.name] += 1
    return dict(counts)


def weekly_counts_per_reviewer(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str] | None = None,
) -> dict[str, dict[str, int]]:
    """{ "2026-W20": { "padenot": 5, ... }, ... }"""
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in commits:
        if not _has_group(c, group):
            continue
        week = iso_week(c.date)
        for name in _individuals(c):
            if _keep(name, members):
                out[week][name] += 1
    return {wk: dict(d) for wk, d in out.items()}


def total_reviews_per_member(
    commits: Iterable[_CommitLike],
    *,
    group: str,
    members: frozenset[str],
) -> list[dict]:
    in_group: Counter[str] = Counter()
    out_of_group: Counter[str] = Counter()
    for c in commits:
        bucket = in_group if _has_group(c, group) else out_of_group
        bucket.update(n for n in _individuals(c) if n in members)
    names = set(in_group) | set(out_of_group)
    rows = [
        {
            "name": n,
            "in_group": in_group.get(n, 0),
            "out_of_group": out_of_group.get(n, 0),
            "total": in_group.get(n, 0) + out_of_group.get(n, 0),
        }
        for n in names
    ]
    rows.sort(key=lambda r: -r["total"])
    return rows


def weekly_authored_per_member(
    commits: Iterable[_CommitLike],
    members: dict[str, str],
    weeks: list[str],
) -> dict[str, list[int]]:
    """Per-(member, week) count of unique patches the member authored.

    `members` is the {handle: display_name} dict from members.py.
    Authors are matched via `canonicalize_author` so alastor0325 /
    alwu / 'Alastor Wu' all map to the alwu handle.

    Returns `{handle: [count per week]}` — every member appears,
    every week aligned with the input `weeks` list (zero-filled).
    Re-lands (multiple commits sharing one D-number) count once,
    placed in the earliest week they landed in.

    Used by the Member Profile / Weekly activity chart's "patches
    submitted" line.
    """
    canonical_to_handle = {display: handle for handle, display in members.items()}
    week_set = set(weeks)

    # For each (handle, D-number), record the EARLIEST week it landed.
    earliest_week: dict[tuple[str, str], str] = {}
    for c in commits:
        canon = canonicalize_author(c.author)
        handle = canonical_to_handle.get(canon)
        if handle is None:
            continue
        wk = iso_week(c.date)
        if wk not in week_set:
            continue
        key = (handle, getattr(c, "differential_revision", None) or f"sha:{c.sha}")
        prev = earliest_week.get(key)
        if prev is None or wk < prev:
            earliest_week[key] = wk

    counts: dict[str, dict[str, int]] = {h: {} for h in members}
    for (handle, _d), wk in earliest_week.items():
        counts[handle][wk] = counts[handle].get(wk, 0) + 1

    return {
        handle: [counts[handle].get(wk, 0) for wk in weeks]
        for handle in members
    }


def author_patch_counts(
    commits: Iterable[_CommitLike],
) -> dict[str, int]:
    """Count unique patches (D-numbers) per author.

    A patch that's backed out and re-landed shows up as multiple
    commits with the same Differential Revision — we count it once.
    Commits without a Differential Revision (rare for filtered
    dom/media) count individually.
    """
    seen: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    for c in commits:
        author = canonicalize_author(c.author)
        d = getattr(c, "differential_revision", None)
        if d:
            if d in seen[author]:
                continue
            seen[author].add(d)
        counts[author] += 1
    return dict(counts)


def author_reviewer_pairs(
    commits: Iterable[_CommitLike],
    *,
    members: frozenset[str] | None = None,
) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for c in commits:
        author = canonicalize_author(c.author)
        for name in _individuals(c):
            if _keep(name, members):
                out[author][name] += 1
    return {a: dict(d) for a, d in out.items() if d}


def reviewer_to_authors(
    commits: Iterable[_CommitLike],
    *,
    members: frozenset[str],
) -> dict[str, list[dict]]:
    """For each member, return an ordered list of {name, count} for the
    authors whose patches they reviewed (descending by count).
    """
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for c in commits:
        author = canonicalize_author(c.author)
        for name in _individuals(c):
            if name in members:
                out[name][author] += 1
    return {
        member: [
            {"name": author, "count": cnt}
            for author, cnt in sorted(counter.items(), key=lambda kv: -kv[1])
        ]
        for member, counter in out.items()
    }


def compute_gini(counts: list[int]) -> float:
    """Gini coefficient. 0 = perfectly even, 1 = one person has everything."""
    n = len(counts)
    if n <= 1:
        return 0.0
    total = sum(counts)
    if total == 0:
        return 0.0
    sorted_counts = sorted(counts)
    cumulative_index_weighted = sum(
        (i + 1) * v for i, v in enumerate(sorted_counts)
    )
    return (2 * cumulative_index_weighted) / (n * total) - (n + 1) / n


def top_n_share(counts: dict[str, int], n: int) -> float:
    if not counts:
        return 0.0
    total = sum(counts.values())
    if total == 0:
        return 0.0
    sorted_vals = sorted(counts.values(), reverse=True)
    return sum(sorted_vals[:n]) / total


def bus_factor(counts: dict[str, int], *, threshold: float) -> int:
    if not counts:
        return 0
    total = sum(counts.values())
    if total == 0:
        return 0
    sorted_vals = sorted(counts.values(), reverse=True)
    accum = 0
    for k, v in enumerate(sorted_vals, start=1):
        accum += v
        if accum / total >= threshold:
            return k
    return len(sorted_vals)
