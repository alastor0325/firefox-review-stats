"""Unit tests for the LLM summarization helpers (no network).

The Anthropic call itself is injected as `summarize_fn`, so these tests
never touch the SDK or the network.
"""

import json
import sys
import types
from collections import Counter
from types import SimpleNamespace

import pytest

from reviewstats.summarize import (
    build_batch_prompt,
    build_copilot_argv,
    build_summary_prompt,
    extract_copilot_text,
    extract_summary_text,
    make_anthropic_summarizer,
    as_batch,
    make_copilot_summarizer,
    parse_batch_response,
    summarize_features,
    summary_cache_key,
)


def _patch(sha, *, dr=None, subject="Do a thing", author="Tester"):
    return {
        "sha": sha, "short_sha": sha[:12], "date": "2026-06-01",
        "differential_revision": dr, "subject": subject,
        "author": author, "bug": "1",
    }


class TestSummaryCacheKey:
    def test_stable_and_order_independent(self):
        assert summary_cache_key("eme", ["D1", "D2"]) == summary_cache_key("eme", ["D2", "D1"])

    def test_sensitive_to_patches(self):
        assert summary_cache_key("eme", ["D1"]) != summary_cache_key("eme", ["D1", "D2"])

    def test_sensitive_to_feature(self):
        assert summary_cache_key("eme", ["D1"]) != summary_cache_key("webaudio", ["D1"])


class TestBuildSummaryPrompt:
    def test_includes_label_and_titles(self):
        system, user = build_summary_prompt(
            "Encrypted Media (EME / DRM)",
            [_patch("a", subject="Fix CDM shutdown crash"),
             _patch("b", subject="Add Widevine L1 probe")],
        )
        assert isinstance(system, str) and system
        assert "Encrypted Media (EME / DRM)" in user
        assert "Fix CDM shutdown crash" in user
        assert "Add Widevine L1 probe" in user


class TestExtractSummaryText:
    def test_joins_text_blocks_skips_thinking(self):
        content = [
            SimpleNamespace(type="thinking", thinking="ignore"),
            SimpleNamespace(type="text", text="Reworked CDM shutdown."),
        ]
        assert extract_summary_text(content) == "Reworked CDM shutdown."

    def test_empty(self):
        assert extract_summary_text([]) == ""


