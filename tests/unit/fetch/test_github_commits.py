"""Tests for the GitHub-commits-API path of commit fetching.

We don't hit the network. Instead we mock `urllib.request.urlopen` and
`subprocess.run` (for `gh auth token`) and verify:

* the URL is correctly assembled with path + since + pagination
* pagination stops when the page count drops below the limit
* the API JSON is converted to our `Commit` dataclass cleanly
* `exclude_paths` subtracts commits by SHA
* commits filtered by `should_skip_commit` (Revert, Lando, merge) are dropped
"""

import io
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from reviewstats.github_commits import (
    _api_commit_to_commit,
    fetch_commits,
)


def _fake_api_commit(sha: str, author: str, date_iso: str, message: str) -> dict:
    return {
        "sha": sha,
        "commit": {
            "author": {"name": author, "date": date_iso},
            "message": message,
        },
    }


def _mk_response(payload):
    body = json.dumps(payload).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


class TestApiCommitToCommit:
    def test_basic_fields_extracted(self):
        api = _fake_api_commit(
            "abc123",
            "Alastor Wu",
            "2026-05-15T10:00:00Z",
            "Bug 1 - Foo. r=padenot\n\nDifferential Revision: https://phabricator.services.mozilla.com/D99999",
        )
        c = _api_commit_to_commit(api)
        assert c.sha == "abc123"
        assert c.author == "Alastor Wu"
        assert c.date == datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)
        assert c.subject.startswith("Bug 1 - Foo")
        assert c.differential_revision == "D99999"
        assert [r.name for r in c.reviewers] == ["padenot"]

    def test_subject_without_body(self):
        api = _fake_api_commit(
            "deadbeef",
            "X",
            "2026-05-15T10:00:00Z",
            "Bug 2 - Bar. r=alwu",  # no body, just subject
        )
        c = _api_commit_to_commit(api)
        assert c.subject.startswith("Bug 2 - Bar")
        assert c.differential_revision is None


class TestFetchCommits:
    @patch("reviewstats.github_commits._get_auth_token", return_value="tok")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_paginates_until_page_smaller_than_limit(self, urlopen, _):
        # Two pages: 100 items then 5 items → stop.
        page1 = [
            _fake_api_commit(f"sha{i}", "X", "2026-05-15T10:00:00Z",
                             f"Bug {i} - X. r=padenot")
            for i in range(100)
        ]
        page2 = [
            _fake_api_commit(f"shaB{i}", "X", "2026-05-15T10:00:00Z",
                             f"Bug 2{i} - X. r=padenot")
            for i in range(5)
        ]
        urlopen.side_effect = [_mk_response(page1), _mk_response(page2)]
        result = fetch_commits(
            repo="mozilla-firefox/firefox",
            path="dom/media",
            since="2025-11-15T00:00:00Z",
        )
        assert len(result) == 105
        assert urlopen.call_count == 2
        # Verify URL had path + since + pagination.
        first_url = urlopen.call_args_list[0].args[0].full_url
        assert "path=dom%2Fmedia" in first_url
        assert "since=2025-11-15T00%3A00%3A00Z" in first_url
        assert "per_page=100" in first_url
        assert "page=1" in first_url
        assert "page=2" in urlopen.call_args_list[1].args[0].full_url

    @patch("reviewstats.github_commits._get_auth_token", return_value="tok")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_excludes_by_subtracting_other_path(self, urlopen, _):
        included = [
            _fake_api_commit("sha-a", "X", "2026-05-15T10:00:00Z",
                             "Bug 1. r=padenot"),
            _fake_api_commit("sha-b", "X", "2026-05-15T10:00:00Z",
                             "Bug 2. r=padenot"),
            _fake_api_commit("sha-c", "X", "2026-05-15T10:00:00Z",
                             "Bug 3. r=padenot"),
        ]
        excluded = [
            _fake_api_commit("sha-b", "X", "2026-05-15T10:00:00Z",
                             "Bug 2. r=padenot"),  # also in webrtc subdir
        ]
        # First query returns included, second returns excluded.
        urlopen.side_effect = [_mk_response(included), _mk_response(excluded)]
        result = fetch_commits(
            repo="mozilla-firefox/firefox",
            path="dom/media",
            since="2025-11-15T00:00:00Z",
            exclude_paths=("dom/media/webrtc",),
        )
        shas = {c.sha for c in result}
        assert shas == {"sha-a", "sha-c"}

    @patch("reviewstats.github_commits._get_auth_token", return_value="tok")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_filters_revert_and_merge_via_should_skip(self, urlopen, _):
        commits = [
            _fake_api_commit("ok", "X", "2026-05-15T10:00:00Z",
                             "Bug 1. r=padenot"),
            _fake_api_commit("rev", "X", "2026-05-15T10:00:00Z",
                             'Revert "Bug 2. r=padenot" for causing bustage'),
            _fake_api_commit("mrg", "X", "2026-05-15T10:00:00Z",
                             "Merge autoland to mozilla-central"),
            _fake_api_commit("lan", "Lando", "2026-05-15T10:00:00Z",
                             "Bug 3 - x. r=padenot"),
        ]
        urlopen.return_value = _mk_response(commits)
        result = fetch_commits(
            repo="mozilla-firefox/firefox",
            path="dom/media",
            since="2025-11-15T00:00:00Z",
        )
        shas = {c.sha for c in result}
        assert shas == {"ok"}  # revert / merge / Lando-author all filtered


