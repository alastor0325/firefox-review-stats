"""Fetch commits from GitHub's REST API — no local clone needed.

Mozilla maintains a public mirror of mozilla-central at
github.com/mozilla-firefox/firefox. The `/commits` endpoint returns
each commit's SHA, author name, date, and full message body (with the
`Differential Revision:` line we need) — everything `git log` gave us
when we used a local checkout.

Authentication uses the gh CLI's stored token (`gh auth token`).
Anonymous calls would also work for ~14 calls per refresh (the public
limit is 60/hour), but using the auth pool gives us 5000/hour
headroom for free.
"""

import json
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Iterator

from reviewstats.git_log import Commit
from reviewstats.parse import (
    extract_differential_revision,
    is_excluded_author,
    parse_reviewers,
    should_skip_commit,
)


_API = "https://api.github.com"
_PER_PAGE = 100
_DEFAULT_REPO = "mozilla-firefox/firefox"


def _get_auth_token() -> str | None:
    # GH Actions exposes the workflow token as GITHUB_TOKEN; the gh CLI
    # honours GH_TOKEN too. Either env var works.
    env_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token
    try:
        out = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() or None
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def _iter_pages(
    repo: str, path: str, since_iso: str, token: str | None
) -> Iterator[list[dict]]:
    page = 1
    while True:
        params = urllib.parse.urlencode({
            "path": path,
            "since": since_iso,
            "per_page": _PER_PAGE,
            "page": page,
        })
        url = f"{_API}/repos/{repo}/commits?{params}"
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r) if hasattr(r, "load") else json.loads(r.read().decode())
        if not payload:
            break
        yield payload
        if len(payload) < _PER_PAGE:
            break
        page += 1


def _shas_for_path(
    repo: str, path: str, since_iso: str, token: str | None
) -> set[str]:
    out: set[str] = set()
    for page in _iter_pages(repo, path, since_iso, token):
        out.update(c["sha"] for c in page)
    return out


def _api_commit_to_commit(api: dict) -> Commit:
    msg = api["commit"]["message"]
    subject, _, body = msg.partition("\n")
    return Commit(
        sha=api["sha"],
        date=datetime.fromisoformat(
            api["commit"]["author"]["date"].replace("Z", "+00:00")
        ),
        author=api["commit"]["author"]["name"],
        subject=subject,
        reviewers=parse_reviewers(subject),
        differential_revision=extract_differential_revision(body),
    )


def fetch_commits(
    *,
    repo: str = _DEFAULT_REPO,
    path: str,
    since: str,
    exclude_paths: tuple[str, ...] = (),
) -> list[Commit]:
    """Return commits touching `path` since `since`, excluding any
    that also touch one of `exclude_paths`.

    `since` must already be a GitHub-acceptable ISO 8601 timestamp
    (e.g. "2025-11-15T00:00:00Z"). The caller converts "6 months ago"
    style strings if needed.

    Applies the same skip rules as the git-log path: Lando-format /
    merge / Revert subjects, Lando-authored commits.
    """
    token = _get_auth_token()
    raw_commits: list[dict] = []
    for page in _iter_pages(repo, path, since, token):
        raw_commits.extend(page)
    excluded_shas: set[str] = set()
    for ex in exclude_paths:
        excluded_shas |= _shas_for_path(repo, ex, since, token)

    out: list[Commit] = []
    for api in raw_commits:
        if api["sha"] in excluded_shas:
            continue
        subject = api["commit"]["message"].partition("\n")[0]
        author = api["commit"]["author"]["name"]
        if should_skip_commit(subject) or is_excluded_author(author):
            continue
        out.append(_api_commit_to_commit(api))
    return out