class TestSummarizeFeatures:
    def _windows(self):
        return {
            "1w": {"window_start": "2026-05-27", "window_end": "2026-06-03",
                   "total": 1, "features": [
                       {"feature": "eme", "label": "EME", "count": 1,
                        "patches": [_patch("a", dr="D1")]}]},
            "1m": {"window_start": "2026-05-04", "window_end": "2026-06-03",
                   "total": 1, "features": [
                       {"feature": "eme", "label": "EME", "count": 1,
                        "patches": [_patch("a", dr="D1")]}]},
        }

    def test_fills_each_feature_and_caches(self, tmp_path):
        calls = []

        def fake(areas):
            calls.extend(a["label"] for a in areas)
            return {a["id"]: f"Overview of {a['label']}" for a in areas}

        windows = self._windows()
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=fake)
        assert windows["1m"]["features"][0]["summary"] == "Overview of EME"
        # Identical feature-set across 1w/1m → summarized once (deduped).
        assert calls == ["EME"]
        assert list(tmp_path.glob("*.json"))

    def test_uses_disk_cache(self, tmp_path):
        windows = self._windows()
        key = summary_cache_key("eme", ["D1"])
        (tmp_path / f"{key}.json").write_text(json.dumps({"summary": "cached"}))

        def boom(areas):
            raise AssertionError("cache hit expected — should not call")

        summarize_features(windows, cache_dir=tmp_path, summarize_fn=boom)
        assert windows["1w"]["features"][0]["summary"] == "cached"

    def test_none_fn_with_empty_cache_leaves_blank(self, tmp_path):
        # No key and nothing cached → the area stays blank (CI fallback).
        windows = self._windows()
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=None)
        assert "summary" not in windows["1w"]["features"][0]

    def test_none_fn_still_fills_from_committed_cache(self, tmp_path):
        # The hybrid model: a run without a key (CI) reuses an overview a
        # local run already generated and committed to .summary_cache.
        windows = self._windows()
        key = summary_cache_key("eme", ["D1"])
        (tmp_path / f"{key}.json").write_text(json.dumps({"summary": "from cache"}))

        summarize_features(windows, cache_dir=tmp_path, summarize_fn=None)
        assert windows["1w"]["features"][0]["summary"] == "from cache"

    def test_failed_summary_left_absent_and_uncached(self, tmp_path):
        windows = self._windows()
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=lambda areas: {})
        assert "summary" not in windows["1w"]["features"][0]
        assert not list(tmp_path.glob("*.json"))

    def test_returns_counts(self, tmp_path):
        # Counts are returned (not just printed) so the caller can detect a
        # backend that is failing every call — the GitHub Models retirement
        # went unnoticed for a week because a 100% failure rate still
        # printed a line and exited green.
        windows = self._windows()
        stats = summarize_features(
            windows, cache_dir=tmp_path, summarize_fn=lambda areas: {}
        )
        assert stats["generated"] == 0 and stats["reused"] == 0
        assert stats["failed"] == 1
        # Call-level counters drive the dead-backend warning: one batch was
        # attempted and it came back empty.
        assert stats["calls"] == 1 and stats["call_failures"] == 1

    def test_counts_are_summable_across_teams(self, tmp_path):
        # main() adds up one Counter per team, so + must work.
        a = summarize_features(
            self._windows(), cache_dir=tmp_path, summarize_fn=lambda areas: {a["id"]: "x" for a in areas}
        )
        b = summarize_features(
            self._windows(), cache_dir=tmp_path, summarize_fn=lambda areas: {a["id"]: "x" for a in areas}
        )
        assert (a + b)["generated"] + (a + b)["reused"] == 2

    def test_returns_counts_for_generated_and_reused(self, tmp_path):
        windows = self._windows()
        stats = summarize_features(
            windows, cache_dir=tmp_path, summarize_fn=lambda areas: {a["id"]: "text" for a in areas}
        )
        assert stats["generated"] == 1 and stats["failed"] == 0

    def test_corrupt_cache_entry_is_resummarized(self, tmp_path):
        # A garbage cache file is treated as a miss → summarize_fn runs and
        # overwrites it (rather than crashing or yielding no summary).
        windows = self._windows()
        key = summary_cache_key("eme", ["D1"])
        (tmp_path / f"{key}.json").write_text("{not json")

        summarize_features(
            windows,
            cache_dir=tmp_path,
            summarize_fn=lambda areas: {a["id"]: "fresh" for a in areas},
        )
        assert windows["1w"]["features"][0]["summary"] == "fresh"
        assert json.loads((tmp_path / f"{key}.json").read_text())["summary"] == "fresh"


def _install_fake_anthropic(monkeypatch):
    """Inject a stub `anthropic` module so make_anthropic_summarizer can be
    tested without the real SDK installed. Returns the exception classes."""
    mod = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class BadRequestError(APIError):
        pass

    mod.APIError = APIError
    mod.BadRequestError = BadRequestError
    mod.Anthropic = lambda *a, **k: None  # not used; we inject a client
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    return BadRequestError, APIError


