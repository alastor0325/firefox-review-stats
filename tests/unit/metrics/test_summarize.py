"""Unit tests for the LLM summarization helpers (no network).

The Anthropic call itself is injected as `summarize_fn`, so these tests
never touch the SDK or the network.
"""

import json
import sys
import types
from types import SimpleNamespace

import pytest

from reviewstats.summarize import (
    build_summary_prompt,
    extract_summary_text,
    make_anthropic_summarizer,
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

    def test_none_fn_is_noop(self, tmp_path):
        windows = self._windows()
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=None)
        assert "summary" not in windows["1w"]["features"][0]

    def test_failed_summary_left_absent_and_uncached(self, tmp_path):
        windows = self._windows()
        summarize_features(windows, cache_dir=tmp_path, summarize_fn=lambda l, p: None)
        assert "summary" not in windows["1w"]["features"][0]
        assert not list(tmp_path.glob("*.json"))

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
