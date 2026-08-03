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
  * Pure helpers (`build_summary_prompt`, `build_batch_prompt`,
    `parse_batch_response`, `summary_cache_key`, `extract_summary_text`)
    are network-free and unit-tested directly.
  * `summarize_features` is the orchestrator. It runs in two passes:
    resolve every feature area against the disk cache, then send the misses
    to an injected `summarize_fn(areas) -> {area_id: overview}` in batches.
    Batching is the whole reason for the two passes — a single walk can
    only ask for one area at a time. Tests inject `summarize_fn` and never
    hit the network.
  * `make_copilot_summarizer` builds the CI backend by shelling out to the
    GitHub Copilot CLI, which authenticates with the workflow's own token
    (no third-party key stored). It is natively batched because the CLI
    bills a ~12k-token agent preamble per invocation.
  * `make_anthropic_summarizer` builds the local backend against the
    Anthropic SDK (imported lazily so the package is only required when a
    summary is actually generated). It stays one-area-at-a-time — a plain
    completion API has no preamble to amortize — and `as_batch` adapts it.
"""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

from reviewstats.recent_changes import _patch_key

# Default model. Per the Claude-API guidance the default is Opus; override
# with REVIEW_STATS_SUMMARY_MODEL (e.g. "claude-haiku-4-5") to trade some
# quality for ~5x lower cost on the weekly batch.
DEFAULT_SUMMARY_MODEL = "claude-opus-4-8"

# GitHub Copilot CLI — the CI backend. It replaces GitHub Models, which was
# retired on 2026-07-30 (its inference endpoint now returns 410 Gone). The
# CLI keeps the property that mattered: it authenticates with the workflow's
# built-in GITHUB_TOKEN (permissions: copilot-requests: write), so no
# third-party key is stored. Unlike GitHub Models it is not free — calls
# consume GitHub AI Credits. Note it is an *agent*, not a plain completion
# endpoint: there is no system role (the instructions ride inline in
# `build_batch_prompt`) and it runs with tools available (see `workdir` and
# `--available-tools=` in `make_copilot_summarizer` / `build_copilot_argv`).
COPILOT_EXECUTABLE = "copilot"
# "auto" (Copilot picks) rather than a pinned id: which models a token may
# use depends on the account's Copilot plan, and an unavailable id is a hard
# error before any request is made — verified locally, where every pinned id
# tried (claude-sonnet-4.5, claude-haiku-4.5, gpt-4.1, gpt-5-mini) returned
# 'Model ... is not available' and only "auto" ran. Pin one via
# REVIEW_STATS_SUMMARY_MODEL if a specific model is wanted and known good.
DEFAULT_COPILOT_MODEL = "auto"
# Areas per call. Copilot Free allows 200 credits/month and ~49 areas need
# generating each week; at one call per area that overruns, at ~12 per call
# it fits several times over. Bounded rather than unlimited so one refused
# or truncated response costs a dozen areas, not the whole week.
DEFAULT_BATCH_SIZE = 12
# Per-call cap. A measured batch of 5 took 31s, so this is ~10x headroom for
# a full batch of 12 — but it is deliberately not larger: a cold cache is ~8
# batches (batching is per team, and each team's remainder rounds up), and
# 8 x this must stay well inside the workflow's 60-minute job budget. A job
# timeout is worse than a failed call, because .summary_cache/ is only
# committed by the final step.
COPILOT_TIMEOUT_SECONDS = 300

_STYLE_PROMPT = (
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
)

# Kept separate from the style guidance above because the batch prompt needs
# the same style but the opposite response format. Inlining "overview text
# only" ahead of "respond with JSON" would contradict itself, and a model
# that obeyed the first sentence would fail the whole batch.
_SINGLE_RESPONSE_INSTRUCTION = "Respond with the overview text only."

_SYSTEM_PROMPT = _STYLE_PROMPT + _SINGLE_RESPONSE_INSTRUCTION


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


def build_batch_prompt(areas: list[dict]) -> str:
    """One prompt covering several feature areas, answered as JSON.

    Copilot charges a ~12k-token agent preamble per invocation while our
    actual payload is ~700 tokens, so the per-area cost is almost entirely
    fixed overhead. Asking for N areas in one call amortizes it — the
    difference between fitting in Copilot Free's 200 credits/month and not.

    `areas` is a list of {"id", "label", "patches"}. The id is the content
    hash, which doubles as the JSON key so the response maps straight back
    onto cache entries.
    """
    blocks = []
    for area in areas:
        titles = "\n".join(f"- {p['subject']}" for p in area["patches"])
        blocks.append(
            f"Area id: {area['id']}\nName: {area['label']}\n"
            f"Patch titles that landed in this area:\n{titles}"
        )
    joined = "\n\n".join(blocks)
    return (
        f"{_STYLE_PROMPT}\n\n"
        f"You will be given {len(areas)} separate areas below. Write one "
        "overview for EACH of them, applying the instructions above to each "
        "independently.\n\n"
        "Respond with a single JSON object mapping each area id to its "
        "overview string, and nothing else — no code fence, no commentary. "
        'Example: {"<area id>": "<overview text>"}\n\n'
        f"{joined}"
    )


def parse_batch_response(text: Optional[str], expected_ids: list[str]) -> dict:
    """Pull {id: overview} out of a batch response.

    Tolerant of a code fence or chatter around the object, since the model
    is an agent rather than a JSON API. Anything not asked for is dropped —
    a hallucinated key must never be written to the cache under a hash no
    feature area maps to. Missing ids are simply absent, so a partial answer
    still lands and only the gaps retry.
    """
    if not text:
        return {}
    wanted = set(expected_ids)
    found: dict = {}
    decoder = json.JSONDecoder()
    # Try to decode an object at *every* '{', not just the first — a single
    # first-brace/last-brace span breaks on any stray brace in the chatter,
    # including the model echoing this prompt's own `{"<area id>": ...}`
    # example back before answering. Also collects across multiple objects,
    # so one-object-per-area answers still work.
    for pos in range(len(text)):
        if text[pos] != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text, pos)
        except ValueError:
            continue
        if isinstance(data, dict):
            _collect_overviews(data, wanted, found)
    return found


def _collect_overviews(data: dict, wanted: set, found: dict) -> None:
    """Harvest wanted id -> overview pairs, descending one level into a
    wrapper object (e.g. `{"overviews": {...}}`). First value for an id
    wins, so a later restatement can't overwrite a real answer."""
    for key, value in data.items():
        if key in wanted and key not in found:
            if isinstance(value, str) and value.strip():
                found[key] = value.strip()
        elif isinstance(value, dict):
            _collect_overviews(value, wanted, found)


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
    summarize_fn: Optional[Callable[[list[dict]], dict]],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Counter:
    """Fill each feature's `summary` across all recent-changes windows.

    Two passes. The first resolves every feature area against the on-disk
    cache (`.summary_cache/`, committed to git), deduping areas that repeat
    across windows, and collects the misses; the second sends those misses to `summarize_fn` in
    batches and writes the answers back. Splitting it this way is what makes
    batching possible — a single walk can only ask for one area at a time.

    `summarize_fn(areas) -> {area_id: overview}` takes a list of
    {"id", "label", "patches"} and need not answer every one; an unanswered
    area is left blank *and* uncached so a later run retries it. The disk
    cache is consulted **even when `summarize_fn` is None**, so a run with
    no backend still fills any overview previously generated and committed.

    Returns a Counter of {generated, reused, failed} (per unique content
    hash) so callers can sum across teams and tell a flaky area apart from a
    backend that is failing every single call — see `dead_backend_warning`.
    """
    cache_dir = Path(cache_dir)
    resolved: dict[str, str] = {}
    pending: dict[str, dict] = {}  # id -> area, deduped by content hash
    order: list[tuple[dict, str]] = []

    for window in windows.values():
        for feature in window.get("features", []):
            key = summary_cache_key(
                feature["feature"], [_patch_key(p) for p in feature["patches"]]
            )
            order.append((feature, key))
            if key in resolved or key in pending:
                continue  # same content in another window — one call, not two
            cached = _read_cached(cache_dir, key)
            if cached is not None:
                resolved[key] = cached
            elif summarize_fn is not None:
                pending[key] = {
                    "id": key,
                    "label": feature["label"],
                    "patches": feature["patches"],
                }

    reused = len(resolved)
    generated = 0
    calls = call_failures = 0  # per *call*, not per area — see dead_backend_warning
    areas = list(pending.values())
    for start in range(0, len(areas), batch_size):
        chunk = areas[start : start + batch_size]
        calls += 1
        try:
            answers = summarize_fn(chunk) or {}
        except Exception as exc:  # one bad batch must not void the others
            print(f"  [summary] batch of {len(chunk)} failed: {exc}")
            answers = {}
        if not isinstance(answers, dict):
            answers = {}
        if not answers:
            call_failures += 1
        for area in chunk:
            summary = answers.get(area["id"])
            if summary:
                _write_cached(cache_dir, area["id"], summary)
                resolved[area["id"]] = summary
                generated += 1

    failed = len(pending) - generated
    for feature, key in order:
        if resolved.get(key):
            feature["summary"] = resolved[key]

    if generated or reused or failed:
        print(
            f"  [summary] {generated} generated, {reused} reused from cache, "
            f"{failed} failed (left blank, will retry next run)"
        )
    return Counter(
        generated=generated,
        reused=reused,
        failed=failed,
        calls=calls,
        call_failures=call_failures,
    )


