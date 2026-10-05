"""Which libwebrtc each supported Firefox release ships — the WebRTC page's
version table, written by fetch_libwebrtc_status.py.

Versions only. The in-tree check_missing_branch_head_commits.py also lists
upstream branch-head commits a release has not vendored, but those are mostly
security fixes Chrome merged to its release branches, so on this public page
that list would be an index of unpatched bugs in shipping Firefox. Nothing
here keeps upstream commits or bug references, and `project_view` is the one
whitelist every payload passes through, on write and on read.

Everything except `collect_status` is pure.
"""

import base64
import json
import re
from dataclasses import dataclass
from datetime import date

from reviewstats.github_commits import _DEFAULT_REPO

PRODUCT_DETAILS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"
CHROME_STABLE_URL = (
    "https://chromiumdash.appspot.com/fetch_releases"
    "?channel=Stable&platform=Windows&num=1"
)
CHROME_SCHEDULE_URL = "https://chromiumdash.appspot.com/fetch_milestone_schedule?mstone={}"
# Only counts are read, and an overflowing page already means "in progress".
GITILES_LOG_URL = "https://webrtc.googlesource.com/src/+log/{}..{}?format=JSON&n=200"

_REPO = f"/repos/{_DEFAULT_REPO}"
_CONFIG_ENV = "dom/media/webrtc/third_party_build/default_config_env"
_UPSTREAM_RE = re.compile(
    r"^Upstream commit: https://webrtc\.googlesource\.com/src/\+/([0-9a-f]{40})",
    re.MULTILINE,
)
_CHANNELS = (
    ("FIREFOX_NIGHTLY", "Nightly", "main"),
    ("LATEST_FIREFOX_DEVEL_VERSION", "Beta", "beta"),
    ("LATEST_FIREFOX_VERSION", "Release", "release"),
)
_VIEW_FIELDS = ("chrome_stable", "as_of")
_ROW_FIELDS = ("label", "firefox", "milestone", "branch_head", "branched",
               "age", "vs_chrome", "in_progress", "last_change")
_LAST_CHANGE_FIELDS = ("date", "kind")


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


def parse_config_env(text: str) -> tuple[int | None, str | None]:
    """(milestone, branch-head) from a branch's default_config_env."""
    milestone = branch_head = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        if "MOZ_NEXT_LIBWEBRTC_MILESTONE=" in line:
            milestone = int(line.split("=", 1)[1].strip().strip('"'))
        elif "MOZ_TARGET_UPSTREAM_BRANCH_HEAD=" in line:
            branch_head = line.split("=", 1)[1].strip().strip('"')
    return milestone, branch_head


def parse_gitiles_json(text: str) -> dict:
    """Gitiles prefixes JSON with `)]}'` to defeat XSSI; drop that line."""
    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1]
    return json.loads(text)


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


def age_label(branched: date, today: date) -> str:
    """Weeks under 8 weeks, months after."""
    days = (today - branched).days
    if days < 56:
        return f"{round(days / 7)} wk"
    return f"{round(days / 30.44)} mo"


def _vs_chrome(milestone: int, chrome_stable: int) -> str:
    delta = milestone - chrome_stable
    if delta == 0:
        return "current"
    return f"{abs(delta)} {'ahead' if delta > 0 else 'behind'}"


def project_view(view: dict) -> dict:
    """Keep only the whitelisted fields, nested ones included."""
    def row(r):
        out = {k: r.get(k) for k in _ROW_FIELDS}
        if out["last_change"]:
            out["last_change"] = {k: out["last_change"].get(k)
                                  for k in _LAST_CHANGE_FIELDS}
        return out
    return {**{k: view.get(k) for k in _VIEW_FIELDS},
            "rows": [row(r) for r in view.get("rows") or []]}


def build_view(rows: list[dict], *, chrome_stable: int, today: date) -> dict:
    """The page payload, with the age and Chrome-relation labels derived."""
    for r in rows:
        r["age"] = (age_label(date.fromisoformat(r["branched"]), today)
                    if r["branched"] else None)
        r["vs_chrome"] = _vs_chrome(r["milestone"], chrome_stable)
    return project_view({"rows": rows, "chrome_stable": chrome_stable,
                         "as_of": today.isoformat()})


def known_branch_dates(view: dict | None) -> dict[int, str]:
    """milestone -> branch date from a previous payload, to skip lookups."""
    return {r["milestone"]: r["branched"] for r in (view or {}).get("rows") or []
            if r.get("milestone") and r.get("branched")}


def _decode_content(payload: dict) -> str:
    return base64.b64decode(payload["content"]).decode()


def _gitiles_count(get_text, frm: str, to: str) -> int | None:
    log = parse_gitiles_json(get_text(GITILES_LOG_URL.format(frm, to)))
    return None if log.get("next") else len(log.get("log", []))


def collect_status(github_get, get_text, *, today: date,
                   known_branch_dates: dict[int, str] | None = None) -> dict:
    """Fetch and assemble the view.

    `github_get(path)` is the authenticated GitHub getter (paths under
    /repos/); `get_text(url)` is the unauthenticated one for every other
    host, so the token never leaves api.github.com. `known_branch_dates`
    (milestone -> date) skips chromiumdash for milestones already seen.
    """
    dates = dict(known_branch_dates or {})
    releases = supported_releases(json.loads(get_text(PRODUCT_DETAILS_URL)))
    chrome_stable = json.loads(get_text(CHROME_STABLE_URL))[0]["milestone"]
    rows = []
    for rel in releases:
        milestone, branch_head = parse_config_env(_decode_content(
            github_get(f"{_REPO}/contents/{_CONFIG_ENV}?ref={rel.branch}")))
        firefox = _decode_content(github_get(
            f"{_REPO}/contents/browser/config/version.txt?ref={rel.branch}")).strip()
        commits = github_get(f"{_REPO}/commits?sha={rel.branch}"
                             f"&path=third_party/libwebrtc&per_page=30")
        if milestone not in dates:
            schedule = json.loads(get_text(CHROME_SCHEDULE_URL.format(milestone)))
            dates[milestone] = ((schedule.get("mstones") or [{}])[0]
                                .get("branch_point") or "")[:10] or None

        in_progress = False
        # Only Nightly vendors a milestone incrementally; release branches
        # only ever take cherry-picks once they have it.
        if rel.branch == "main":
            ref = f"refs/{branch_head}"
            last = last_vendored_upstream(commits)
            in_progress = last is None or update_in_progress(
                remaining=_gitiles_count(get_text, last, ref),
                branch_only=_gitiles_count(get_text, "refs/heads/main", ref) or 0,
            )
        rows.append({
            "label": rel.label, "firefox": firefox, "milestone": milestone,
            "branch_head": branch_head, "branched": dates[milestone],
            "last_change": last_libwebrtc_change(commits),
            "in_progress": in_progress,
        })
    return build_view(rows, chrome_stable=chrome_stable, today=today)
