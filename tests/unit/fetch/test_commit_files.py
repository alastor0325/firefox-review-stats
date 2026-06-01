"""Tests for the single-commit file-list fetch + disk cache.

Network is mocked at the shared `github_http` layer. We verify:

* `fetch_commit_files` extracts the `files[].filename` array
* it inherits `github_http`'s retry on a transient 504 (the bug that
  motivated routing it through the shared helper)
* the disk cache short-circuits the network on a second call
"""

import json
import urllib.error
from unittest.mock import patch, MagicMock

from reviewstats.commit_files import fetch_commit_files, fetch_commit_files_cached


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://api.github.com/x", code, "boom", {}, None
    )


def _mk_response(payload):
    body = json.dumps(payload).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


_COMMIT = {
    "files": [
        {"filename": "dom/media/MediaDecoder.cpp"},
        {"filename": "dom/media/MediaDecoder.h"},
    ]
}


class TestFetchCommitFiles:
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_extracts_filenames(self, urlopen):
        urlopen.return_value = _mk_response(_COMMIT)
        files = fetch_commit_files("mozilla-firefox/firefox", "abc", token="t")
        assert files == [
            "dom/media/MediaDecoder.cpp",
            "dom/media/MediaDecoder.h",
        ]

    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_missing_files_array_yields_empty(self, urlopen):
        urlopen.return_value = _mk_response({})  # no "files" key
        assert fetch_commit_files("r", "sha", token=None) == []

    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_retries_transient_504(self, urlopen, sleep):
        urlopen.side_effect = [_http_error(504), _mk_response(_COMMIT)]
        files = fetch_commit_files("r", "sha", token=None)
        assert files == [
            "dom/media/MediaDecoder.cpp",
            "dom/media/MediaDecoder.h",
        ]
        assert urlopen.call_count == 2


class TestFetchCommitFilesCached:
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_second_call_hits_cache_not_network(self, urlopen, tmp_path):
        urlopen.return_value = _mk_response(_COMMIT)
        first = fetch_commit_files_cached(
            "r", "sha", cache_dir=tmp_path, token=None
        )
        second = fetch_commit_files_cached(
            "r", "sha", cache_dir=tmp_path, token=None
        )
        assert first == second
        assert urlopen.call_count == 1  # second call served from disk
