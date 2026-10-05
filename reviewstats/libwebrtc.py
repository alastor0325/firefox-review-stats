"""Which libwebrtc each supported Firefox release ships, what the next update
is, and how big the Mozilla patch stack is — the WebRTC page's libwebrtc view,
written by fetch_libwebrtc_status.py.

Versions only. The in-tree check_missing_branch_head_commits.py also lists
upstream branch-head commits a release has not vendored, but those are mostly
security fixes Chrome merged to its release branches, so on this public page
that list would be an index of unpatched bugs in shipping Firefox. Nothing here
keeps upstream commits; the only bug reference is the public fast-forward meta
bug. `project_view` is the one whitelist every payload passes through, on write
and on read.

The Releases table is the core and fails the fetch if it can't be built. The
Next-update and Patch-stack sections are optional: each falls back to last
week's copy (keeping its own `as_of`) so one flaky host can't freeze the rest.

Everything except `collect_status` and its `_fetch_*` helpers is pure.
"""

import base64
import json
import re
import urllib.error
from dataclasses import dataclass
from datetime import date, datetime

from reviewstats.github_commits import _DEFAULT_REPO

PRODUCT_DETAILS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"
CHROME_STABLE_URL = (
    "https://chromiumdash.appspot.com/fetch_releases"
    "?channel=Stable&platform=Windows&num=1"
)
CHROME_SCHEDULE_URL = "https://chromiumdash.appspot.com/fetch_milestone_schedule?mstone={}&n={}"
FIREFOX_TRAIN_URL = "https://whattrainisitnow.com/api/release/schedule/?version={}"
# Only counts are read, and an overflowing page already means "in progress".
GITILES_LOG_URL = "https://webrtc.googlesource.com/src/+log/{}..{}?format=JSON&n=200"
GITILES_HEAD_URL = "https://webrtc.googlesource.com/src/+log/refs/heads/main?format=JSON&n=1"
GITILES_COMMIT_URL = "https://webrtc.googlesource.com/src/+/{}?format=JSON"
UPCOMING = 3
HISTORY_MONTHS = 12

_REPO = f"/repos/{_DEFAULT_REPO}"
_CONFIG_ENV = "dom/media/webrtc/third_party_build/default_config_env"
_PATCH_STACK = "third_party/libwebrtc/moz-patch-stack"
_UPSTREAM_RE = re.compile(
    r"^Upstream commit: https://webrtc\.googlesource\.com/src/\+/([0-9a-f]{40})",
    re.MULTILINE,
)
# A main commit records its own position; a branch-head commit records the
# main position it branched from.
_MAIN_POSITION_RE = re.compile(
    r"^Cr-(?:Commit-Position|Branched-From):.*refs/heads/main@\{#(\d+)\}", re.MULTILINE)
_CHANNELS = (
    ("FIREFOX_NIGHTLY", "Nightly", "main"),
    ("LATEST_FIREFOX_DEVEL_VERSION", "Beta", "beta"),
    ("LATEST_FIREFOX_VERSION", "Release", "release"),
)
_VIEW_FIELDS = ("chrome_stable", "as_of")
_ROW_FIELDS = ("label", "firefox", "milestone", "branch_head", "branched",
               "vs_chrome", "in_progress", "last_change")
_LAST_CHANGE_FIELDS = ("date", "kind")
_CURRENT_FIELDS = ("milestone", "firefox", "fastforward_bug", "in_progress", "deadline")
_UPCOMING_FIELDS = ("milestone", "firefox", "chrome_branch", "chrome_stable",
                    "nightly_start", "merge_day")
_LAG_FIELDS = ("last_vendored", "upstream_head", "behind")
_STACK_RELEASE_FIELDS = ("label", "count")
_STACK_HISTORY_FIELDS = ("month", "count", "sampled")


@dataclass(frozen=True)
class Release:
    label: str
    branch: str


