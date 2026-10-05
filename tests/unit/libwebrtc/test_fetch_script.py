"""fetch_libwebrtc_status.py: the separate CI step that writes the card's
data. Upstream trouble must cost one week of freshness, never the build or
last week's table."""

import json

import fetch_libwebrtc_status as fls

VIEW = {"chrome_stable": 154, "as_of": "2026-10-05",
        "rows": [{"label": "Release", "firefox": "157.0.1", "milestone": 153,
                  "branch_head": "branch-heads/8010", "branched": "2026-08-17",
                  "age": "7 wk", "vs_chrome": "1 behind", "in_progress": False,
                  "last_change": None}]}


def test_defaults_to_the_webrtc_team():
    assert fls.build_parser().parse_args([]).team == "webrtc"


def test_writes_the_team_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fls, "collect", lambda known: VIEW)
    assert fls.main(["--out", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "webrtc" / "data_libwebrtc.json").read_text()) == VIEW


def test_an_empty_result_does_not_overwrite_good_data(tmp_path, monkeypatch):
    path = tmp_path / "webrtc" / "data_libwebrtc.json"
    path.parent.mkdir()
    path.write_text(json.dumps(VIEW))
    monkeypatch.setattr(fls, "collect", lambda known: {**VIEW, "rows": []})
    assert fls.main(["--out", str(tmp_path)]) == 1
    assert json.loads(path.read_text()) == VIEW


def test_a_failed_fetch_leaves_the_file_and_exits_nonzero(tmp_path, monkeypatch):
    path = tmp_path / "webrtc" / "data_libwebrtc.json"
    path.parent.mkdir()
    path.write_text(json.dumps(VIEW))

    def down(known):
        raise OSError("gitiles down")
    monkeypatch.setattr(fls, "collect", down)
    assert fls.main(["--out", str(tmp_path)]) == 1
    assert json.loads(path.read_text()) == VIEW


def test_last_weeks_branch_dates_are_passed_on(tmp_path, monkeypatch):
    path = tmp_path / "webrtc" / "data_libwebrtc.json"
    path.parent.mkdir()
    path.write_text(json.dumps(VIEW))
    seen = {}
    monkeypatch.setattr(fls, "collect", lambda known: (seen.update(known), VIEW)[1])
    fls.main(["--out", str(tmp_path)])
    assert seen == {153: "2026-08-17"}
