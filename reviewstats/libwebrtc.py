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
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from reviewstats.github_commits import _DEFAULT_REPO

PRODUCT_DETAILS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"
# The newest few Stable releases; their milestone may still be early stable.
CHROME_STABLE_URL = (
    "https://chromiumdash.appspot.com/fetch_releases"
    "?channel=Stable&platform=Windows&num=3"
)
CHROME_SCHEDULE_URL = "https://chromiumdash.appspot.com/fetch_milestone_schedule?mstone={}&n={}"
FIREFOX_TRAIN_URL = "https://whattrainisitnow.com/api/release/schedule/?version={}"
# Every shipped Firefox version and its release date.
FIREFOX_RELEASES_URL = "https://whattrainisitnow.com/api/firefox/releases/"
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
# Seconds the patch-stack section may spend; past it the section keeps last
# week's copy, so a slow raw-file host can't push the CI step (5 minutes)
# past its limit and lose the whole file.
STACK_BUDGET_S = 120
_now = time.monotonic
# A dropped patch whose title says it carried upstream code is "now in
# upstream": its change arrived with the update. A best guess from the title.
_ABSORBED_RE = re.compile(r"(?i)webrtc backport|cherry-pick upstream")

_REPO = f"/repos/{_DEFAULT_REPO}"
_CONFIG_ENV = "dom/media/webrtc/third_party_build/default_config_env"
_PATCH_STACK = "third_party/libwebrtc/moz-patch-stack"
_UPSTREAM_RE = re.compile(
    r"^Upstream commit: https://webrtc\.googlesource\.com/src/\+/([0-9a-f]{40})",
    re.MULTILINE,
)
# See unvendored_commits and fix_identity.
# Milestone tags only ([M155], [M120-LTS]); component tags like [Wayland] say
# what a fix touches and stay in its name.
_MILESTONE_TAG_RE = re.compile(r"^(\[M\d+[^\]]*\]\s*)+")
_REVERT_RE = re.compile(r'^(?:Revert(?:\^(\d+))?|(Reland))\s+"(.*)"$')
_CHERRY_RE = re.compile(r"\(cherry picked from commit ([0-9a-f]{40})\)")
_BRACKET_PREFIX_RE = re.compile(r"^(\[[^\]]*\]\s*)+")
# A main commit records its own position; a branch-head commit records the
# main position it branched from.
_MAIN_POSITION_RE = re.compile(
    r"^Cr-(?:Commit-Position|Branched-From):.*refs/heads/main@\{#(\d+)\}", re.MULTILINE)
NIGHTLY_REF = "main"  # Nightly ships main; there is no tag to read
_CHANNELS = (
    ("FIREFOX_NIGHTLY", "Nightly"),
    ("LATEST_FIREFOX_DEVEL_VERSION", "Beta"),
    ("LATEST_FIREFOX_VERSION", "Release"),
)
_VIEW_FIELDS = ("chrome_stable", "as_of")
_ROW_FIELDS = ("label", "firefox", "milestone", "branch_head", "branched",
               "vs_chrome", "patches", "last_change")
_LAST_CHANGE_FIELDS = ("date",)
_PLAN_FIELDS = ("milestone", "firefox", "chrome_branch", "chrome_stable",
                "nightly_start", "merge_day", "vendoring", "fastforward_bug",
                "in_progress")
_LAG_FIELDS = ("last_vendored", "upstream_head", "behind")
_STACK_HISTORY_FIELDS = ("month", "count", "sampled", "sha", "added", "dropped", "updates")
_STACK_ADDED_FIELDS = ("subject", "absorbed")
_STACK_DROPPED_FIELDS = ("subject", "absorbed", "update")
_STACK_UPDATE_FIELDS = ("milestone", "bug", "date")
RAW_URL = "https://raw.githubusercontent.com/{}/{}/{}/{}"
_UNVENDORED_FIELDS = ("commits", "as_of", "branch_commits", "last_merge")
_UNVENDORED_COMMIT_FIELDS = ("sha", "subject", "fix", "role")


@dataclass(frozen=True)
class Release:
    label: str
    ref: str      # git ref of the build users have
    firefox: str  # its version


def _major(version: str) -> int:
    return int(version.split(".")[0])


