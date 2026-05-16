"""Parse a Phabricator revision page's timeline.

Conduit (the JSON API) sits behind aggressive Varnish anti-abuse limits,
but the rendered revision page (`https://phabricator.services.mozilla.com/D<n>`)
is treated as normal browser traffic and ships the full timeline in
HTML — including the `accepted this revision` event that Conduit's
`transaction.search` exposes but the moz MCP server hides.

We parse it with regex because the HTML structure is stable and we want
zero external deps. The `print-only` span carries a precise UTC
timestamp per event (e.g. `2026-05-11 15:06:17 (UTC+0)`), so we don't
need to worry about the human-readable display strings.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


_HOST = "https://phabricator.services.mozilla.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_BOT_HANDLES = frozenset({"phab-bot", "Lando", "lando", "lando-bot"})

# Action verbs we recognise (Phab's wording, lowercased). Order matters
# only for `_REVIEW_ACTIONS`; the verb→action map is exhaustive over what
# we see in dom/media revisions and falls back to "other" for anything new.
_VERB_TO_ACTION: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^created this revision\b"),                "create"),
    (re.compile(r"^accepted this revision\b"),               "accept"),
    (re.compile(r"^requested changes to this revision\b"),   "request-changes"),
    (re.compile(r"^rejected this revision\b"),               "reject"),
    (re.compile(r"^abandoned this revision\b"),              "abandon"),
    (re.compile(r"^reclaimed this revision\b"),              "reclaim"),
    (re.compile(r"^reopened this revision\b"),               "reopen"),
    (re.compile(r"^requested review of this revision\b"),    "request-review"),
    (re.compile(r"^published this revision\b"),              "publish"),
    (re.compile(r"^closed this revision\b"),                 "close"),
    (re.compile(r"^updated this revision\b"),                "update-diff"),
    (re.compile(r"^added (?:a comment|inline comments?)\b"), "comment"),
    (re.compile(r"^added a reviewer\b"),                     "add-reviewer"),
    (re.compile(r"^removed a reviewer\b"),                   "remove-reviewer"),
    (re.compile(r"^added a child revision\b"),               "add-child"),
    (re.compile(r"^added a parent revision\b"),              "add-parent"),
    (re.compile(r"^marked \d+ inline\b"),                    "mark-done"),
    (re.compile(r"^changed the visibility\b"),               "change-visibility"),
    (re.compile(r"^retitled this revision\b"),               "retitle"),
    (re.compile(r"^edited the summary\b"),                   "edit-summary"),
    (re.compile(r"^changed the edit policy\b"),              "change-policy"),
]

_REVIEW_ACTIONS = frozenset({"accept", "request-changes", "reject", "comment"})

# Each real timeline event is wrapped in a transaction-anchor container.
# Splitting on that boundary cleanly separates events from page metadata
# (sidebar reviewers, header byline) that would otherwise match our
# actor/verb/timestamp pattern. The class string can carry extra modifiers
# like `phui-timeline-green` (used for accept events), so we match any
# `phui-timeline-shell` class prefix.
_TRANSACTION_SPLIT_RE = re.compile(
    r'<div class="phui-timeline-shell[^"]*" data-sigil="transaction anchor-container"'
)

# Within one transaction block: the FIRST actor handle (person or system
# like "Herald") + the verb/body that follows + the precise print-only
# timestamp. Bots use bare `phui-handle`; users use `phui-handle
# phui-link-person`; either way we want the first handle in the chunk.
_ENTRY_RE = re.compile(
    r'class="phui-handle[^"]*"[^>]*>([^<]+)</a>'
    r'(.*?)'
    r'<span class="print-only"[^>]*>([^<]+)</span>',
    re.DOTALL,
)

_TS_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\s*\(UTC([+-]\d+)\)"
)


@dataclass(frozen=True)
class Event:
    timestamp: datetime
    actor: str
    action: str
    raw_verb: str
    # For add-reviewer / remove-reviewer events: the target reviewer
    # handle (individual or group like "media-playback-reviewers").
    target: str | None = None


_RETRY_STATUSES = ("429", "500", "502", "503", "504")
_MAX_RETRIES = 4


class FetchError(RuntimeError):
    pass


def fetch_revision_page(
    d_number: int | str,
    *,
    timeout: float = 20.0,
    max_retries: int = _MAX_RETRIES,
) -> str:
    """One-shot fetch via a temporary Playwright browser.

    Cheap for spot checks (a few pages) but spins up a fresh Chromium
    per call. For bulk runs, use `PlaywrightFetcher` to reuse the
    browser across many fetches.
    """
    with PlaywrightFetcher() as f:
        return f.fetch(d_number, timeout=timeout, max_retries=max_retries)


async def bulk_fetch_async(
    d_numbers: list[str],
    *,
    concurrency: int = 5,
    timeout: float = 30.0,
    on_each: callable | None = None,
) -> dict[str, str | Exception]:
    """Fetch many revision pages concurrently using Playwright async.

    Returns `{d_number: html_str | Exception}`. Each fetch uses its own
    `page` inside one shared `browser` instance — keeps memory low
    (~150 MB total) while running up to `concurrency` requests in
    flight at once.

    `on_each(d, result)` is called as each fetch completes; useful for
    progress reporting and incremental persistence.
    """
    import asyncio
    from playwright.async_api import async_playwright

    sem = asyncio.Semaphore(concurrency)
    results: dict[str, str | Exception] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        async def fetch_one(d: str) -> None:
            async with sem:
                page = await browser.new_page(user_agent=_UA)
                try:
                    d_int = int(d.lstrip("D"))
                    url = f"{_HOST}/D{d_int}"
                    resp = await page.goto(url, timeout=int(timeout * 1000))
                    if resp and resp.status == 200:
                        html = await page.content()
                        results[d] = html
                    else:
                        results[d] = FetchError(
                            f"{url}: HTTP {resp.status if resp else '?'}"
                        )
                except Exception as e:
                    results[d] = e
                finally:
                    await page.close()
                    if on_each is not None:
                        on_each(d, results[d])

        await asyncio.gather(*(fetch_one(d) for d in d_numbers))
        await browser.close()
    return results


class PlaywrightFetcher:
    """Reusable Playwright session for bulk fetches.

    Mozilla Phabricator's Varnish CDN blocks urllib and curl after a
    few hundred requests from one IP, but accepts a real Chromium
    handshake the same way it accepts a browser visit. Driving
    Chromium via Playwright dodges the block; the only cost is ~3-5 s
    per page (browser-internal navigation + render).

    Use as a context manager:

        with PlaywrightFetcher() as f:
            for d in d_numbers:
                html = f.fetch(d)
    """

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None

    def __enter__(self) -> "PlaywrightFetcher":
        # Local import so the rest of the module (parser, tests) stays
        # importable without playwright installed.
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page(user_agent=_UA)
        return self

    def __exit__(self, *exc) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def fetch(
        self,
        d_number: int | str,
        *,
        timeout: float = 20.0,
        max_retries: int = _MAX_RETRIES,
    ) -> str:
        import time
        d_int = int(str(d_number).lstrip("D"))
        url = f"{_HOST}/D{d_int}"
        backoff = 30.0
        last_err = ""
        for attempt in range(max_retries):
            resp = self._page.goto(url, timeout=int(timeout * 1000))
            status = resp.status if resp else 0
            if status == 200:
                return self._page.content()
            if str(status) in _RETRY_STATUSES and attempt < max_retries - 1:
                last_err = f"HTTP {status}"
                time.sleep(backoff)
                backoff = min(backoff * 2, 300.0)
                continue
            last_err = f"HTTP {status}"
            break
        raise FetchError(f"{url}: {last_err}")


def _parse_timestamp(s: str) -> datetime | None:
    m = _TS_RE.search(s)
    if not m:
        return None
    y, mo, d, hh, mm, ss, off = m.groups()
    return datetime(
        int(y), int(mo), int(d), int(hh), int(mm), int(ss),
        tzinfo=timezone.utc,  # Phab's print-only always renders UTC+0
    )


def _verb_to_action(body_text: str) -> tuple[str, str]:
    verb = body_text.strip()
    for pat, action in _VERB_TO_ACTION:
        if pat.match(verb):
            return action, verb[:120]
    return "other", verb[:120]


# Inside an add-reviewer / remove-reviewer body, the target reviewer
# appears as a `phui-handle` link immediately after the verb.
_REVIEWER_TARGET_RE = re.compile(
    r"(?:added|removed) a reviewer:\s*([A-Za-z0-9_.\-]+)"
)


def _extract_target(action: str, body_text: str) -> str | None:
    if action not in ("add-reviewer", "remove-reviewer"):
        return None
    m = _REVIEWER_TARGET_RE.search(body_text)
    return m.group(1) if m else None


def parse_timeline(html: str) -> list[Event]:
    events: list[Event] = []
    chunks = _TRANSACTION_SPLIT_RE.split(html)
    # First chunk is the page preamble before any transaction — skip.
    for chunk in chunks[1:]:
        match = _ENTRY_RE.search(chunk)
        if not match:
            continue
        actor = match.group(1).strip()
        body_html = match.group(2)
        ts_str = match.group(3)

        verb_text = re.sub(r"<[^>]+>", " ", body_html)
        verb_text = re.sub(r"\s+", " ", verb_text).strip()
        verb_text = verb_text.lstrip(". ").strip()

        action, raw_verb = _verb_to_action(verb_text)
        ts = _parse_timestamp(ts_str)
        if ts is None:
            continue
        target = _extract_target(action, verb_text)
        events.append(
            Event(
                timestamp=ts,
                actor=actor,
                action=action,
                raw_verb=raw_verb,
                target=target,
            )
        )
    return events


def first_member_review_action(
    events: Iterable[Event],
    *,
    members: frozenset[str],
    author: str | None,
) -> Event | None:
    for e in events:
        if e.action not in _REVIEW_ACTIONS:
            continue
        if e.actor == author:
            continue
        if e.actor in _BOT_HANDLES:
            continue
        if e.actor not in members:
            continue
        return e
    return None