def dead_backend_warning(stats: Counter) -> Optional[str]:
    """Return a warning line when the backend produced nothing at all, else
    None.

    Lives next to `summarize_features` because it is a statement about that
    function's failure semantics: one bad call is retryable and self-heals
    next run, but *every* call failing is a dead backend.

    Judged on `call_failures` vs `calls`, not on `failed` — `failed` counts
    feature areas, and since batching one call covers ~12 of them, a single
    flaky invocation would otherwise read as a dozen independent failures.
    `calls` is only non-zero when a backend was actually invoked, so a
    cache-only run can never trip this.

    Needed because the failure is otherwise invisible — GitHub Models was
    retired on 2026-07-30 and the next weekly refresh 410'd on every single
    call, printed its usual summary line, and exited green.
    """
    calls = stats["calls"]
    if not calls or stats["call_failures"] < calls:
        return None
    return (
        f"summary backend produced nothing: all {calls} call(s) failed, "
        f"leaving {stats['failed']} feature area(s) with no overview. "
        f"Likely broken rather than flaky — check the log above for the "
        f"per-call error."
    )


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


def as_batch(
    per_area_fn: Callable[[str, list[dict]], Optional[str]],
) -> Callable[[list[dict]], dict]:
    """Adapt a one-area-at-a-time summarizer to the batch contract.

    Only Copilot needs true batching — its per-call agent preamble dwarfs
    the payload. A plain completion API has no such overhead, so Anthropic
    keeps its simpler per-area implementation and loops here."""

    def batch(areas: list[dict]) -> dict:
        out = {}
        for area in areas:
            # Guard per area, not per batch: these are real completed calls
            # that have already been paid for, so one area raising must not
            # discard the summaries its neighbours already returned.
            try:
                summary = per_area_fn(area["label"], area["patches"])
            except Exception as exc:
                print(f"  [summary] error for {area['label']!r}: {exc}")
                continue
            if summary:
                out[area["id"]] = summary
        return out

    return batch