def release_tag(version: str) -> str:
    """The tag a shipped build was made from ("158.0b5" ->
    FIREFOX_158_0b5_RELEASE). Branch tips are not it: from merge day to
    release day the release branch already carries the next version."""
    return f"FIREFOX_{version.replace('.', '_')}_RELEASE"


def supported_releases(versions: dict) -> list[Release]:
    """Release channels, then every ESR in the feed, newest first. Nightly
    is main; the others are read at their shipped build's tag.

    ESRs are taken from any `FIREFOX_ESR*` key (FIREFOX_ESR, FIREFOX_ESR115,
    FIREFOX_ESR_NEXT, ...) and de-duplicated by major version.
    """
    out = [Release(label, NIGHTLY_REF if key == "FIREFOX_NIGHTLY" else release_tag(v), v)
           for key, label in _CHANNELS if (v := versions.get(key))]
    esrs = {}
    for k, v in versions.items():
        if k.startswith("FIREFOX_ESR") and v:
            esrs.setdefault(_major(v), v)
    out += [Release(f"ESR {m}", release_tag(esrs[m]), esrs[m].removesuffix("esr"))
            for m in sorted(esrs, reverse=True)]
    return out


def check_channels(versions: dict, calendar: dict, today: date) -> None:
    """Raise unless Nightly, Beta and Release are each one major apart and
    Release is the newest major the release calendar (version -> release
    date) has shipped by `today`."""
    try:
        n, b, r = (_major(versions[key]) for key in
                   ("FIREFOX_NIGHTLY", "LATEST_FIREFOX_DEVEL_VERSION", "LATEST_FIREFOX_VERSION"))
    except KeyError as exc:
        raise ValueError(f"product-details has no {exc.args[0]}") from None
    if (n - b, b - r) != (1, 1):
        raise ValueError(f"Nightly {n}, Beta {b}, Release {r}: "
                         "expected each one version apart")
    shipped = max((_major(v) for v, d in calendar.items() if d <= today.isoformat()),
                  default=None)
    if r != shipped:
        raise ValueError(f"product-details says Release {r}, "
                         f"but the release calendar says {shipped}")


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


def is_libwebrtc_change(commit: dict) -> bool:
    """Whether a commit touching third_party/libwebrtc changes its code — a
    vendor, cherry-pick or backport — rather than only its metadata
    (license declarations, lint sweeps)."""
    message = commit["commit"]["message"]
    subject = message.split("\n", 1)[0]
    return bool(re.search(r"(?i)\b(cherry-pick|backport)", subject)
                or _UPSTREAM_RE.search(message))


def last_libwebrtc_change(commits: list[dict]) -> dict | None:
    """Date of the newest real libwebrtc change (GitHub commit objects,
    newest first)."""
    for c in commits:
        if is_libwebrtc_change(c):
            return {"date": _day(c["commit"]["committer"]["date"])}
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


def full_stable(newest: int, stable_date: str | None, today: date) -> int:
    """Chrome's full-stable milestone. The release feed's newest "Stable"
    can still be in its early-stable rollout to a fraction of users; until
    its scheduled stable date the previous milestone is the one most users
    run."""
    if stable_date and date.fromisoformat(stable_date) > today:
        return newest - 1
    return newest


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


_UPDATE_COMMIT_RE = re.compile(r"^Bug (\d+) - updated default_config_env for v(\d+)")