def supported_releases(versions: dict) -> list[Release]:
    """Release channels, then every ESR in the feed, newest first.

    ESRs are taken from any `FIREFOX_ESR*` key (FIREFOX_ESR, FIREFOX_ESR115,
    FIREFOX_ESR_NEXT, ...) and de-duplicated by major version.
    """
    out = [Release(label, branch) for key, label, branch in _CHANNELS
           if versions.get(key)]
    majors = {int(v.split(".")[0]) for k, v in versions.items()
              if k.startswith("FIREFOX_ESR") and v}
    out += [Release(f"ESR {m}", f"esr{m}") for m in sorted(majors, reverse=True)]
    return out


def parse_env_vars(text: str) -> dict[str, str]:
    """`export KEY=value` assignments from a default_config_env, comments
    skipped and quotes stripped."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def _int(value: str | None) -> int | None:
    return int(value) if value else None


def parse_config_env(text: str) -> tuple[int | None, str | None]:
    """(milestone, branch-head) from a branch's default_config_env."""
    env = parse_env_vars(text)
    return (_int(env.get("MOZ_NEXT_LIBWEBRTC_MILESTONE")),
            env.get("MOZ_TARGET_UPSTREAM_BRANCH_HEAD"))


def parse_rel_target(text: str) -> tuple[int | None, int | None]:
    """(Firefox release the next update targets, its fast-forward bug) from
    main's default_config_env."""
    env = parse_env_vars(text)
    return (_int(env.get("MOZ_NEXT_FIREFOX_REL_TARGET")),
            _int(env.get("MOZ_FASTFORWARD_BUG")))


def parse_gitiles_json(text: str) -> dict:
    """Gitiles prefixes JSON with `)]}'` to defeat XSSI; drop that line."""
    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]
    return json.loads(text)


def gitiles_date(time_str: str) -> str:
    """ISO date from a Gitiles committer time ('Mon Oct 05 15:02:17 2026',
    optionally followed by a UTC offset)."""
    return datetime.strptime(" ".join(time_str.split()[:5]),
                             "%a %b %d %H:%M:%S %Y").date().isoformat()


def main_position(message: str) -> int | None:
    """Upstream main commit number a commit is at (or branched from)."""
    m = _MAIN_POSITION_RE.search(message)
    return int(m.group(1)) if m else None


def classify_libwebrtc_change(commit: dict) -> str | None:
    """'vendor', 'cherry-pick', 'backport', or None for commits that touch
    third_party/libwebrtc without changing its code (license metadata,
    lint sweeps)."""
    message = commit["commit"]["message"]
    subject = message.split("\n", 1)[0]
    if re.search(r"(?i)\bcherry-pick", subject):
        return "cherry-pick"
    if re.search(r"(?i)\bbackport", subject):
        return "backport"
    if _UPSTREAM_RE.search(message):
        return "vendor"
    return None


def last_libwebrtc_change(commits: list[dict]) -> dict | None:
    """Date and kind of the newest real libwebrtc change (GitHub commit
    objects, newest first)."""
    for c in commits:
        kind = classify_libwebrtc_change(c)
        if kind:
            return {"date": c["commit"]["committer"]["date"][:10], "kind": kind}
    return None


def last_vendored_upstream(commits: list[dict]) -> str | None:
    """Full upstream SHA from the newest `Upstream commit:` footer."""
    for c in commits:
        m = _UPSTREAM_RE.search(c["commit"]["message"])
        if m:
            return m.group(1)
    return None


def update_in_progress(*, remaining: int | None, branch_only: int) -> bool:
    """Whether Nightly is still vendoring its target milestone.

    `remaining` counts upstream commits from Firefox's last vendored one to
    the branch-head, `branch_only` those that exist only on the branch-head.
    Once Firefox reaches the branch point only the latter can remain. None
    means Gitiles had more than a page left.
    """
    return remaining is None or remaining > branch_only


