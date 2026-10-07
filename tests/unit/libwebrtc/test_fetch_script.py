"""fetch_libwebrtc_status.py: the separate CI step that writes the libwebrtc view's
data. Upstream trouble must cost one week of freshness, never the build or
last week's table."""

import json

import fetch_libwebrtc_status as fls

VIEW = {"chrome_stable": 154, "as_of": "2026-10-05",
        "rows": [{"label": "Release", "firefox": "157.0.1", "milestone": 153,
                  "branch_head": "branch-heads/8010", "branched": "2026-08-17",
                  "vs_chrome": "1 behind", "patches": 150,
                  "last_change": None}]}


def test_defaults_to_the_webrtc_team():
    assert fls.build_parser().parse_args([]).team == "webrtc"


def test_writes_the_team_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fls, "collect", lambda previous: VIEW)
    assert fls.main(["--out", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "webrtc" / "data_libwebrtc.json").read_text()) == VIEW


def test_an_empty_result_does_not_overwrite_good_data(tmp_path, monkeypatch):
    path = tmp_path / "webrtc" / "data_libwebrtc.json"
    path.parent.mkdir()
    path.write_text(json.dumps(VIEW))
    monkeypatch.setattr(fls, "collect", lambda previous: {**VIEW, "rows": []})
    assert fls.main(["--out", str(tmp_path)]) == 1
    assert json.loads(path.read_text()) == VIEW


def test_a_failed_fetch_leaves_the_file_and_exits_nonzero(tmp_path, monkeypatch):
    path = tmp_path / "webrtc" / "data_libwebrtc.json"
    path.parent.mkdir()
    path.write_text(json.dumps(VIEW))

    def down(previous):
        raise OSError("gitiles down")
    monkeypatch.setattr(fls, "collect", down)
    assert fls.main(["--out", str(tmp_path)]) == 1
    assert json.loads(path.read_text()) == VIEW


def test_last_weeks_file_is_passed_on(tmp_path, monkeypatch):
    path = tmp_path / "webrtc" / "data_libwebrtc.json"
    path.parent.mkdir()
    path.write_text(json.dumps(VIEW))
    seen = []
    monkeypatch.setattr(fls, "collect", lambda previous: (seen.append(previous), VIEW)[1])
    fls.main(["--out", str(tmp_path)])
    assert seen == [VIEW]



def test_the_weekly_job_publishes_what_the_fetcher_writes():
    """The workflow commits each registered team's folder, so the fetcher's
    default team must be one of them or its file would never be published."""
    from reviewstats.teams import TEAMS
    assert fls.build_parser().parse_args([]).team in TEAMS


def test_failures_are_annotated_on_the_actions_run(tmp_path, monkeypatch, capsys):
    """The CI step is continue-on-error, so a failure must surface as an
    annotation on the run summary, not only as a log line."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    def down(previous):
        raise OSError("gitiles down")
    monkeypatch.setattr(fls, "collect", down)
    assert fls.main(["--out", str(tmp_path)]) == 1
    assert "::error title=libwebrtc fetch::" in capsys.readouterr().out


def test_section_fallbacks_are_warnings_on_the_actions_run(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    fls.report_fallback("plan", OSError("whattrainisitnow down"))
    out = capsys.readouterr().out
    assert out.startswith("::warning title=libwebrtc fetch::") and "plan" in out


def test_outside_actions_messages_go_to_stderr(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    fls.report_fallback("plan", OSError("down"))
    captured = capsys.readouterr()
    assert captured.out == "" and "plan" in captured.err


def test_annotation_text_is_escaped(monkeypatch, capsys):
    """Workflow commands end at a newline; %, CR and LF must be encoded or a
    multi-line exception truncates the annotation."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    fls.report_fallback("plan", OSError("50% down\nsecond line"))
    out = capsys.readouterr().out
    assert out.count("\n") == 1 and "50%25 down%0Asecond line" in out
