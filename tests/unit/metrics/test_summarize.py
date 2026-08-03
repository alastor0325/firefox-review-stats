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
    build_copilot_argv,
    build_copilot_prompt,
    build_summary_prompt,
    extract_copilot_text,
    extract_summary_text,
    make_anthropic_summarizer,
    make_copilot_summarizer,
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

        def fake(label, patches):
            calls.append(label)
            return f"Overview of {label}"

        windows = self._windows()
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=fake)
        assert windows["1m"]["features"][0]["summary"] == "Overview of EME"
        # Identical feature-set across 1w/1m → summarized once (memoized).
        assert calls == ["EME"]
        assert list(tmp_path.glob("*.json"))

    def test_uses_disk_cache(self, tmp_path):
        windows = self._windows()
        key = summary_cache_key("eme", ["D1"])
        (tmp_path / f"{key}.json").write_text(json.dumps({"summary": "cached"}))

        def boom(label, patches):
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
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=lambda l, p: None)
        assert "summary" not in windows["1w"]["features"][0]
        assert not list(tmp_path.glob("*.json"))

    def test_returns_counts(self, tmp_path):
        # Counts are returned (not just printed) so the caller can detect a
        # backend that is failing every call — the GitHub Models retirement
        # went unnoticed for a week because a 100% failure rate still
        # printed a line and exited green.
        windows = self._windows()
        stats = summarize_features(
            windows, cache_dir=tmp_path, summarize_fn=lambda l, p: None
        )
        assert stats == Counter(generated=0, reused=0, failed=1)

    def test_counts_are_summable_across_teams(self, tmp_path):
        # main() adds up one Counter per team, so + must work.
        a = summarize_features(
            self._windows(), cache_dir=tmp_path, summarize_fn=lambda l, p: "x"
        )
        b = summarize_features(
            self._windows(), cache_dir=tmp_path, summarize_fn=lambda l, p: "x"
        )
        assert (a + b)["generated"] + (a + b)["reused"] == 2

    def test_returns_counts_for_generated_and_reused(self, tmp_path):
        windows = self._windows()
        stats = summarize_features(
            windows, cache_dir=tmp_path, summarize_fn=lambda l, p: "text"
        )
        assert stats["generated"] == 1 and stats["failed"] == 0

    def test_corrupt_cache_entry_is_resummarized(self, tmp_path):
        # A garbage cache file is treated as a miss → summarize_fn runs and
        # overwrites it (rather than crashing or yielding no summary).
        windows = self._windows()
        key = summary_cache_key("eme", ["D1"])
        (tmp_path / f"{key}.json").write_text("{not json")

        summarize_features(
            windows, cache_dir=tmp_path, summarize_fn=lambda l, p: "fresh"
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


class TestBuildCopilotPrompt:
    def test_folds_system_and_user_into_one_prompt(self):
        # Copilot CLI takes a single prompt string — no system role — so the
        # system instructions must be carried inline.
        system, user = build_summary_prompt("EME", [_patch("a", subject="Fix X")])
        prompt = build_copilot_prompt("EME", [_patch("a", subject="Fix X")])
        assert system in prompt
        assert user in prompt
        assert "Fix X" in prompt


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
            return 0, "  Copilot overview.  ", ""

        fn = make_copilot_summarizer(model="claude-sonnet-4.5", run=run)
        assert fn("EME", [{"subject": "Fix X"}]) == "Copilot overview."
        assert seen["argv"][0] == "copilot"
        assert "Fix X" in seen["argv"][seen["argv"].index("-p") + 1]
        assert seen["timeout"] > 0

    def test_nonzero_exit_returns_none(self):
        fn = make_copilot_summarizer(
            run=lambda *a, **k: (1, "", "not authenticated")
        )
        assert fn("EME", [{"subject": "x"}]) is None

    def test_subprocess_raise_returns_none(self):
        def run(*a, **k):
            raise OSError("copilot: command not found")

        fn = make_copilot_summarizer(run=run)
        assert fn("EME", [{"subject": "x"}]) is None

    def test_empty_output_returns_none(self):
        # Blank stdout must not be cached as a valid (empty) overview.
        fn = make_copilot_summarizer(
            run=lambda *a, **k: (0, "   \n", "")
        )
        assert fn("EME", [{"subject": "x"}]) is None

    def test_runs_outside_the_repo_checkout(self, tmp_path):
        # The agent has tools enabled; keep its working directory away from
        # the checkout so it cannot wander into repo files.
        seen = {}

        def run(argv, *, cwd, timeout):
            seen["cwd"] = cwd
            return 0, "ok", ""

        fn = make_copilot_summarizer(run=run, workdir=str(tmp_path))
        fn("EME", [{"subject": "x"}])
        assert seen["cwd"] == str(tmp_path)