def _vs_chrome(milestone: int, chrome_stable: int) -> str:
    delta = milestone - chrome_stable
    if delta == 0:
        return "current"
    return f"{abs(delta)} {'ahead' if delta > 0 else 'behind'}"


def build_next_update(*, milestone: int, rel_target: int, fastforward_bug: int | None,
                      in_progress: bool, schedule: dict[int, tuple[str | None, str | None]],
                      trains: dict[int, tuple[str | None, str | None]],
                      lag: dict | None) -> dict:
    """Nightly's current update, the next few, and its lag behind upstream.

    `schedule` maps Chrome milestone -> (branch date, stable date); `trains`
    maps Firefox version -> (Nightly start, merge-to-Beta date). The current
    target is read from the tree; later ones are projected one train per
    milestone (both ship every two weeks), and a projection is dropped when
    the milestone branches too late to land in that train.
    """
    upcoming = []
    for k in range(1, UPCOMING + 1):
        m, f = milestone + k, rel_target + k
        branch, stable = schedule.get(m) or (None, None)
        nightly, merge = trains.get(f) or (None, None)
        if branch and merge and branch >= merge:
            f = nightly = merge = None
        upcoming.append({"milestone": m, "firefox": f, "chrome_branch": branch,
                         "chrome_stable": stable, "nightly_start": nightly,
                         "merge_day": merge})
    return {
        "current": {"milestone": milestone, "firefox": rel_target,
                    "fastforward_bug": fastforward_bug, "in_progress": in_progress,
                    "deadline": (trains.get(rel_target) or (None, None))[1]},
        "upcoming": upcoming,
        "lag": lag,
    }


def count_patches(entries: list[dict]) -> int:
    """Mozilla patch files in a moz-patch-stack directory listing."""
    return sum(1 for e in entries if e["name"].endswith(".patch"))


def month_samples(today: date, n: int) -> list[tuple[str, str]]:
    """(YYYY-MM, sample date) for the last `n` months, oldest first. Past
    months sample their last day; the current month samples today."""
    out, y, m = [], today.year, today.month
    for i in range(n):
        if i == 0:
            day = today
        else:
            first_next = date(y + (m == 12), m % 12 + 1, 1)
            day = date.fromordinal(first_next.toordinal() - 1)
        out.append((f"{y:04d}-{m:02d}", day.isoformat()))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


def plan_history(today: date, known: dict[str, dict]) -> tuple[dict[str, dict], list]:
    """Split the trend's months into points to reuse and (month, day) samples
    to fetch. A point is final only once sampled on its month's last day, so a
    mid-month sample is refetched after the month closes. The current month
    is left to the caller (it is Nightly's live count)."""
    samples = month_samples(today, HISTORY_MONTHS)
    reuse, fetch = {}, []
    for month, day in samples[:-1]:
        point = known.get(month)
        if point and (point.get("sampled") or "") >= day:
            reuse[month] = point
        else:
            fetch.append((month, day))
    return reuse, fetch


def project_view(view: dict) -> dict:
    """Keep only the whitelisted fields, nested ones included. Sections a
    payload lacks (files written before they existed) come back as None."""
    def pick(d, fields):
        return {k: d.get(k) for k in fields} if d else None

    def pick_all(items, fields):
        return [pick(x, fields) for x in items or [] if x]

    def row(r):
        out = pick(r, _ROW_FIELDS)
        out["last_change"] = pick(out["last_change"], _LAST_CHANGE_FIELDS)
        return out

    nxt, stack = view.get("next_update"), view.get("patch_stack")
    return {
        **{k: view.get(k) for k in _VIEW_FIELDS},
        "rows": [row(r) for r in view.get("rows") or [] if r],
        "next_update": nxt and {
            "as_of": nxt.get("as_of"),
            "current": pick(nxt.get("current"), _CURRENT_FIELDS),
            "upcoming": pick_all(nxt.get("upcoming"), _UPCOMING_FIELDS),
            "lag": pick(nxt.get("lag"), _LAG_FIELDS)},
        "patch_stack": stack and {
            "as_of": stack.get("as_of"),
            "releases": pick_all(stack.get("releases"), _STACK_RELEASE_FIELDS),
            "history": pick_all(stack.get("history"), _STACK_HISTORY_FIELDS)},
    }