def build_copilot_argv(
    prompt: str, *, model: str, executable: str = COPILOT_EXECUTABLE
) -> list[str]:
    """Argv for one non-interactive Copilot CLI run.

    Flag by flag, since this is a chat endpoint being driven as one:
      -s / --no-color        stdout is the response only, no decoration
      --no-ask-user          never pause for input it can't get in CI
      --allow-all-tools      the CLI requires it for non-interactive runs
      --available-tools=     …but expose none of them. Permission flags only
                             control approval prompts; this is what keeps the
                             tool schemas out of the (billed) request, and
                             the agent unable to touch anything
      --disable-builtin-mcps skip spawning the GitHub MCP server; we're
                             summarizing strings, and this runs ~60x a week
      --no-custom-instructions  ignore any AGENTS.md that would otherwise
                             reword the overviews out from under us

    The prompt is a single argv entry — never shell-interpolated."""
    argv = [
        executable,
        "-p", prompt,
        "-s",
        "--no-color",
        "--no-ask-user",
        "--allow-all-tools",
        "--available-tools=",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
    ]
    if model:
        argv.append(f"--model={model}")
    return argv


# Belt-and-braces cleanup of the CLI's stdout. `-s` is supposed to emit only
# the response, but this is prose that gets committed to .summary_cache/ and
# rendered on the dashboard, so strip any terminal chrome that leaks through.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_SPINNER_RE = re.compile(r"[⠀-⣿]")  # braille spinner frames


