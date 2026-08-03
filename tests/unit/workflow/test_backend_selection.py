"""Tests for summary-backend selection in analyze_git.main().

A misconfigured backend name must not fall through to the silent
cache-only path. That is the same invisible failure as a backend that
runs and fails every call (see test_summary_backend_warning.py) — just
entered through a different door: a typo, a rename, or the retired
`github` value left in an old environment.
"""

from collections import Counter
from unittest.mock import patch

import pytest

import analyze_git


@pytest.fixture
def stub_teams(tmp_path):
    """Run main() without touching the network or writing reports."""
    with patch.object(
        analyze_git, "_generate_for_team", side_effect=lambda *a, **k: Counter()
    ):
        yield


def _run(monkeypatch, capsys, tmp_path, backend):
    monkeypatch.setenv("REVIEW_STATS_SUMMARY_BACKEND", backend)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    analyze_git.main(["--out", str(tmp_path)])
    return capsys.readouterr().out


def test_unknown_backend_warns_loudly(monkeypatch, capsys, tmp_path, stub_teams):
    out = _run(monkeypatch, capsys, tmp_path, "copliot")  # typo
    assert "::warning" in out
    assert "copliot" in out


def test_retired_github_backend_warns(monkeypatch, capsys, tmp_path, stub_teams):
    # GitHub Models shut down 2026-07-30; the value is no longer valid.
    out = _run(monkeypatch, capsys, tmp_path, "github")
    assert "::warning" in out


def test_off_is_silent(monkeypatch, capsys, tmp_path, stub_teams):
    # Explicitly disabled is a deliberate choice, not a misconfiguration.
    assert "::warning" not in _run(monkeypatch, capsys, tmp_path, "off")


def test_unset_is_silent(monkeypatch, capsys, tmp_path, stub_teams):
    assert "::warning" not in _run(monkeypatch, capsys, tmp_path, "")


def test_copilot_backend_is_selected(monkeypatch, capsys, tmp_path, stub_teams):
    out = _run(monkeypatch, capsys, tmp_path, "copilot")
    assert "::warning" not in out
    assert "Copilot CLI" in out