def _msg(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class _FakeMessages:
    def __init__(self, impl):
        self._impl = impl

    def create(self, **kwargs):
        return self._impl(**kwargs)


class _FakeClient:
    def __init__(self, impl):
        self.messages = _FakeMessages(impl)


class TestAnthropicSummarizer:
    def test_success_returns_text(self, monkeypatch):
        _install_fake_anthropic(monkeypatch)
        client = _FakeClient(lambda **k: _msg("An overview."))
        fn = make_anthropic_summarizer(client=client)
        assert fn("EME", [{"subject": "x"}]) == "An overview."

    def test_uses_adaptive_thinking_then_falls_back(self, monkeypatch):
        BadRequestError, _ = _install_fake_anthropic(monkeypatch)
        seen = []

        def impl(**kwargs):
            seen.append("thinking" in kwargs)
            if "thinking" in kwargs:
                raise BadRequestError("model lacks adaptive thinking")
            return _msg("Plain overview.")

        fn = make_anthropic_summarizer(client=_FakeClient(impl))
        assert fn("EME", [{"subject": "x"}]) == "Plain overview."
        # First call requested adaptive thinking; retry dropped it.
        assert seen == [True, False]

    def test_api_error_returns_none(self, monkeypatch):
        _, APIError = _install_fake_anthropic(monkeypatch)

        def impl(**kwargs):
            raise APIError("boom")

        fn = make_anthropic_summarizer(client=_FakeClient(impl))
        assert fn("EME", [{"subject": "x"}]) is None


class TestGithubModelsBackendRemoved:
    """GitHub Models was retired on 2026-07-30 (every call 410s). The backend
    is gone — this guards against it being reintroduced by a stale import."""

    def test_factory_is_gone(self):
        import reviewstats.summarize as s

        assert not hasattr(s, "make_github_models_summarizer")
        assert not hasattr(s, "GITHUB_MODELS_URL")


class TestBuildCopilotArgv:
    def test_non_interactive_scriptable_flags(self):
        argv = build_copilot_argv("hello", model="claude-sonnet-4.5")
        assert argv[0] == "copilot"
        # -p carries the prompt as a single argv entry (never shell-quoted).
        assert argv[argv.index("-p") + 1] == "hello"
        # -s: response only, no stats/decoration. --no-ask-user: never block
        # waiting for input in CI.
        assert "-s" in argv and "--no-ask-user" in argv
        # The CLI refuses to run non-interactively without this.
        assert "--allow-all-tools" in argv
        assert "--model=claude-sonnet-4.5" in argv

    def test_defaults_to_auto_model(self):
        # Pinned model ids are gated by the token's Copilot plan and fail
        # hard ("Model ... is not available") before any request. "auto"
        # always resolves, so it is the only safe default.
        from reviewstats.summarize import DEFAULT_COPILOT_MODEL

        assert DEFAULT_COPILOT_MODEL == "auto"

    def test_ignores_repo_custom_instructions(self):
        # An AGENTS.md in the working tree would otherwise rewrite the
        # overview style; the summary prompt is the only instruction.
        assert "--no-custom-instructions" in build_copilot_argv("x", model="auto")

    def test_exposes_no_tools_to_the_model(self):
        # Summarizing titles needs no tools. --allow-all-tools only waives
        # approval prompts; an empty --available-tools is what actually
        # keeps the tool schemas out of every billed request.
        argv = build_copilot_argv("x", model="auto")
        assert "--available-tools=" in argv
        assert "--disable-builtin-mcps" in argv

    def test_model_omitted_when_falsy(self):
        argv = build_copilot_argv("hello", model="")
        assert not any(a.startswith("--model") for a in argv)

    def test_prompt_with_newlines_stays_one_argument(self):
        argv = build_copilot_argv("line1\nline2", model="m")
        assert "line1\nline2" in argv


class TestExtractCopilotText:
    def test_plain_text(self):
        assert extract_copilot_text("  An overview.  \n") == "An overview."

    def test_strips_ansi_colour_codes(self):
        assert extract_copilot_text("\x1b[32mGreen text.\x1b[0m") == "Green text."

    def test_strips_spinner_glyphs_and_carriage_returns(self):
        # The CLI redraws a braille spinner in place; -s should suppress it,
        # but never let chrome leak into a committed overview.
        raw = "⠋ Thinking\r⠙ Thinking\rReal overview.\n"
        assert extract_copilot_text(raw) == "Real overview."

    def test_drops_leading_and_trailing_blank_lines(self):
        assert extract_copilot_text("\n\n Body. \n\n") == "Body."

    def test_empty_and_none(self):
        assert extract_copilot_text("") == ""
        assert extract_copilot_text(None) == ""


class TestCopilotSummarizer:
    def test_success_and_command_shape(self):
        seen = {}

        def run(argv, *, cwd, timeout):
            seen.update(argv=argv, cwd=cwd, timeout=timeout)
            return 0, '{"k1": "  Copilot overview.  "}', ""

        fn = make_copilot_summarizer(model="claude-sonnet-4.5", run=run)
        assert fn([_area("k1", "EME", ("Fix X",))]) == {"k1": "Copilot overview."}
        assert seen["argv"][0] == "copilot"
        prompt = seen["argv"][seen["argv"].index("-p") + 1]
        assert "Fix X" in prompt and "k1" in prompt
        assert seen["timeout"] > 0

    def test_nonzero_exit_returns_none(self):
        fn = make_copilot_summarizer(
            run=lambda *a, **k: (1, "", "not authenticated")
        )
        assert fn([_area("k1")]) == {}

    def test_subprocess_raise_returns_none(self):
        def run(*a, **k):
            raise OSError("copilot: command not found")

        fn = make_copilot_summarizer(run=run)
        assert fn([_area("k1")]) == {}

    def test_empty_output_returns_none(self):
        # Blank stdout must not be cached as a valid (empty) overview.
        fn = make_copilot_summarizer(
            run=lambda *a, **k: (0, "   \n", "")
        )
        assert fn([_area("k1")]) == {}

    def test_runs_outside_the_repo_checkout(self, tmp_path):
        # The agent has tools enabled; keep its working directory away from
        # the checkout so it cannot wander into repo files.
        seen = {}

        def run(argv, *, cwd, timeout):
            seen["cwd"] = cwd
            return 0, '{"k1": "ok"}', ""

        fn = make_copilot_summarizer(run=run, workdir=str(tmp_path))
        fn([_area("k1")])
        assert seen["cwd"] == str(tmp_path)


# --------------------------------------------------------------------------
# Batching.
#
# Copilot bills per token and charges a ~12,000-token agent preamble on
# *every* invocation, against a 200-credit/month Copilot Free allowance.
# One call per feature area (~49 uncached areas/week) does not fit; batching
# the areas into a handful of calls amortizes that overhead and does.
# --------------------------------------------------------------------------


def _area(aid, label="EME", subjects=("Fix X",)):
    return {
        "id": aid,
        "label": label,
        "patches": [_patch(aid, subject=s) for s in subjects],
    }


class TestBuildBatchPrompt:
    def test_includes_every_area_id_label_and_title(self):
        prompt = build_batch_prompt(
            [_area("k1", "EME", ("Fix CDM crash",)),
             _area("k2", "Web Audio", ("Add worklet test",))]
        )
        for token in ("k1", "k2", "EME", "Web Audio",
                      "Fix CDM crash", "Add worklet test"):
            assert token in prompt

    def test_carries_the_shared_style_instructions(self):
        # The batch prompt must not silently drop the house style that the
        # single-area prompt enforces (plain language, name technologies,
        # emphasis markup) — otherwise batching changes the prose.
        prompt = build_batch_prompt([_area("k1")])
        assert "**double asterisks**" in prompt
        assert "non-engineer" in prompt

    def test_asks_for_json_keyed_by_id(self):
        prompt = build_batch_prompt([_area("k1")])
        assert "JSON" in prompt


class TestParseBatchResponse:
    def test_plain_json_object(self):
        out = parse_batch_response('{"k1": "One.", "k2": "Two."}', ["k1", "k2"])
        assert out == {"k1": "One.", "k2": "Two."}

    def test_strips_markdown_code_fence(self):
        raw = '```json\n{"k1": "One."}\n```'
        assert parse_batch_response(raw, ["k1"]) == {"k1": "One."}

    def test_ignores_prose_around_the_object(self):
        raw = 'Sure, here you go:\n{"k1": "One."}\nHope that helps!'
        assert parse_batch_response(raw, ["k1"]) == {"k1": "One."}

    def test_drops_ids_we_did_not_ask_for(self):
        # A hallucinated key must never reach the cache under a bogus hash.
        out = parse_batch_response('{"k1": "One.", "bogus": "Nope."}', ["k1"])
        assert out == {"k1": "One."}

    def test_partial_response_returns_what_it_got(self):
        # Two asked for, one answered: the answered one is still usable and
        # the missing one is retried next run rather than voiding the batch.
        out = parse_batch_response('{"k1": "One."}', ["k1", "k2"])
        assert out == {"k1": "One."}

    def test_blank_and_non_string_values_dropped(self):
        raw = '{"k1": "  ", "k2": null, "k3": 5, "k4": "Real."}'
        assert parse_batch_response(raw, ["k1", "k2", "k3", "k4"]) == {"k4": "Real."}

    def test_survives_stray_braces_in_the_chatter(self):
        # A first-brace/last-brace span breaks on any brace outside the
        # object. Each of these previously returned {} and lost the batch.
        cases = [
            '{"k1":"One."}\nLet me know if you want more :}',
            'Note: I use {area id} as the key.\n{"k1":"One."}',
            '```json\n{"k1":"One."}\n```\nDone {ok}',
        ]
        for raw in cases:
            assert parse_batch_response(raw, ["k1"]) == {"k1": "One."}, raw

    def test_survives_the_prompt_example_being_echoed_back(self):
        # build_batch_prompt itself contains {"<area id>": "<overview text>"}.
        # A model restating the format before answering must not wipe the batch.
        raw = 'Format: {"<area id>": "<overview text>"}\n{"k1": "One."}'
        assert parse_batch_response(raw, ["k1"]) == {"k1": "One."}

    def test_accepts_one_object_per_area(self):
        raw = '{"k1": "One."}\n{"k2": "Two."}'
        assert parse_batch_response(raw, ["k1", "k2"]) == {"k1": "One.", "k2": "Two."}

    def test_descends_into_a_wrapper_object(self):
        raw = '{"overviews": {"k1": "One."}}'
        assert parse_batch_response(raw, ["k1"]) == {"k1": "One."}

    def test_first_answer_wins(self):
        # A restatement after the real answer must not overwrite it.
        raw = '{"k1": "Real."}\nOr as JSON: {"k1": "<overview text>"}'
        assert parse_batch_response(raw, ["k1"]) == {"k1": "Real."}

    def test_malformed_json_returns_empty(self):
        assert parse_batch_response("not json at all", ["k1"]) == {}
        assert parse_batch_response("", ["k1"]) == {}
        assert parse_batch_response(None, ["k1"]) == {}


class TestSummarizeFeaturesBatching:
    def _windows(self, n):
        feats = [
            {"feature": f"f{i}", "label": f"Area {i}", "count": 1,
             "patches": [_patch(f"s{i}", dr=f"D{i}")]}
            for i in range(n)
        ]
        return {"1w": {"total": n, "features": feats}}

    def test_one_call_covers_many_areas(self, tmp_path):
        calls = []

        def batch(areas):
            calls.append(len(areas))
            return {a["id"]: f"Overview {a['label']}" for a in areas}

        windows = self._windows(5)
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=batch)
        # Five areas, one round trip — that is the whole point.
        assert calls == [5]
        assert windows["1w"]["features"][0]["summary"] == "Overview Area 0"
        assert len(list(tmp_path.glob("*.json"))) == 5

    def test_respects_batch_size(self, tmp_path):
        sizes = []

        def batch(areas):
            sizes.append(len(areas))
            return {a["id"]: "x" for a in areas}

        summarize_features(
            self._windows(7), cache_dir=tmp_path, summarize_fn=batch, batch_size=3
        )
        assert sizes == [3, 3, 1]

    def test_only_cache_misses_are_sent(self, tmp_path):
        # Pre-seed two of three areas; only the third should cost credits.
        windows = self._windows(3)
        for i in (0, 1):
            key = summary_cache_key(f"f{i}", [f"D{i}"])
            (tmp_path / f"{key}.json").write_text(json.dumps({"summary": "old"}))

        sent = []

        def batch(areas):
            sent.extend(a["label"] for a in areas)
            return {a["id"]: "new" for a in areas}

        summarize_features(windows, cache_dir=tmp_path, summarize_fn=batch)
        assert sent == ["Area 2"]
        assert windows["1w"]["features"][0]["summary"] == "old"
        assert windows["1w"]["features"][2]["summary"] == "new"

    def test_areas_missing_from_the_response_count_as_failed(self, tmp_path):
        windows = self._windows(3)
        stats = summarize_features(
            windows,
            cache_dir=tmp_path,
            # Answers only the first area.
            summarize_fn=lambda areas: {areas[0]["id"]: "only one"},
        )
        assert stats["generated"] == 1
        assert stats["failed"] == 2
        # The unanswered ones stay blank AND uncached, so they retry.
        assert "summary" not in windows["1w"]["features"][1]
        assert len(list(tmp_path.glob("*.json"))) == 1

    def test_batch_raising_fails_only_that_batch(self, tmp_path):
        def batch(areas):
            if areas[0]["label"] == "Area 0":
                raise RuntimeError("quota exhausted")
            return {a["id"]: "ok" for a in areas}

        windows = self._windows(4)
        stats = summarize_features(
            windows, cache_dir=tmp_path, summarize_fn=batch, batch_size=2
        )
        # First batch died, second still landed.
        assert stats["failed"] == 2 and stats["generated"] == 2

    def test_duplicate_areas_across_windows_sent_once(self, tmp_path):
        # 1w and 1m usually share some feature areas; identical content must
        # cost one call, not two.
        feat = {"feature": "eme", "label": "EME", "count": 1,
                "patches": [_patch("a", dr="D1")]}
        windows = {"1w": {"features": [dict(feat)]}, "1m": {"features": [dict(feat)]}}
        sent = []
        summarize_features(
            windows,
            cache_dir=tmp_path,
            summarize_fn=lambda areas: (
                sent.extend(a["id"] for a in areas)
                or {a["id"]: "shared" for a in areas}
            ),
        )
        assert len(sent) == 1
        assert windows["1w"]["features"][0]["summary"] == "shared"
        assert windows["1m"]["features"][0]["summary"] == "shared"

    def test_empty_cached_summary_is_not_assigned(self, tmp_path):
        # A blank/corrupt cache entry must leave the area without a summary
        # rather than rendering an empty overview block.
        windows = self._windows(1)
        key = summary_cache_key("f0", ["D0"])
        (tmp_path / f"{key}.json").write_text(json.dumps({"summary": ""}))
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=None)
        assert "summary" not in windows["1w"]["features"][0]

    def test_non_dict_response_does_not_crash(self, tmp_path):
        stats = summarize_features(
            self._windows(2), cache_dir=tmp_path, summarize_fn=lambda areas: ["oops"]
        )
        assert stats["failed"] == 2 and stats["generated"] == 0

    def test_no_backend_makes_no_calls(self, tmp_path):
        stats = summarize_features(
            self._windows(3), cache_dir=tmp_path, summarize_fn=None
        )
        assert stats["failed"] == 0 and stats["generated"] == 0


