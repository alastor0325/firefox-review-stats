"""Tests for the per-team analyzer-output layout.

Each registered team's report lives in `<out>/<slug>/`:

    <out>/playback/data_git.json
    <out>/playback/data_phab.json
    <out>/playback/index.html
    <out>/webrtc/...

raw_data/ and the on-disk caches stay flat at <out> — they're
keyed by SHA / D-number and reuse across teams is the whole point
of keeping them shared.

These tests exercise the layout helpers + the analyzer's
loop-over-TEAMS structure without hitting the network.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import analyze_git
from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.teams import PLAYBACK_TEAM, WEBRTC_TEAM


def _commit(sha: str = "a" * 40) -> Commit:
    return Commit(
        sha=sha,
        date=datetime(2026, 5, 12, tzinfo=timezone.utc),
        author="Alastor Wu",
        subject="Bug 1 - x. r=padenot,media-playback-reviewers",
        reviewers=[
            Reviewer("padenot", False),
            Reviewer("media-playback-reviewers", True),
        ],
        differential_revision="D9999",
    )


def test_generate_for_team_writes_into_slug_subfolder(tmp_path: Path):
    """The per-team helper creates <out>/<slug>/ and writes both
    data_git.json and index.html into it — the entire shape of the
    new layout in one assertion."""
    # `bad_commits` is empty (the commit tags the group), but the
    # recent-changes feed fetches a file list for every recent landing,
    # so stub fetch_commit_files_cached to stay offline.
    with patch.object(analyze_git, "fetch_commits", return_value=[_commit()]), \
        patch.object(
            analyze_git, "fetch_commit_files_cached",
            return_value=["dom/media/eme/foo.cpp"],
        ):
        analyze_git._generate_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            out_dir=tmp_path,
            cache_dir=tmp_path / ".commit_files_cache",
            archive_week=False,
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
    assert (tmp_path / "playback" / "data_git.json").is_file()
    assert (tmp_path / "playback" / "index.html").is_file()
    # Nothing leaked into the root.
    assert not (tmp_path / "data_git.json").exists()
    assert not (tmp_path / "index.html").exists()


def test_generate_for_team_no_commits_short_circuits(tmp_path: Path):
    """When fetch_commits returns nothing, the helper logs and exits
    without producing any output (which would otherwise be an empty
    report with broken percentile math)."""
    with patch.object(analyze_git, "fetch_commits", return_value=[]):
        analyze_git._generate_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            out_dir=tmp_path,
            cache_dir=tmp_path / ".commit_files_cache",
            archive_week=False,
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
    assert not (tmp_path / "playback").exists()


def test_generate_for_team_meta_carries_paths_list(tmp_path: Path):
    """meta.paths in the per-team data_git.json mirrors the team's
    paths tuple — drives the page-header 'watching ...' clause."""
    with patch.object(analyze_git, "fetch_commits", return_value=[_commit()]), \
        patch.object(
            analyze_git, "fetch_commit_files_cached",
            return_value=["dom/media/eme/foo.cpp"],
        ):
        analyze_git._generate_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            out_dir=tmp_path,
            cache_dir=tmp_path / ".commit_files_cache",
            archive_week=False,
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
    data = json.loads((tmp_path / "playback" / "data_git.json").read_text())
    assert data["meta"]["paths"] == ["dom/media"]
    # Singular `path` field kept for older consumers.
    assert data["meta"]["path"] == "dom/media"


def test_generate_for_team_emits_recent_changes(tmp_path: Path):
    """The recent-changes feed reaches data_git.json, bucketed into a
    feature area derived from the commit's primary subdirectory."""
    with patch.object(analyze_git, "fetch_commits", return_value=[_commit()]), \
        patch.object(
            analyze_git, "fetch_commit_files_cached",
            return_value=["dom/media/eme/foo.cpp"],
        ):
        analyze_git._generate_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            out_dir=tmp_path,
            cache_dir=tmp_path / ".commit_files_cache",
            archive_week=False,
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
    data = json.loads((tmp_path / "playback" / "data_git.json").read_text())
    assert "recent_changes" in data
    month = data["recent_changes"]["1m"]
    assert month["total"] == 1
    assert month["features"][0]["feature"] == "eme"
    # Display title is cleaned of both the r=… tag and the "Bug NNNN -" prefix.
    assert month["features"][0]["patches"][0]["subject"] == "x."


def test_generate_for_team_attaches_feature_summaries(tmp_path: Path):
    """When a summarize_fn is supplied, each recent-change feature area
    gets a 'what we did' overview in data_git.json."""
    with patch.object(analyze_git, "fetch_commits", return_value=[_commit()]), \
        patch.object(
            analyze_git, "fetch_commit_files_cached",
            return_value=["dom/media/eme/foo.cpp"],
        ):
        analyze_git._generate_for_team(
            PLAYBACK_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            out_dir=tmp_path,
            cache_dir=tmp_path / ".commit_files_cache",
            archive_week=False,
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
            summarize_fn=lambda label, patches: f"Overview of {label}",
        )
    data = json.loads((tmp_path / "playback" / "data_git.json").read_text())
    feature = data["recent_changes"]["1m"]["features"][0]
    assert feature["summary"] == f"Overview of {feature['label']}"


def test_multiroot_team_recent_feed_buckets_one_level_deep(tmp_path: Path):
    """A multi-root team (webrtc) buckets its Recent Changes feed one level
    under the owned root — so feature areas are meaningful (e.g.
    dom/media/webrtc/transport) rather than the whole root."""
    with patch.object(analyze_git, "fetch_commits", return_value=[_commit()]), \
        patch.object(
            analyze_git, "fetch_commit_files_cached",
            return_value=["dom/media/webrtc/transport/Foo.cpp"],
        ):
        analyze_git._generate_for_team(
            WEBRTC_TEAM,
            repo="mozilla-firefox/firefox",
            since="2026-05-01T00:00:00Z",
            out_dir=tmp_path,
            cache_dir=tmp_path / ".commit_files_cache",
            archive_week=False,
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
    data = json.loads((tmp_path / "webrtc" / "data_git.json").read_text())
    feature = data["recent_changes"]["1m"]["features"][0]
    assert feature["feature"] == "dom/media/webrtc/transport"
    assert feature["label"] == "Connection transport (ICE / DTLS)"


def test_main_iterates_every_registered_team(tmp_path: Path):
    """main() must visit every team in the registry — the GH Action
    output is the union of all team subfolders. Verified by spying
    on _generate_for_team and asserting one call per registered
    team."""
    call_count = {"n": 0}

    def fake_gen(team, **_kwargs):
        call_count["n"] += 1

    with patch.object(analyze_git, "_generate_for_team", side_effect=fake_gen):
        analyze_git.main(["--out", str(tmp_path)])

    from reviewstats.teams import TEAMS
    assert call_count["n"] == len(TEAMS)