def extract_copilot_text(stdout: Optional[str]) -> str:
    """Strip ANSI escapes, spinner glyphs and in-place redraws from the CLI's
    stdout, returning the response text."""
    # split("\n"), not splitlines(): splitlines() also breaks on \r, which
    # would turn each spinner redraw into its own line instead of letting
    # the last one win. The trailing strip() drops the blank lines that
    # leaves at either end.
    lines = [
        _SPINNER_RE.sub("", _ANSI_RE.sub("", raw.rstrip("\r").split("\r")[-1]))
        for raw in (stdout or "").split("\n")
    ]
    return "\n".join(line.rstrip() for line in lines).strip()


def _run_copilot(argv: list[str], *, cwd: Optional[str], timeout: int):
    """Run the Copilot CLI, returning (returncode, stdout, stderr).

    With no `cwd` the agent runs in a throwaway empty directory rather than
    the checkout — it has tools enabled, and summarizing patch titles never
    needs to touch repo files."""
    import contextlib
    import subprocess
    import tempfile

    with contextlib.ExitStack() as stack:
        workdir = cwd or stack.enter_context(
            tempfile.TemporaryDirectory(prefix="review-stats-summary-")
        )
        proc = subprocess.run(
            argv, cwd=workdir, timeout=timeout, capture_output=True, text=True
        )
    return proc.returncode, proc.stdout, proc.stderr


def make_copilot_summarizer(
    *,
    model: str = DEFAULT_COPILOT_MODEL,
    run=_run_copilot,
    timeout: int = COPILOT_TIMEOUT_SECONDS,
    workdir: Optional[str] = None,
) -> Callable[[list[dict]], dict]:
    """Build a batch `summarize_fn` backed by the GitHub Copilot CLI.

    Authenticates via the ambient GITHUB_TOKEN, so no third-party key is
    stored. `run(argv, cwd=, timeout=) -> (rc, stdout, stderr)` is
    injectable for tests. Any failure returns {} so the refresh degrades to
    no overviews for that batch rather than failing the whole run.

    Batched rather than one call per area because the CLI bills a ~12k-token
    agent preamble per invocation regardless of payload size — see
    `build_batch_prompt`.

    No call pacing: unlike GitHub Models' free per-minute tier, Copilot is
    credit-billed with no rate limit to stay under (it hard-stops at the
    plan's credit ceiling instead).
    """

    def summarize(areas: list[dict]) -> dict:
        if not areas:
            return {}
        ids = [a["id"] for a in areas]
        argv = build_copilot_argv(build_batch_prompt(areas), model=model)
        label = f"batch of {len(areas)}"
        try:
            code, out, err = run(argv, cwd=workdir, timeout=timeout)
        except Exception as exc:  # missing binary, timeout, OS error
            print(f"  [summary] Copilot CLI error for {label}: {exc}")
            return {}
        if code != 0:
            detail = (err or out or "").strip().splitlines()
            reason = detail[-1][:200] if detail else "no output"
            print(f"  [summary] Copilot CLI exit {code} for {label}: {reason}")
            return {}
        answers = parse_batch_response(extract_copilot_text(out), ids)
        if not answers:
            print(f"  [summary] unparseable response for {label}")
        return answers

    return summarize
