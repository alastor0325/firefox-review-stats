"""LLM-backed per-category "what we did" overviews for the Recent Changes
tab.

For each feature area in a window we ask Claude to read the area's landed
patch titles and reason out a short overview: what was done, the fix or
benefit, and what it affects. The full change list is shown verbatim
beneath the overview — the LLM only writes the synthesis.

Overviews are cached on disk keyed by the *content* (feature + the set of
patches), so the weekly refresh only pays for feature-sets it hasn't
summarized before.

Design:
  * Pure helpers (`build_summary_prompt`, `summary_cache_key`,
    `extract_summary_text`) are network-free and unit-tested directly.
  * `summarize_features` is the orchestrator: it walks the recent-changes
    windows, fills each feature's `summary`, and is driven by an injected
    `summarize_fn(label, patches) -> str | None` so tests never hit the API.
  * `make_anthropic_summarizer` builds the real `summarize_fn` against the
    Anthropic SDK (imported lazily so the package is only required when a
    summary is actually generated).
"""

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

from reviewstats.recent_changes import _patch_key

# Default model. Per the Claude-API guidance the default is Opus; override
# with REVIEW_STATS_SUMMARY_MODEL (e.g. "claude-haiku-4-5") to trade some
# quality for ~5x lower cost on the weekly batch.
DEFAULT_SUMMARY_MODEL = "claude-opus-4-8"

_SYSTEM_PROMPT = (
    "You explain recent changes to one part of the Firefox browser for a "
    "broad audience. Given the area name and the titles of the patches "
    "that landed in it, reason over them and write a short overview "
    "(about 2-4 sentences — enough to give real context, but keep it "
    "tight) of what changed and why it matters.\n\n"
    "Write so a non-engineer can follow it, in plain everyday language. "
    "BUT do not strip out the important real concepts: name the actual "
    "technologies, standards, formats, and features involved — e.g. "
    "WebRTC, HEVC, Media Source Extensions (MSE), DRM, WebCodecs, Web "
    "Audio, HLS, picture-in-picture — and add a few plain words of "
    "explanation when a term may be unfamiliar (e.g. 'WebRTC, the "
    "technology behind video calls'). Never water a meaningful concept "
    "down to a vague phrase like 'a video-calling option' just to avoid "
    "naming it — name it. Only avoid low-level code details: function "
    "names, file names, and internal class names.\n\n"
    "Group related work rather than listing patches; do not include bug "
    "numbers, headings, or bullet points. Emphasis markup: wrap a "
    "genuinely important, user-facing highlight in **double asterisks** "
    "(shown in red) — use this sparingly, at most once per overview, and "
    "not merely to mark a technology name; many overviews need none. Use "
    "_underscores_ for a minor aside or caveat (e.g. 'no visible change'). "
    "Respond with the overview text only."
)


def summary_cache_key(feature: str, patch_keys: list[str]) -> str:
    """Stable content hash for one feature's overview. Order-independent
    over the patch identifiers so a reordered list reuses the same cache
    entry; changes when the feature or the *set* of patches changes."""
    payload = feature + "\n" + "\n".join(sorted(patch_keys))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def build_summary_prompt(feature_label: str, patches: list[dict]) -> tuple[str, str]:
    """Return (system, user) prompt strings for one feature area."""
    titles = "\n".join(f"- {p['subject']}" for p in patches)
    user = (
        f"Area: {feature_label}\n\n"
        f"Patch titles that landed in this area:\n{titles}\n\n"
        "Overview:"
    )
    return _SYSTEM_PROMPT, user


def extract_summary_text(content: list) -> str:
    """Join the text blocks of an Anthropic response's content list,
    skipping non-text blocks (e.g. thinking). Returns a stripped string."""
    parts = [
        getattr(b, "text", "")
        for b in content
        if getattr(b, "type", None) == "text"
    ]
    return "".join(parts).strip()


def _read_cached(cache_dir: Path, key: str) -> Optional[str]:
    path = cache_dir / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())["summary"]
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def _write_cached(cache_dir: Path, key: str, summary: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps({"summary": summary}))


def summarize_features(
    windows: dict,
    *,
    cache_dir: Path,
    summarize_fn: Optional[Callable[[str, list[dict]], Optional[str]]],
) -> None:
    """Fill each feature's `summary` across all recent-changes windows.

    Resolution order per feature area: in-run memo → on-disk cache
    (`.summary_cache/`, committed to git) → `summarize_fn`. The disk cache
    is consulted **even when `summarize_fn` is None** — so a run without an
    API key (e.g. CI) still fills any overview previously generated and
    committed locally, leaving only never-seen feature-areas blank. When a
    key *is* present, freshly-generated overviews are written back to the
    cache so they can be committed. `summarize_fn` returning None (failure)
    is left un-cached so a later run can retry.
    """
    cache_dir = Path(cache_dir)
    memo: dict[str, Optional[str]] = {}
    for window in windows.values():
        for feature in window.get("features", []):
            key = summary_cache_key(
                feature["feature"],
                [_patch_key(p) for p in feature["patches"]],
            )
            if key in memo:
                summary = memo[key]
            else:
                summary = _read_cached(cache_dir, key)
                if summary is None and summarize_fn is not None:
                    summary = summarize_fn(
                        feature["label"], feature["patches"]
                    )
                    if summary:
                        _write_cached(cache_dir, key, summary)
                memo[key] = summary
            if summary:
                feature["summary"] = summary


def make_anthropic_summarizer(
    *,
    model: str = DEFAULT_SUMMARY_MODEL,
    client=None,
) -> Callable[[str, list[dict]], Optional[str]]:
    """Build a `summarize_fn` backed by the Anthropic SDK.

    `anthropic` is imported lazily so the dependency is only needed when a
    summary is actually generated. Adaptive thinking is requested so the
    model reasons over the change set before writing — with a fallback to
    no-thinking for models that don't support it. Any API error returns
    None (the pipeline degrades to no overview rather than failing the
    whole refresh)."""
    import anthropic  # lazy: only required when summaries are generated

    if client is None:
        client = anthropic.Anthropic()

    def summarize(feature_label: str, patches: list[dict]) -> Optional[str]:
        system, user = build_summary_prompt(feature_label, patches)

        def _create(think: bool):
            kwargs = dict(
                model=model,
                max_tokens=1200,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            if think:
                kwargs["thinking"] = {"type": "adaptive"}
            return client.messages.create(**kwargs)

        try:
            try:
                message = _create(think=True)
            except anthropic.BadRequestError:
                # Model doesn't support adaptive thinking — retry plainly.
                message = _create(think=False)
        except anthropic.APIError as exc:
            print(f"  [summary] API error for {feature_label!r}: {exc}")
            return None
        return extract_summary_text(message.content) or None

    return summarize