def known_branch_dates(view: dict | None) -> dict[int, str]:
    """milestone -> branch date from a previous payload, to skip lookups."""
    return {r["milestone"]: r["branched"] for r in (view or {}).get("rows") or []
            if r.get("milestone") and r.get("branched")}


def known_history(view: dict | None) -> dict[str, dict]:
    """month -> trend point from a previous payload."""
    stack = (view or {}).get("patch_stack") or {}
    return {h["month"]: h for h in stack.get("history") or [] if h.get("month")}


# --- fetching -----------------------------------------------------------

def _decode_content(payload: dict) -> str:
    return base64.b64decode(payload["content"]).decode()


def _day(value: str | None) -> str | None:
    return (value or "")[:10] or None


def _not_scheduled(exc: Exception) -> bool:
    """Schedule services answer 4xx for dates they haven't planned yet."""
    return isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500


def _fetch_schedules(get_text, first: int, n: int) -> dict[int, tuple]:
    """Chrome milestone -> (branch date, stable date) for `n` milestones."""
    try:
        data = json.loads(get_text(CHROME_SCHEDULE_URL.format(first, n)))
    except Exception as exc:  # noqa: BLE001
        if _not_scheduled(exc):
            return {}
        raise
    return {m["mstone"]: (_day(m.get("branch_point")), _day(m.get("stable_date")))
            for m in data.get("mstones") or []}


def _fetch_train(get_text, version: int) -> tuple[str | None, str | None]:
    try:
        t = json.loads(get_text(FIREFOX_TRAIN_URL.format(version)))
    except Exception as exc:  # noqa: BLE001
        if _not_scheduled(exc):
            return None, None
        raise
    return _day(t.get("nightly_start")), _day(t.get("merge_day"))


def _fetch_gitiles_count(get_text, frm: str, to: str) -> int | None:
    log = parse_gitiles_json(get_text(GITILES_LOG_URL.format(frm, to)))
    return None if log.get("next") else len(log.get("log", []))


def _fetch_lag(get_text, last: str | None) -> dict | None:
    """How far Nightly's newest vendored commit trails upstream main, from
    the two commits' main positions (no log download)."""
    if last is None:
        return None
    head = parse_gitiles_json(get_text(GITILES_HEAD_URL))["log"][0]
    vendored = parse_gitiles_json(get_text(GITILES_COMMIT_URL.format(last)))
    h, v = main_position(head["message"]), main_position(vendored["message"])
    return {"last_vendored": gitiles_date(vendored["committer"]["time"]),
            "upstream_head": gitiles_date(head["committer"]["time"]),
            "behind": h - v if h is not None and v is not None else None}


def _fetch_next_update(get_text, *, env: str, milestone: int, in_progress: bool,
                       last: str | None) -> dict | None:
    rel_target, ff_bug = parse_rel_target(env)
    if not rel_target:
        return None
    return build_next_update(
        milestone=milestone, rel_target=rel_target, fastforward_bug=ff_bug,
        in_progress=in_progress,
        schedule=_fetch_schedules(get_text, milestone + 1, UPCOMING),
        trains={f: _fetch_train(get_text, f)
                for f in range(rel_target, rel_target + UPCOMING + 1)},
        lag=_fetch_lag(get_text, last))


