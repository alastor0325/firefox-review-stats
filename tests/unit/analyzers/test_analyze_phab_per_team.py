"""Tests for the per-team Phab analyzer loop.

`_analyze_for_team` is the parallel of analyze_git.py's
`_generate_for_team` for Phab data — it owns one team's slice of
the wait-time pipeline and writes `<out>/<slug>/data_phab.json`.

We mock the network boundary (`fetch_commits`, the raw_data on
disk) and verify the loop produces the right output file shape for
both single-path and multi-path teams.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import analyze_phab
from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.teams import PLAYBACK_TEAM, WEBRTC_TEAM


def _fake_commit(d_number: str, author: str = "alwu") -> Commit:
    return Commit(
        sha=d_number.lower() * 4,  # fake sha
        date=datetime(2026, 5, 12, tzinfo=timezone.utc),
        author=author,
        subject=f"Bug 1 - thing. r=padenot,media-playback-reviewers",
        reviewers=[
            Reviewer("padenot", False),
            Reviewer("media-playback-reviewers", True),
        ],
        differential_revision=d_number,
    )


def _fake_raw(d_number: str, author: str = "alwu") -> dict:
    """A team-agnostic raw_data payload, simulating what
    parse_html_to_raw would have written for this revision."""
    return {
        "d_number": d_number,
        "author": author,
        "created_at": "2026-05-01T00:00:00+00:00",
        "events": [
            {"ts": "2026-05-01T00:00:00+00:00", "actor": author,
             "action": "create"},
            {"ts": "2026-05-02T00:00:00+00:00", "actor": author,
             "action": "add-reviewer",
             "target": "media-playback-reviewers"},
            {"ts": "2026-05-03T00:00:00+00:00", "actor": "padenot",
             "action": "comment"},
        ],
        "time_to_react_seconds": 2 * 86400,
        "time_to_accept_seconds": None,
    }


def _seed_raw_data(raw_dir: Path, d_numbers: list[str]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for d in d_numbers:
        (raw_dir / f"{d}.json").write_text(json.dumps(_fake_raw(d)))


def test_writes_data_phab_into_slug_subfolder(tmp_path: Path):
    """End-to-end: _analyze_for_team writes its single output file
    into <out>/<slug>/data_phab.json — same layout convention as
    analyze_git's per-team helper."""
    d_numbers = ["D1001", "D1002"]
    _seed_raw_data(tmp_path / "raw_data", d_numbers)

    commits = [_fake_commit(d) for d in d_numbers]

    with patch.object(analyze_phab, "_OUT_DIR", tmp_path), \
         patch.object(analyze_phab, "_RAW_DIR", tmp_path / "raw_data"), \
         patch.object(analyze_phab, "_HTML_CACHE_DIR",
                      tmp_path / ".phab_html_cache"), \
         patch.object(analyze_phab, "fetch_commits", return_value=commits):
        analyze_phab._analyze_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            concurrency=1,
            force=False,
            failures={},
        )

    out_path = tmp_path / "playback" / "data_phab.json"
    assert out_path.is_file(), "data_phab.json should live in <slug>/"
    # Nothing leaked to root.
    assert not (tmp_path / "data_phab.json").exists()


def test_output_includes_aggregated_wait_time_shape(tmp_path: Path):
    """The data_phab.json shape downstream renderers read from must
    be intact — n, percentiles, weekly_median, last_week, per_author,
    patch_list, meta."""
    d_numbers = ["D1001"]
    _seed_raw_data(tmp_path / "raw_data", d_numbers)

    with patch.object(analyze_phab, "_OUT_DIR", tmp_path), \
         patch.object(analyze_phab, "_RAW_DIR", tmp_path / "raw_data"), \
         patch.object(analyze_phab, "_HTML_CACHE_DIR",
                      tmp_path / ".phab_html_cache"), \
         patch.object(analyze_phab, "fetch_commits",
                      return_value=[_fake_commit("D1001")]):
        analyze_phab._analyze_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            concurrency=1,
            force=False,
            failures={},
        )

    data = json.loads(
        (tmp_path / "playback" / "data_phab.json").read_text()
    )
    # Top-level keys downstream renderers expect.
    for key in ("n", "histogram", "percentiles", "weekly_median",
                "last_week", "per_author", "patch_list", "meta"):
        assert key in data, f"data_phab.json missing top-level {key!r}"


def test_multi_path_team_runs_without_falling_back_to_singular_path(
    tmp_path: Path,
):
    """WebRTC has two paths — `_analyze_for_team` must call
    fetch_commits with `paths=team.paths`, not `path=`. Catches a
    future regression that downgrades multi-path to a single path."""
    captured = {}

    def fake_fetch(*, repo, paths=None, path=None, since, exclude_paths):
        captured["paths"] = paths
        captured["path"] = path
        return []

    with patch.object(analyze_phab, "_OUT_DIR", tmp_path), \
         patch.object(analyze_phab, "_RAW_DIR", tmp_path / "raw_data"), \
         patch.object(analyze_phab, "_HTML_CACHE_DIR",
                      tmp_path / ".phab_html_cache"), \
         patch.object(analyze_phab, "fetch_commits", side_effect=fake_fetch):
        analyze_phab._analyze_for_team(
            WEBRTC_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            concurrency=1,
            force=False,
            failures={},
        )

    assert captured["paths"] == WEBRTC_TEAM.paths, (
        "_analyze_for_team must pass `paths=team.paths` so WebRTC's "
        "two roots are both queried."
    )
    assert captured["path"] is None


def test_main_iterates_every_registered_team(tmp_path: Path):
    """main() calls _analyze_for_team once per team in the registry.
    Adding a third team later auto-extends the loop without further
    wiring."""
    calls: list[str] = []

    def fake_analyze(team, **_kwargs):
        calls.append(team.slug)

    with patch.object(analyze_phab, "_analyze_for_team",
                      side_effect=fake_analyze), \
         patch("sys.argv", ["analyze_phab.py"]):
        analyze_phab.main()

    from reviewstats.teams import TEAMS
    assert sorted(calls) == sorted(TEAMS.keys())
