"""The libwebrtc card is WebRTC-only by data, like the Metrics subview:
fetch_libwebrtc_status.py writes webrtc/data_libwebrtc.json, and a page
renders the card only when its team directory has that file."""

import json
from pathlib import Path

import analyze_git
from reviewstats.render import render_html
from reviewstats.teams import TEAMS
from tests.unit.render.test_sticky_layout import _MINIMAL_DATA

VIEW = {"chrome_stable": 154, "as_of": "2026-10-05", "rows": []}


def test_reads_the_team_file_when_present(tmp_path):
    (tmp_path / "data_libwebrtc.json").write_text(json.dumps(VIEW))
    assert analyze_git._read_libwebrtc_view(tmp_path) == VIEW


def test_none_without_the_file(tmp_path):
    assert analyze_git._read_libwebrtc_view(tmp_path) is None


def test_reading_applies_the_whitelist(tmp_path):
    (tmp_path / "data_libwebrtc.json").write_text(
        json.dumps({**VIEW, "missing_fixes": ["chromium:1"]}))
    assert "missing_fixes" not in analyze_git._read_libwebrtc_view(tmp_path)


def test_unreadable_file_omits_the_card(tmp_path):
    (tmp_path / "data_libwebrtc.json").write_text("{not json")
    assert analyze_git._read_libwebrtc_view(tmp_path) is None


def test_only_the_webrtc_folder_carries_the_data():
    root = Path(analyze_git.__file__).resolve().parent
    have = sorted(s for s in TEAMS if (root / s / "data_libwebrtc.json").exists())
    assert have in ([], ["webrtc"])


def test_page_embeds_the_payload_or_null():
    assert "const LIBWEBRTC = null;" in render_html(_MINIMAL_DATA)
    html = render_html(_MINIMAL_DATA, libwebrtc_data=VIEW)
    assert "const LIBWEBRTC = {" in html
    assert 'id="libwebrtc-section"' in html
    assert "__LIBWEBRTC_DATA_JSON__" not in html
