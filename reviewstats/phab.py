"""Phabricator Conduit API client (thin).

Pure helpers (`build_form_payload`, `parse_*`) are testable in isolation.
The network shell (`conduit_call`) is the only place that does I/O.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Iterator


_HOST = "https://phabricator.services.mozilla.com/api/"
_USER_AGENT = "firefox-review-stats/0.1"
_RETRY_STATUSES = (429, 500, 502, 503, 504)
_MAX_RETRIES = 5


def read_token(arcrc_path: Path | None = None) -> str:
    path = arcrc_path or (Path.home() / ".arcrc")
    arcrc = json.loads(path.read_text(encoding="utf-8"))
    return arcrc["hosts"][_HOST]["token"]


def build_form_payload(params: dict) -> str:
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            base = key.removesuffix("[]")
            for i, item in enumerate(value):
                pairs.append((f"{base}[{i}]", str(item)))
        else:
            pairs.append((key, str(value)))
    return urllib.parse.urlencode(pairs)


def conduit_call(method: str, params: dict, *, token: str) -> dict:
    full = {"api.token": token, **params}
    body = build_form_payload(full).encode("utf-8")
    req = urllib.request.Request(
        _HOST + method,
        data=body,
        headers={"User-Agent": _USER_AGENT},
    )
    backoff = 10.0
    for attempt in range(_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in _RETRY_STATUSES or attempt == _MAX_RETRIES - 1:
                raise
            print(
                f"  conduit {e.code} on {method}, sleeping {backoff:.0f}s..."
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 300.0)
    raise RuntimeError("unreachable")


def _batches(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def parse_revision_search_response(raw: dict) -> dict[str, dict]:
    if raw.get("error_code"):
        raise RuntimeError(
            f"Phabricator error: {raw['error_code']} {raw.get('error_info','')}"
        )
    out: dict[str, dict] = {}
    for item in raw.get("result", {}).get("data", []):
        d_id = item["id"]
        f = item.get("fields", {})
        out[f"D{d_id}"] = {
            "phid": item.get("phid"),
            "author_phid": f.get("authorPHID"),
            "date_created": f.get("dateCreated"),
            "date_modified": f.get("dateModified"),
            "title": f.get("title"),
        }
    return out


def fetch_revisions(
    d_numbers: Iterable[str], *, token: str, batch_size: int = 100
) -> dict[str, dict]:
    """Batch-fetch metadata for D<N> revisions."""
    numeric_ids = [int(d.lstrip("D")) for d in d_numbers]
    out: dict[str, dict] = {}
    for chunk in _batches(numeric_ids, batch_size):
        raw = conduit_call(
            "differential.revision.search",
            {"constraints[ids][]": chunk},
            token=token,
        )
        out.update(parse_revision_search_response(raw))
        time.sleep(0.1)  # be polite to Conduit
    return out


def fetch_transactions(revision_phid: str, *, token: str) -> list[dict]:
    raw = conduit_call(
        "transaction.search",
        {"objectIdentifier": revision_phid},
        token=token,
    )
    if raw.get("error_code"):
        raise RuntimeError(
            f"Phabricator error: {raw['error_code']} {raw.get('error_info','')}"
        )
    return raw.get("result", {}).get("data", [])
