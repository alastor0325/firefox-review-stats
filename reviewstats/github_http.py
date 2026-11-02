"""Shared retrying HTTP GET over plain urllib.

`get_text` is the helper for every host (GitHub, Gitiles, chromiumdash,
Perfherder, Treeherder, Bugzilla); `get_json` adds GitHub's Accept header
and token. Upstreams occasionally return transient 5xx / 429 errors, time
out, or drop the connection under load — a 504 once aborted an entire
weekly refresh — so every call retries those with exponential backoff
instead of failing the whole run.
"""

import http.client
import json
import time
import urllib.error
import urllib.request


_MAX_ATTEMPTS = 5
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# What a request can end in once retries are spent, for callers that
# tolerate an upstream being down. A dropped connection escapes urlopen
# unwrapped, hence ConnectionError and IncompleteRead.
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, ConnectionError,
                  http.client.IncompleteRead)


def is_retryable_error(exc: BaseException) -> bool:
    """True if `exc` is a transient error worth retrying.

    Any of NETWORK_ERRORS except an HTTPError outside 5xx / 429. Other
    http.client errors (InvalidURL, LineTooLong) are permanent.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_STATUS
    return isinstance(exc, NETWORK_ERRORS)


def backoff_seconds(attempt: int) -> float:
    """Exponential backoff for a 1-based attempt number: 1, 2, 4, 8 ..."""
    return float(2 ** (attempt - 1))


def get_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    max_attempts: int = _MAX_ATTEMPTS,
) -> str:
    """GET `url` and return the body as text, retrying transient failures
    with exponential backoff like `get_json`.

    Sends only the given headers, so it is also the helper for non-GitHub
    hosts, which must never see the GitHub token.
    """
    req = urllib.request.Request(url, headers=headers or {})
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode()
        except Exception as exc:  # noqa: BLE001 — re-raised below if fatal
            if attempt < max_attempts and is_retryable_error(exc):
                time.sleep(backoff_seconds(attempt))
                continue
            raise


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
    return json.loads(get_text(url, headers=headers, timeout=timeout,
                               max_attempts=max_attempts))
