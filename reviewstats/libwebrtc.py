"""Which libwebrtc each supported Firefox release ships, which upstream
branch-head commits it hasn't vendored, what the next update is, and how big
the Mozilla patch stack is — the WebRTC page's libwebrtc view, written by
fetch_libwebrtc_status.py.

The unvendored commits are mostly fixes Chrome merged to its release
branches, many of them security fixes. Publishing them was a deliberate
decision by the dashboard's owner (the data is all public upstream and in
Firefox's history); it is the field to reconsider first if this page ever
needs to say less. `project_view` is the one whitelist every payload passes
through, on write and on read.

The Releases table (with each release's patch count) is the core and fails the
fetch if it can't be built; the patch counts are core because they come from
the same GitHub API as the rest of it. Each release's unvendored list, the
milestone plan and the patch-stack trend are optional: each falls back to last
week's copy so one flaky host (chromiumdash, whattrainisitnow, Gitiles) can't
freeze the rest.

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
# A `next` key means the log ran past one page.
GITILES_LOG_URL = "https://webrtc.googlesource.com/src/+log/{}..{}?format=JSON&n=200"
GITILES_HEAD_URL = "https://webrtc.googlesource.com/src/+log/refs/heads/main?format=JSON&n=1"
GITILES_COMMIT_URL = "https://webrtc.googlesource.com/src/+/{}?format=JSON"
PLAN_ROWS = 4  # the update in flight plus the next three milestones
HISTORY_MONTHS = 12
# Firefox history pages per release; one milestone's libwebrtc commits on a
# branch measure at most ~4 pages, so reaching this means something is off.
MAX_PAGES = 10
# A subject-only match needs this many words: vendoring commits embed whole
# upstream messages, so "Fix crash" would match an unrelated line.
MIN_SUBJECT_WORDS = 4

_REPO = f"/repos/{_DEFAULT_REPO}"
_CONFIG_ENV = "dom/media/webrtc/third_party_build/default_config_env"
_PATCH_STACK = "third_party/libwebrtc/moz-patch-stack"
_UPSTREAM_RE = re.compile(
    r"^Upstream commit: https://webrtc\.googlesource\.com/src/\+/([0-9a-f]{40})",
    re.MULTILINE,
)
# See unvendored_commits.
_CHERRY_RE = re.compile(r"\(cherry picked from commit ([0-9a-f]{40})\)")
_BRACKET_PREFIX_RE = re.compile(r"^(\[[^\]]*\]\s*)+")
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
               "vs_chrome", "patches", "last_change")
_LAST_CHANGE_FIELDS = ("date", "kind")
_PLAN_FIELDS = ("milestone", "firefox", "chrome_branch", "chrome_stable",
                "nightly_start", "merge_day", "vendoring", "fastforward_bug",
                "in_progress")
_LAG_FIELDS = ("last_vendored", "upstream_head", "behind")
_STACK_HISTORY_FIELDS = ("month", "count", "sampled")
_UNVENDORED_FIELDS = ("count", "commits", "as_of")
_UNVENDORED_COMMIT_FIELDS = ("sha", "subject")


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


def build_plan(*, milestone: int, rel_target: int, fastforward_bug: int | None,
               in_progress: bool | None,
               schedule: dict[int, tuple[str | None, str | None]],
               trains: dict[int, tuple[str | None, str | None]],
               lag: dict | None) -> dict:
    """Nightly's milestone plan — the update in flight, then the next few —
    and its lag behind upstream.

    `schedule` maps Chrome milestone -> (branch date, stable date); `trains`
    maps Firefox version -> (Nightly start, merge-to-Beta date). The row
    being vendored is marked `vendoring` and carries its own status; its
    target is read from the tree. Later targets are projected one train per
    milestone (both ship every two weeks), and a projection is dropped when
    the milestone branches too late to land in that train.
    """
    rows = []
    for k in range(PLAN_ROWS):
        m, f = milestone + k, rel_target + k
        branch, stable = schedule.get(m) or (None, None)
        nightly, merge = trains.get(f) or (None, None)
        vendoring = k == 0
        if not vendoring and branch and merge and branch >= merge:
            f = nightly = merge = None
        rows.append({"milestone": m, "firefox": f, "chrome_branch": branch,
                     "chrome_stable": stable, "nightly_start": nightly,
                     "merge_day": merge, "vendoring": vendoring,
                     "fastforward_bug": fastforward_bug if vendoring else None,
                     "in_progress": in_progress if vendoring else None})
    return {"rows": rows, "lag": lag}


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


def unvendored_commits(branch_log: list[dict], firefox_commits: list[dict]) -> list[dict]:
    """Upstream branch-head commits a Firefox branch hasn't vendored — the
    logic of check_missing_branch_head_commits.py.

    `branch_log` is Gitiles' main..branch-head log (entries with `commit` and
    `message`); `firefox_commits` are GitHub commit objects touching
    third_party/libwebrtc on that branch. A commit counts as vendored if its
    SHA is in an `Upstream commit:` footer or a `(cherry picked from commit)`
    line, or if its subject, without [M153]-style prefixes, appears in any
    of those messages (manual backports that dropped the SHA). Beyond the
    script, the main commit a branch-head commit was cherry-picked from also
    counts, since Firefox sometimes takes the original rather than the copy,
    and a subject-only match needs MIN_SUBJECT_WORDS words so a generic one
    can't hide a missing fix. The result is a list to triage, not a verdict:
    some commits are deliberately not taken (Chrome-only code paths).
    """
    messages = [c["commit"]["message"] for c in firefox_commits]
    vendored = set()
    for m in messages:
        vendored.update(_UPSTREAM_RE.findall(m))
        vendored.update(_CHERRY_RE.findall(m))
    text = "\n".join(messages)
    out = []
    for c in branch_log:
        subject = c["message"].split("\n", 1)[0]
        stripped = _BRACKET_PREFIX_RE.sub("", subject).strip()
        original = _CHERRY_RE.findall(c["message"])
        by_subject = len(stripped.split()) >= MIN_SUBJECT_WORDS and stripped in text
        if c["commit"] in vendored or vendored.intersection(original) or by_subject:
            continue
        out.append({"sha": c["commit"], "subject": subject})
    return out


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
        u = r.get("unvendored")
        out["unvendored"] = u and {**pick(u, _UNVENDORED_FIELDS), "commits": pick_all(
            u.get("commits"), _UNVENDORED_COMMIT_FIELDS)}
        return out

    plan, stack = view.get("plan"), view.get("patch_stack")
    return {
        **{k: view.get(k) for k in _VIEW_FIELDS},
        "rows": [row(r) for r in view.get("rows") or [] if r],
        "plan": plan and {
            "as_of": plan.get("as_of"),
            "rows": pick_all(plan.get("rows"), _PLAN_FIELDS),
            "lag": pick(plan.get("lag"), _LAG_FIELDS)},
        "patch_stack": stack and {
            "as_of": stack.get("as_of"),
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


def _fetch_gitiles_log(get_text, frm: str, to: str) -> dict:
    return parse_gitiles_json(get_text(GITILES_LOG_URL.format(frm, to)))


def _fetch_gitiles_count(get_text, frm: str, to: str) -> int | None:
    log = _fetch_gitiles_log(get_text, frm, to)
    return None if log.get("next") else len(log.get("log", []))


def _fetch_unvendored(github_get, get_text, *, branch: str, branch_head: str,
                      branched: str | None, today: date) -> dict:
    """A release's unvendored upstream branch-head commits.

    Firefox history is read only from the milestone's branch date on: a
    branch-head commit (or the main commit it copies) can't have been
    vendored before the branch existed. Anything that would leave the input
    incomplete raises, so the caller falls back to last week's list rather
    than publishing a count from partial history.
    """
    if not branched:
        raise RuntimeError(f"no branch date for {branch_head}")
    log = _fetch_gitiles_log(get_text, "refs/heads/main", f"refs/{branch_head}")
    if log.get("next"):
        raise RuntimeError(f"{branch_head} has more branch-only commits than one page")
    entries = log.get("log", [])
    firefox = []
    for page in range(1, MAX_PAGES + 1) if entries else ():
        batch = github_get(f"{_REPO}/commits?sha={branch}&path=third_party/libwebrtc"
                           f"&since={branched}T00:00:00Z&per_page=100&page={page}")
        firefox += batch
        if len(batch) < 100:
            break
    else:
        if entries:
            raise RuntimeError(f"{branch} history exceeds {MAX_PAGES} pages")
    missing = unvendored_commits(entries, firefox)
    return {"count": len(missing), "commits": missing, "as_of": today.isoformat()}


def _guarded(get_text, on_error):
    """`get_text` for one run: identical URLs are fetched once, and a host
    that fails (other than "not scheduled yet" 4xx answers) is not asked
    again, so one hanging host costs one timeout instead of one per row."""
    cache, down = {}, set()

    def get(url):
        host = url.split("/")[2]
        if url in cache:
            return cache[url]
        if host in down:
            raise RuntimeError(f"{host} already failed this run")
        try:
            cache[url] = get_text(url)
        except Exception as exc:  # noqa: BLE001
            if not _not_scheduled(exc):
                down.add(host)
            raise
        return cache[url]
    return get


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


def _fetch_plan(get_text, *, env: str, milestone: int,
                in_progress: bool | None, last: str | None) -> dict | None:
    rel_target, ff_bug = parse_rel_target(env)
    if not rel_target:
        return None
    return build_plan(
        milestone=milestone, rel_target=rel_target, fastforward_bug=ff_bug,
        in_progress=in_progress,
        schedule=_fetch_schedules(get_text, milestone, PLAN_ROWS),
        trains={f: _fetch_train(get_text, f)
                for f in range(rel_target, rel_target + PLAN_ROWS)},
        lag=_fetch_lag(get_text, last))


def _fetch_patch_stack(github_get, *, nightly_count: int | None, today: date,
                       known: dict[str, dict]) -> dict:
    """Nightly's month-end patch counts. This month is the live count the
    Releases table already fetched."""
    history, fetch = plan_history(today, known)
    for month, day in fetch:
        commits = github_get(f"{_REPO}/commits?sha=main&path={_PATCH_STACK}"
                             f"&until={day}T23:59:59Z&per_page=1")
        if commits:
            history[month] = {"month": month, "sampled": day, "count": count_patches(
                github_get(f"{_REPO}/contents/{_PATCH_STACK}?ref={commits[0]['sha']}"))}
    if nightly_count is not None:
        current, _ = month_samples(today, 1)[0]
        history[current] = {"month": current, "sampled": today.isoformat(),
                            "count": nightly_count}
    return {"history": [history[k] for k in sorted(history)]}


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
    get_text = _guarded(get_text, on_error)
    dates = known_branch_dates(previous)
    # Last week's list is reusable only for the same branch-head: on a merge
    # week a release moves milestone and the old list no longer applies.
    last_unvendored = {(r.get("label"), r.get("branch_head")): r.get("unvendored")
                       for r in (previous or {}).get("rows") or []}
    releases = supported_releases(json.loads(get_text(PRODUCT_DETAILS_URL)))
    chrome_stable = json.loads(get_text(CHROME_STABLE_URL))[0]["milestone"]
    rows, nightly, nightly_count = [], None, None
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
        patches = count_patches(
            github_get(f"{_REPO}/contents/{_PATCH_STACK}?ref={rel.branch}"))
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
            nightly_count = patches
        try:
            unvendored = _fetch_unvendored(github_get, get_text, branch=rel.branch,
                                           branch_head=branch_head,
                                           branched=dates[milestone], today=today)
        except Exception as exc:  # noqa: BLE001 — keep last week's list
            on_error("unvendored", exc)
            unvendored = last_unvendored.get((rel.label, branch_head))
        rows.append({
            "label": rel.label, "firefox": firefox, "milestone": milestone,
            "branch_head": branch_head, "branched": dates[milestone],
            "vs_chrome": _vs_chrome(milestone, chrome_stable),
            "patches": patches,
            "last_change": last_libwebrtc_change(commits),
            "unvendored": unvendored,
        })
    return project_view({
        "rows": rows, "chrome_stable": chrome_stable, "as_of": today.isoformat(),
        "plan": _optional(
            "plan", lambda: nightly and _fetch_plan(get_text, **nightly),
            previous, today, on_error),
        "patch_stack": _optional(
            "patch_stack", lambda: _fetch_patch_stack(
                github_get, nightly_count=nightly_count, today=today,
                known=known_history(previous)),
            previous, today, on_error),
    })
