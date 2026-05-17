"""`select_fetch_targets` must never re-fetch a revision we already
have data for. These tests pin that contract — if anyone accidentally
loosens it, weekly refreshes would balloon back to ~520 Playwright
fetches instead of the ~10 they should be.
"""

from pathlib import Path

from analyze_phab import select_fetch_targets


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")


class TestSelectFetchTargets:
    def test_all_missing_go_to_fetch(self, tmp_path):
        raw = tmp_path / "raw"
        html = tmp_path / "html"
        skip, from_cache, to_fetch = select_fetch_targets(
            ["D1", "D2", "D3"], raw_dir=raw, html_cache_dir=html,
        )
        assert skip == []
        assert from_cache == []
        assert to_fetch == ["D1", "D2", "D3"]

    def test_existing_raw_data_is_skipped(self, tmp_path):
        raw = tmp_path / "raw"
        html = tmp_path / "html"
        _touch(raw / "D1.json")
        _touch(raw / "D3.json")
        skip, from_cache, to_fetch = select_fetch_targets(
            ["D1", "D2", "D3", "D4"],
            raw_dir=raw, html_cache_dir=html,
        )
        # D1 and D3 already have raw_data — must not be fetched again.
        assert set(skip) == {"D1", "D3"}
        assert from_cache == []
        assert set(to_fetch) == {"D2", "D4"}

    def test_html_cached_goes_to_reparse_not_fetch(self, tmp_path):
        raw = tmp_path / "raw"
        html = tmp_path / "html"
        # raw_data missing, HTML cached — should re-parse, NOT re-fetch.
        _touch(html / "D1.html")
        skip, from_cache, to_fetch = select_fetch_targets(
            ["D1", "D2"], raw_dir=raw, html_cache_dir=html,
        )
        assert skip == []
        assert from_cache == ["D1"]
        assert to_fetch == ["D2"]

    def test_force_bypasses_raw_data_skip(self, tmp_path):
        raw = tmp_path / "raw"
        html = tmp_path / "html"
        _touch(raw / "D1.json")
        _touch(raw / "D2.json")
        _touch(html / "D1.html")  # cached
        skip, from_cache, to_fetch = select_fetch_targets(
            ["D1", "D2"], raw_dir=raw, html_cache_dir=html, force=True,
        )
        # With force, raw_data presence is ignored. HTML cache still
        # avoids the network for D1; D2 still needs Playwright.
        assert skip == []
        assert from_cache == ["D1"]
        assert to_fetch == ["D2"]

    def test_weekly_refresh_scenario(self, tmp_path):
        """End-to-end realistic case: 500 already-fetched revisions
        and 5 new ones from the latest week. Only the 5 should be
        Playwright candidates."""
        raw = tmp_path / "raw"
        html = tmp_path / "html"
        existing = [f"D{i}" for i in range(1000, 1500)]
        new = [f"D{i}" for i in range(2000, 2005)]
        for d in existing:
            _touch(raw / f"{d}.json")
            _touch(html / f"{d}.html")
        skip, from_cache, to_fetch = select_fetch_targets(
            existing + new, raw_dir=raw, html_cache_dir=html,
        )
        assert len(skip) == 500, (
            "weekly refresh must skip every already-cached revision"
        )
        assert from_cache == []
        assert to_fetch == new, "only the genuinely new ones get fetched"

    def test_empty_input(self, tmp_path):
        skip, from_cache, to_fetch = select_fetch_targets(
            [], raw_dir=tmp_path / "raw", html_cache_dir=tmp_path / "html",
        )
        assert skip == from_cache == to_fetch == []