class TestAsBatch:
    """Anthropic has no per-call preamble to amortize, so it keeps the
    simpler per-area implementation and is adapted to the batch contract."""

    def test_maps_each_area_through_the_per_area_fn(self):
        batch = as_batch(lambda label, patches: f"Overview of {label}")
        out = batch([_area("k1", "EME"), _area("k2", "Web Audio")])
        assert out == {"k1": "Overview of EME", "k2": "Overview of Web Audio"}

    def test_drops_areas_the_per_area_fn_declines(self):
        # A None from one area must not block the others in the batch.
        batch = as_batch(lambda label, patches: None if label == "EME" else "ok")
        assert batch([_area("k1", "EME"), _area("k2", "Other")]) == {"k2": "ok"}

    def test_empty_input(self):
        assert as_batch(lambda label, patches: "x")([]) == {}

    def test_one_raising_area_keeps_its_neighbours(self):
        # These are completed, already-paid-for calls. Letting one area's
        # exception escape would discard up to 11 real answers in the batch.
        def flaky(label, patches):
            if label == "Bad":
                raise RuntimeError("transient")
            return f"ok {label}"

        out = as_batch(flaky)([_area("k1", "A"), _area("k2", "Bad"),
                               _area("k3", "C")])
        assert out == {"k1": "ok A", "k3": "ok C"}
