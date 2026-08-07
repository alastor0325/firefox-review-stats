"""Which teams get the Media Health view, and how the loader degrades.

The view is playback-only. That is expressed as a per-team capability plus a
data gate, not as a team-name check in the template: the loader returns None
whenever there is nothing to show, and the page removes the tab when the
payload is null.
"""

from pathlib import Path

import pytest

import analyze_git
from reviewstats.teams import TEAMS, get_team


class TestTeamCapability:
    def test_only_playback_has_a_roadmap(self):
        with_roadmap = sorted(t.slug for t in TEAMS.values() if t.has_roadmap)
        assert with_roadmap == ["playback"], (
            "Media Health is playback-only; if another team gains a roadmap "
            "that is a deliberate decision, not a default."
        )

    def test_has_roadmap_defaults_false(self):
        """A newly registered team must not silently acquire the view."""
        for slug in ("gfx", "webrtc"):
            assert get_team(slug).has_roadmap is False


class TestLoaderGate:
    def test_returns_none_for_a_team_without_a_roadmap(self, monkeypatch):
        monkeypatch.setenv("ROADMAP_YAML", "/nonexistent/roadmap.yaml")
        assert analyze_git._load_roadmap_view(
            get_team("gfx"), audience="internal"
        ) is None

    def test_returns_none_when_the_file_is_missing(self, monkeypatch, tmp_path):
        """A missing roadmap degrades to "no tab", never a failed build — the
        weekly refresh runs on a machine that may not have the investigation
        repo checked out."""
        monkeypatch.setenv("ROADMAP_YAML", str(tmp_path / "absent.yaml"))
        assert analyze_git._load_roadmap_view(
            get_team("playback"), audience="internal"
        ) is None

    def test_reads_and_projects_when_present(self, monkeypatch, tmp_path):
        yaml = pytest.importorskip("yaml")
        src = tmp_path / "roadmap.yaml"
        src.write_text(
            yaml.safe_dump(
                {
                    "updated": "2026-08-07",
                    "condition": {"summary": "s", "aspects": []},
                    "scopes": [],
                    "metrics": [],
                    "questions": [],
                    "closed": [],
                    "items": [
                        {
                            "id": "a", "scope": "reliability", "type": "MISSING",
                            "title": "t", "consequence": "c", "impact": "S1",
                            "reach": 4, "confidence": "high", "cost": "M",
                            "outcome_tags": ["PLATFORM"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("ROADMAP_YAML", str(src))
        view = analyze_git._load_roadmap_view(
            get_team("playback"), audience="internal"
        )
        assert view is not None
        assert view["counts"] == {
            "total": 1, "ranked": 1, "measure": 0, "continuous": 0
        }

    def test_env_var_overrides_the_default_path(self, monkeypatch, tmp_path):
        """The default points into a home directory, so CI and other machines
        must be able to redirect it."""
        monkeypatch.setenv("ROADMAP_YAML", str(tmp_path / "nope.yaml"))
        # Would have found the real file at the default path; the override
        # sends it somewhere empty instead.
        assert analyze_git._load_roadmap_view(
            get_team("playback"), audience="internal"
        ) is None

    def test_published_build_defaults_to_the_public_subset(self):
        """`<slug>/index.html` is git-tracked and the weekly workflow commits
        it, and `internal` output is a strict superset of `public`. So the
        default must be `public`: an internal default would publish exactly the
        fields the annotation exists to protect, and CI passes no flag."""
        import inspect

        sig = inspect.signature(analyze_git._generate_for_team)
        assert sig.parameters["roadmap_audience"].default == "public"

    def test_cli_default_is_public(self):
        """The weekly workflow runs `python analyze_git.py` with no audience
        flag, so this default is what actually gets published."""
        args = analyze_git.build_parser().parse_args([])
        assert args.roadmap_audience == "public"

    def test_cli_accepts_every_audience_the_library_does(self):
        """The choices list is derived from the library's AUDIENCES rather than
        restated, so the CLI cannot reject a value the model accepts."""
        from reviewstats.roadmap import AUDIENCES

        for audience in AUDIENCES:
            args = analyze_git.build_parser().parse_args(
                ["--roadmap-audience", audience]
            )
            assert args.roadmap_audience == audience

    def test_default_path_is_outside_this_repo(self):
        """The roadmap is hand-curated and slow-moving; the weekly refresh must
        read it, never own or regenerate it."""
        repo = Path(analyze_git.__file__).resolve().parent
        assert repo not in analyze_git.DEFAULT_ROADMAP_YAML.parents
