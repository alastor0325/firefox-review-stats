"""Shared GitHub REST API helper: authenticated JSON GET with retry.

Both the commit-list path (`github_commits`) and the single-commit
file-list path (`commit_files`) hit api.github.com over plain urllib.
GitHub occasionally returns transient 5xx / 429 errors or times out
under load — a 504 Gateway Timeout once aborted an entire weekly
refresh — so every call retries those with exponential backoff instead
of failing the whole run.
"""

import json
import time
import urllib.error
import urllib.request


_MAX_ATTEMPTS = 5
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def is_retryable_error(exc: BaseException) -> bool:
    """True if `exc` is a transient error worth retrying.

    Retryable: GitHub 5xx / 429 responses, plus connection failures and
    socket timeouts (URLError / TimeoutError). Note HTTPError subclasses
    URLError, so it must be checked first — a 404 is *not* retryable.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_STATUS
    return isinstance(exc, (urllib.error.URLError, TimeoutError))


def backoff_seconds(attempt: int) -> float:
    """Exponential backoff for a 1-based attempt number: 1, 2, 4, 8 ..."""
    return float(2 ** (attempt - 1))


def get_json(
    url: str,
    *,
    token: str | None = None,
    timeout: float = 30,
    max_attempts: int = _MAX_ATTEMPTS,
):
    """Authenticated GET of `url`, returning the decoded JSON.

    Sends the GitHub `Accept` header and (if `token` is given) an
    `Authorization` header. Retries transient failures with exponential
    backoff; re-raises the last error once attempts are exhausted or the
    error is non-retryable.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as exc:  # noqa: BLE001 — re-raised below if fatal
            if attempt < max_attempts and is_retryable_error(exc):
                time.sleep(backoff_seconds(attempt))
                continue
            raise