def patch_subject(text: str) -> str | None:
    """A patch file's Subject header, unwrapped and without a [PATCH] tag."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not line.startswith("Subject:"):
            continue
        parts = [line[len("Subject:"):].strip()]
        for cont in lines[i + 1:]:
            if not cont.startswith((" ", "\t")):
                break
            parts.append(cont.strip())
        return re.sub(r"^\[PATCH[^\]]*\]\s*", "", " ".join(parts))
    return None


def diff_stack(before: list[str], after: list[str]) -> tuple[list[dict], list[dict]]:
    """Patches added and dropped between two snapshots' subject lists,
    compared as multisets (several patches can share a subject). A dropped
    patch is `absorbed` when its title says it carried upstream code."""
    left = list(after)
    dropped = []
    for s in before:
        if s in left:
            left.remove(s)
        else:
            dropped.append(s)
    return ([{"subject": s, "absorbed": False} for s in left],
            [{"subject": s, "absorbed": bool(_ABSORBED_RE.search(s))} for s in dropped])


def attribute_drops(dropped: list[dict], pushes: list[tuple[int, list[str] | None]]) -> list[dict]:
    """Credit each dropped patch to the upstream update whose own push
    removed it (`update` = milestone), one for one; anything else gets
    `update: None` — dropped outside an update, so worth checking for a
    backout. `pushes` is (milestone, subjects that push dropped); None means
    the push couldn't be read, so its month's drops are credited to it as a
    whole rather than raising a false alarm."""
    unread = next((m for m, subjects in pushes if subjects is None), None)
    pool = [(m, s) for m, subjects in pushes if subjects for s in subjects]
    out = []
    for d in dropped:
        match = next((i for i, (_, s) in enumerate(pool) if s == d["subject"]), None)
        if match is not None:
            out.append({**d, "update": pool.pop(match)[0]})
        else:
            out.append({**d, "update": unread})
    return out


def parse_update_commit(subject: str) -> tuple[int, int] | None:
    """(bug, milestone) for the commit a libwebrtc update push starts with
    ("Bug N - updated default_config_env for vNNN"), else None."""
    m = _UPDATE_COMMIT_RE.match(subject)
    return (int(m.group(1)), int(m.group(2))) if m else None


def patch_entries(entries: list[dict]) -> list[dict]:
    """The patch files in a moz-patch-stack directory listing."""
    return [e for e in entries if e["name"].endswith(".patch")]


def count_patches(entries: list[dict]) -> int:
    """Mozilla patch files in a moz-patch-stack directory listing."""
    return len(patch_entries(entries))


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


def plan_history(today: date, known: dict[str, dict]) -> dict[str, dict]:
    """The closed months whose points are final and can be reused: sampled on
    the month's last day, with change lists (see has_change_lists). A
    mid-month sample, or an older-format point, is refetched."""
    samples = month_samples(today, HISTORY_MONTHS + 1)  # +1: the first month's baseline
    return {month: known[month] for month, day in samples[:-1]
            if month in known and (known[month].get("sampled") or "") >= day
            and has_change_lists(known[month])}


def has_change_lists(point: dict) -> bool:
    """Recorded with added/dropped lists, each drop credited (or not) to an
    update push — older points lack these and are refetched."""
    return point.get("added") is not None and all(
        "update" in d for d in point.get("dropped") or [])


def fix_identity(subject: str) -> tuple[str, str]:
    """(fix, role) for an upstream branch commit: the same fix lands on each
    milestone branch under its own SHA and [Mxxx] tag, and may be reverted and
    relanded. `fix` is the subject without those tags or the Revert/Reland
    wrapper; `role` is landed, reverted or relanded (Revert^N alternates)."""
    stripped = _MILESTONE_TAG_RE.sub("", subject).strip()
    m = _REVERT_RE.match(stripped)
    if not m:
        return stripped, "landed"
    inner = _MILESTONE_TAG_RE.sub("", m.group(3)).strip()
    if m.group(2):
        return inner, "relanded"
    return inner, "reverted" if int(m.group(1) or 1) % 2 else "relanded"


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
    can't hide a missing fix. Matching is heuristic, so some results are false
    positives and some fixes are skipped on purpose (Chrome-only code). Each
    result carries its `fix_identity`, the one definition of "same fix" the
    page groups by.
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
        fix, role = fix_identity(subject)
        out.append({"sha": c["commit"], "subject": subject, "fix": fix, "role": role})
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
        out["unvendored"] = u and {**pick(u, _UNVENDORED_FIELDS), "commits": [
            commit(c) for c in pick_all(u.get("commits"), _UNVENDORED_COMMIT_FIELDS)]}
        return out

    def history_point(h):
        for key, fields in (("added", _STACK_ADDED_FIELDS), ("dropped", _STACK_DROPPED_FIELDS),
                            ("updates", _STACK_UPDATE_FIELDS)):
            if h[key] is not None:
                h[key] = pick_all(h[key], fields)
        return h

    def commit(c):
        # Files written before fix_identity carry only the subject.
        if c["fix"] is None and c["subject"]:
            c["fix"], c["role"] = fix_identity(c["subject"])
        return c

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
            "history": [history_point(h) for h in pick_all(stack.get("history"),
                                                          _STACK_HISTORY_FIELDS)]},
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


def _fetch_unvendored(github_get, get_text, *, ref: str, branch_head: str,
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
        batch = github_get(f"{_REPO}/commits?sha={ref}&path=third_party/libwebrtc"
                           f"&since={branched}T00:00:00Z&per_page=100&page={page}")
        firefox += batch
        if len(batch) < 100:
            break
    else:
        if entries:
            raise RuntimeError(f"{ref} history exceeds {MAX_PAGES} pages")
    return {"commits": unvendored_commits(entries, firefox), "as_of": today.isoformat(),
            # Gitiles lists newest first.
            "branch_commits": len(entries),
            "last_merge": gitiles_date(entries[0]["committer"]["time"]) if entries else None}


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


def _fetch_stack_subjects(github_get, get_text, sha: str, blobs: dict) -> list[str]:
    """The patch Subjects in moz-patch-stack at `sha`, in stack order. Files
    are read from raw.githubusercontent.com in parallel; `blobs` maps git
    blob SHA -> subject across the run, so a file version shared by several
    snapshots is read once."""
    entries = patch_entries(github_get(f"{_REPO}/contents/{_PATCH_STACK}?ref={sha}"))
    todo = [e for e in entries if e.get("sha") not in blobs]
    url = lambda e: RAW_URL.format(_DEFAULT_REPO, sha, _PATCH_STACK, e["name"])
    with ThreadPoolExecutor(max_workers=16) as pool:
        for e, text in zip(todo, pool.map(lambda e: get_text(url(e)), todo)):
            blobs[e.get("sha") or e["name"]] = patch_subject(text) or e["name"]
    return [blobs[e.get("sha") or e["name"]] for e in entries]


def _fetch_updates(github_get, since: str) -> dict[str, list[dict]]:
    """month -> libwebrtc update pushes that started that month on main.
    Each carries the SHA just before the push (`_before`, not published)."""
    commits = []
    for page in range(1, MAX_PAGES + 1):
        batch = github_get(f"{_REPO}/commits?sha=main&path={_CONFIG_ENV}"
                           f"&since={since}T00:00:00Z&per_page=100&page={page}")
        commits += batch
        if len(batch) < 100:
            break
    else:
        raise RuntimeError(f"default_config_env history exceeds {MAX_PAGES} pages")
    out = {}
    for c in commits:
        parsed = parse_update_commit(c["commit"]["message"].split("\n", 1)[0])
        if parsed:
            day = _day(c["commit"]["committer"]["date"])
            out.setdefault(day[:7], []).append(
                {"milestone": parsed[1], "bug": parsed[0], "date": day,
                 "_before": (c.get("parents") or [{}])[0].get("sha")})
    return {m: sorted(u, key=lambda x: x["date"]) for m, u in out.items()}


def _push_after(github_get, update: dict) -> str | None:
    """The last moz-patch-stack commit of an update push: the newest commit
    in the few days after it started that carries the update's bug."""
    start = date.fromisoformat(update["date"])
    commits = github_get(f"{_REPO}/commits?sha=main&path={_PATCH_STACK}"
                         f"&since={start}T00:00:00Z&until={start + timedelta(days=3)}T00:00:00Z"
                         f"&per_page=100")
    return next((c["sha"] for c in commits
                 if c["commit"]["message"].startswith(f"Bug {update['bug']} ")), None)


