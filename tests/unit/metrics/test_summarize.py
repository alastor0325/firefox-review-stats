"""Unit tests for the LLM summarization helpers (no network).

The Anthropic call itself is injected as `summarize_fn`, so these tests
never touch the SDK or the network.
"""

import json
from types import SimpleNamespace

from reviewstats.summarize import (
    build_summary_prompt,
    extract_summary_text,
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