def _fetch_patch_stack(github_get, releases: list[Release], *, today: date,
                       known: dict[str, dict]) -> dict:
    counts = [{"label": r.label, "count": count_patches(
        github_get(f"{_REPO}/contents/{_PATCH_STACK}?ref={r.branch}"))}
        for r in releases]
    history, fetch = plan_history(today, known)
    for month, day in fetch:
        commits = github_get(f"{_REPO}/commits?sha=main&path={_PATCH_STACK}"
                             f"&until={day}T23:59:59Z&per_page=1")
        if commits:
            history[month] = {"month": month, "sampled": day, "count": count_patches(
                github_get(f"{_REPO}/contents/{_PATCH_STACK}?ref={commits[0]['sha']}"))}
    nightly = next((c["count"] for c in counts if c["label"] == "Nightly"), None)
    current, _ = month_samples(today, 1)[0]
    if nightly is not None:
        history[current] = {"month": current, "sampled": today.isoformat(),
                            "count": nightly}
    return {"releases": counts, "history": [history[k] for k in sorted(history)]}


def _optional(key: str, build, previous: dict | None, today: date, on_error):
    """Build an optional section; on failure keep last week's copy (with its
    own as_of) rather than failing the whole fetch."""
    try:
        section = build()
    except Exception as exc:  # noqa: BLE001 — degrade this section only
        on_error(key, exc)
        return (previous or {}).get(key)
    return section and {**section, "as_of": today.isoformat()}


def collect_status(github_get, get_text, *, today: date, previous: dict | None = None,
                   on_error=lambda key, exc: None) -> dict:
    """Fetch and assemble the view.

    `github_get(path)` is the authenticated GitHub getter (paths under
    /repos/); `get_text(url)` is the unauthenticated one for every other
    host, so the token never leaves api.github.com. `previous` is last
    week's payload: settled values (branch dates, final trend points) are
    reused from it, and it backs the optional sections if they fail.
    """
    dates = known_branch_dates(previous)
    releases = supported_releases(json.loads(get_text(PRODUCT_DETAILS_URL)))
    chrome_stable = json.loads(get_text(CHROME_STABLE_URL))[0]["milestone"]
    rows, nightly = [], None
    for rel in releases:
        env = _decode_content(
            github_get(f"{_REPO}/contents/{_CONFIG_ENV}?ref={rel.branch}"))
        milestone, branch_head = parse_config_env(env)
        firefox = _decode_content(github_get(
            f"{_REPO}/contents/browser/config/version.txt?ref={rel.branch}")).strip()
        commits = github_get(f"{_REPO}/commits?sha={rel.branch}"
                             f"&path=third_party/libwebrtc&per_page=30")
        if milestone not in dates:
            dates[milestone] = (_fetch_schedules(get_text, milestone, 1)
                                .get(milestone, (None, None))[0])
        in_progress = False
        # Only Nightly vendors a milestone incrementally; release branches
        # only ever take cherry-picks once they have it.
        if rel.branch == "main":
            ref = f"refs/{branch_head}"
            last = last_vendored_upstream(commits)
            # Gitiles is optional: if it is down the table still refreshes,
            # with the update status unknown (None) for the week.
            try:
                in_progress = last is None or update_in_progress(
                    remaining=_fetch_gitiles_count(get_text, last, ref),
                    branch_only=_fetch_gitiles_count(get_text, "refs/heads/main", ref) or 0)
            except Exception as exc:  # noqa: BLE001
                on_error("in_progress", exc)
                in_progress = None
            nightly = dict(env=env, milestone=milestone, in_progress=in_progress,
                           last=last)
        rows.append({
            "label": rel.label, "firefox": firefox, "milestone": milestone,
            "branch_head": branch_head, "branched": dates[milestone],
            "vs_chrome": _vs_chrome(milestone, chrome_stable),
            "last_change": last_libwebrtc_change(commits),
            "in_progress": in_progress,
        })
    return project_view({
        "rows": rows, "chrome_stable": chrome_stable, "as_of": today.isoformat(),
        "next_update": _optional(
            "next_update", lambda: nightly and _fetch_next_update(get_text, **nightly),
            previous, today, on_error),
        "patch_stack": _optional(
            "patch_stack", lambda: _fetch_patch_stack(
                github_get, releases, today=today, known=known_history(previous)),
            previous, today, on_error),
    })