def _fetch_patch_stack(github_get, get_text, *, today: date,
                       known: dict[str, dict]) -> dict:
    """Nightly's month-end patch stacks: count, what was added and dropped
    since the previous month end — each drop credited to the update push that
    removed it, if any — and which updates landed. Final closed months, and
    any month whose snapshot hasn't moved, are reused."""
    started = _now()

    def within_budget():
        if _now() - started > STACK_BUDGET_S:
            raise RuntimeError(f"patch stack over its {STACK_BUDGET_S}s budget")

    samples = month_samples(today, HISTORY_MONTHS + 1)
    reuse = plan_history(today, known)
    shas, subjects, blobs = {}, {}, {}
    for month, day in samples:
        if month in reuse:
            shas[month] = reuse[month]["sha"]
            continue
        commits = github_get(f"{_REPO}/commits?sha=main&path={_PATCH_STACK}"
                             f"&until={day}T23:59:59Z&per_page=1")
        if commits:
            shas[month] = commits[0]["sha"]
            old = known.get(month)
            if old and old.get("sha") == shas[month] and has_change_lists(old):
                reuse[month] = {**old, "sampled": day}   # snapshot unchanged

    def stack(sha):
        if sha not in subjects:
            within_budget()
            subjects[sha] = _fetch_stack_subjects(github_get, get_text, sha, blobs)
        return subjects[sha]

    def push_drops(update):
        after = _push_after(github_get, update)
        if not (after and update.get("_before")):
            return None
        return [d["subject"] for d in diff_stack(stack(update["_before"]), stack(after))[1]]

    updates = _fetch_updates(github_get, samples[1][0] + "-01")
    history = []
    for (prev, _), (month, day) in zip(samples, samples[1:]):
        if month in reuse:
            history.append(reuse[month])
            continue
        if month not in shas:
            continue
        added = dropped = None
        current = stack(shas[month])
        month_updates = updates.get(month, [])
        if prev in shas:
            added, dropped = diff_stack(stack(shas[prev]), current)
            if dropped:
                dropped = attribute_drops(
                    dropped, [(u["milestone"], push_drops(u)) for u in month_updates])
        history.append({"month": month, "sampled": day, "sha": shas[month],
                        "count": len(current), "added": added, "dropped": dropped,
                        "updates": month_updates})
    return {"history": history}


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
    versions = json.loads(get_text(PRODUCT_DETAILS_URL))
    check_channels(versions, json.loads(get_text(FIREFOX_RELEASES_URL)), today)
    releases = supported_releases(versions)
    def scheduled(milestone: int) -> tuple:
        """(branch, stable) dates, or (None, None) if chromiumdash fails; the
        table still refreshes, just without them."""
        try:
            return _fetch_schedules(get_text, milestone, 1).get(milestone, (None, None))
        except Exception as exc:  # noqa: BLE001
            on_error("chrome stable", exc)
            return None, None

    newest = max(r["milestone"] for r in json.loads(get_text(CHROME_STABLE_URL)))
    chrome_stable = full_stable(newest, scheduled(newest)[1], today)
    rows, nightly = [], None
    for rel in releases:
        env = _decode_content(
            github_get(f"{_REPO}/contents/{_CONFIG_ENV}?ref={rel.ref}"))
        milestone, branch_head = parse_config_env(env)
        commits = github_get(f"{_REPO}/commits?sha={rel.ref}"
                             f"&path=third_party/libwebrtc&per_page=30")
        if milestone not in dates:
            dates[milestone] = scheduled(milestone)[0]
        patches = count_patches(
            github_get(f"{_REPO}/contents/{_PATCH_STACK}?ref={rel.ref}"))
        # Only Nightly vendors a milestone incrementally; release branches
        # only ever take cherry-picks once they have it.
        if rel.ref == NIGHTLY_REF:
            head_ref = f"refs/{branch_head}"
            last = last_vendored_upstream(commits)
            # Gitiles is optional: if it is down the table still refreshes,
            # with the update status unknown (None) for the week.
            try:
                in_progress = last is None or update_in_progress(
                    remaining=_fetch_gitiles_count(get_text, last, head_ref),
                    branch_only=_fetch_gitiles_count(get_text, "refs/heads/main", head_ref) or 0)
            except Exception as exc:  # noqa: BLE001
                on_error("in_progress", exc)
                in_progress = None
            nightly = dict(env=env, milestone=milestone, in_progress=in_progress,
                           last=last)
        try:
            unvendored = _fetch_unvendored(github_get, get_text, ref=rel.ref,
                                           branch_head=branch_head,
                                           branched=dates[milestone], today=today)
        except Exception as exc:  # noqa: BLE001 — keep last week's list
            on_error("missing fixes", exc)
            unvendored = last_unvendored.get((rel.label, branch_head))
        rows.append({
            "label": rel.label, "firefox": rel.firefox, "milestone": milestone,
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
                github_get, get_text, today=today, known=known_history(previous)),
            previous, today, on_error),
    })
