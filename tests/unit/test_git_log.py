from datetime import datetime, timezone

from reviewstats.git_log import Commit, parse_git_log_output


def _entry(h: str, dt: str, subject: str, body: str = "", author: str = "Some Author") -> str:
    return f"{h}\t{dt}\t{author}\t{subject}\n{body}\n\x1e\n"


class TestParseGitLogOutput:
    def test_single_commit(self):
        raw = _entry(
            "abc123",
            "2026-05-15T10:00:00+00:00",
            "Bug 123 - Fix thing. r=media-playback-reviewers,padenot",
            author="Alastor Wu",
        )
        commits = parse_git_log_output(raw)
        assert len(commits) == 1
        c = commits[0]
        assert c.sha == "abc123"
        assert c.date == datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)
        assert c.author == "Alastor Wu"
        assert c.subject.startswith("Bug 123")
        assert [r.name for r in c.reviewers] == [
            "media-playback-reviewers",
            "padenot",
        ]

    def test_multiple_commits(self):
        raw = _entry(
            "aaa",
            "2026-05-15T10:00:00+00:00",
            "Bug 1 - X. r=padenot",
        ) + _entry(
            "bbb",
            "2026-05-14T10:00:00+00:00",
            "Bug 2 - Y. r=alwu",
        )
        commits = parse_git_log_output(raw)
        assert len(commits) == 2
        assert commits[0].sha == "aaa"
        assert commits[1].sha == "bbb"

    def test_skips_lando_format_commit(self):
        raw = _entry(
            "ccc",
            "2026-05-15T10:00:00+00:00",
            "Bug 3: apply code formatting via Lando",
        ) + _entry(
            "ddd",
            "2026-05-15T11:00:00+00:00",
            "Bug 4 - Real fix. r=padenot",
        )
        commits = parse_git_log_output(raw)
        assert [c.sha for c in commits] == ["ddd"]

    def test_skips_lando_authored_commit(self):
        raw = _entry(
            "lll",
            "2026-05-15T10:00:00+00:00",
            "Bug 999 - some change. r=padenot",
            author="Lando",
        )
        assert parse_git_log_output(raw) == []

    def test_skips_revert_commit(self):
        raw = _entry(
            "rrr",
            "2026-05-15T10:00:00+00:00",
            'Revert "Bug 1 - X" for causing failures',
        )
        assert parse_git_log_output(raw) == []

    def test_skips_merge_commit(self):
        raw = _entry("eee", "2026-05-15T10:00:00+00:00", "Merge autoland to mozilla-central")
        assert parse_git_log_output(raw) == []

    def test_extracts_differential_revision(self):
        raw = _entry(
            "fff",
            "2026-05-15T10:00:00+00:00",
            "Bug 5 - Z. r=padenot",
            body="Differential Revision: https://phabricator.services.mozilla.com/D99999",
        )
        commits = parse_git_log_output(raw)
        assert commits[0].differential_revision == "D99999"

    def test_no_phab_link(self):
        raw = _entry(
            "ggg", "2026-05-15T10:00:00+00:00", "Bug 6 - Q. r=padenot"
        )
        assert parse_git_log_output(raw)[0].differential_revision is None


def test_commit_dataclass_shape():
    from reviewstats.parse import Reviewer

    c = Commit(
        sha="x",
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        author="A",
        subject="s",
        reviewers=[Reviewer("padenot", False)],
        differential_revision=None,
    )
    assert c.reviewers[0].name == "padenot"
