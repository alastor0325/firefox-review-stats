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
            "total": 1, "ranked": 1, "needs_measuring": 0
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


class TestCiCanRenderTheRoadmapWithoutThePrivateSource:
    """The weekly action cannot see roadmap.yaml, and that would delete the view.

    The authoring file lives in a separate private repo
    (~/firefox-bug-investigation). The workflow never checks it out and never sets
    ROADMAP_YAML, so `_load_roadmap_view` returns None, the Media Health tab is
    hidden, and the regenerated index.html -- which the job then commits --
    silently loses the whole view. Verified in a browser: the tab button exists in
    the markup but has no offsetParent, and zero roadmap rows render.

    So the public projection is committed as a data file. That exposes nothing new:
    it is byte-for-byte what was already embedded in the published index.html. The
    YAML stays private and stays the source of truth; this is the fallback CI reads.
    """

    def test_the_generator_writes_the_public_projection(self):
        import pathlib
        src = pathlib.Path("analyze_git.py").read_text(encoding="utf-8")
        assert "data_roadmap.json" in src, (
            "nothing persists the roadmap for a run that cannot see the YAML"
        )

    def test_only_the_public_projection_is_ever_written(self):
        """Committing the internal projection would publish every withheld field.

        Scoped to the *write* site. `data_roadmap.json` appears three times -- the
        fallback read, its log line, and the write -- and an earlier version of this
        test matched the first, so it proved nothing about the gate.
        """
        import pathlib, re
        lines = pathlib.Path("analyze_git.py").read_text(
            encoding="utf-8").splitlines()
        write = [n for n, ln in enumerate(lines)
                 if "data_roadmap.json" in ln and "write_text" in "".join(
                     lines[max(0, n - 1):n + 2])]
        assert write, "nothing writes data_roadmap.json"
        block = "\n".join(lines[max(0, write[0] - 8):write[0] + 3])
        assert re.search(r'audience\s*==\s*"public"', block), (
            "the write is not gated on the public audience: an "
            "--roadmap-audience internal run would commit withheld fields\n"
            + block
        )

    def test_the_fallback_is_used_when_the_yaml_is_absent(self, tmp_path,
                                                          monkeypatch):
        import json, sys
        sys.path.insert(0, ".")
        import analyze_git
        from reviewstats.teams import TEAMS

        team_dir = tmp_path / "playback"
        team_dir.mkdir()
        (team_dir / "data_roadmap.json").write_text(json.dumps({
            "items": [{"id": "x", "title": "t", "churn": "LEAVES",
                       "needs_measuring": False, "withheld": []}],
            "counts": {"total": 1, "ranked": 1, "needs_measuring": 0},
            "aspects": [], "metrics": [], "audience": "public",
        }), encoding="utf-8")
        monkeypatch.setenv("ROADMAP_YAML", str(tmp_path / "absent.yaml"))
        view = analyze_git._load_roadmap_view(
            TEAMS["playback"], audience="public", team_dir=team_dir)
        assert view is not None, "the committed projection was not used"
        assert view["counts"]["total"] == 1

    def test_a_missing_yaml_and_no_fallback_still_degrades_quietly(
            self, tmp_path, monkeypatch):
        import sys
        sys.path.insert(0, ".")
        import analyze_git
        from reviewstats.teams import TEAMS
        monkeypatch.setenv("ROADMAP_YAML", str(tmp_path / "absent.yaml"))
        d = tmp_path / "empty"
        d.mkdir()
        assert analyze_git._load_roadmap_view(
            TEAMS["playback"], audience="public", team_dir=d) is None