class TestFetchCommitsMultiPath:
    @patch("reviewstats.github_commits._get_auth_token", return_value="tok")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_paths_runs_one_query_per_path(self, urlopen, _):
        """Multi-path teams (WebRTC owns dom/media/webrtc +
        dom/media/systemservices) need one GitHub query per path —
        the API only filters by one `path` at a time."""
        page_a = [_fake_api_commit("sha-a", "X", "2026-05-15T10:00:00Z",
                                    "Bug 1. r=jib")]
        page_b = [_fake_api_commit("sha-b", "X", "2026-05-15T10:00:00Z",
                                    "Bug 2. r=jib")]
        urlopen.side_effect = [_mk_response(page_a), _mk_response(page_b)]
        result = fetch_commits(
            repo="mozilla-firefox/firefox",
            paths=("dom/media/webrtc", "dom/media/systemservices"),
            since="2025-11-15T00:00:00Z",
        )
        shas = {c.sha for c in result}
        assert shas == {"sha-a", "sha-b"}
        # One query per path.
        assert urlopen.call_count == 2
        first_url = urlopen.call_args_list[0].args[0].full_url
        second_url = urlopen.call_args_list[1].args[0].full_url
        assert "dom%2Fmedia%2Fwebrtc" in first_url
        assert "dom%2Fmedia%2Fsystemservices" in second_url

    @patch("reviewstats.github_commits._get_auth_token", return_value="tok")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_commit_touching_multiple_paths_appears_once(self, urlopen, _):
        """A commit touching dom/media/webrtc AND
        dom/media/systemservices is returned by both path queries —
        dedup by SHA so it's not double-counted."""
        page_a = [
            _fake_api_commit("sha-shared", "X", "2026-05-15T10:00:00Z",
                             "Bug 1. r=jib"),
            _fake_api_commit("sha-a-only", "X", "2026-05-15T10:00:00Z",
                             "Bug 2. r=jib"),
        ]
        page_b = [
            _fake_api_commit("sha-shared", "X", "2026-05-15T10:00:00Z",
                             "Bug 1. r=jib"),  # duplicate
            _fake_api_commit("sha-b-only", "X", "2026-05-15T10:00:00Z",
                             "Bug 3. r=jib"),
        ]
        urlopen.side_effect = [_mk_response(page_a), _mk_response(page_b)]
        result = fetch_commits(
            repo="mozilla-firefox/firefox",
            paths=("dom/media/webrtc", "dom/media/systemservices"),
            since="2025-11-15T00:00:00Z",
        )
        shas = [c.sha for c in result]
        assert shas.count("sha-shared") == 1
        assert set(shas) == {"sha-shared", "sha-a-only", "sha-b-only"}

    def test_requires_path_or_paths(self):
        """Forgetting both is a programming error, not a silent
        full-repo scan."""
        import pytest
        with pytest.raises(TypeError, match="path"):
            fetch_commits(
                repo="mozilla-firefox/firefox",
                since="2025-11-15T00:00:00Z",
            )
