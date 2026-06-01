"""Tests for the shared GitHub HTTP helper (auth + retry/backoff).

We never hit the network: `urllib.request.urlopen` and `time.sleep` are
mocked. We verify:

* transient errors (5xx / 429 / URLError / timeout) are classified as
  retryable; client errors (4xx) and unrelated exceptions are not
* `backoff_seconds` grows exponentially from a 1-based attempt number
* `get_json` retries transient failures, gives up after `_MAX_ATTEMPTS`,
  and does not retry non-retryable errors
* the request carries the GitHub Accept header and (when given) the token
"""

import json
import urllib.error
from unittest.mock import patch, MagicMock

import pytest

from reviewstats.github_http import (
    _MAX_ATTEMPTS,
    backoff_seconds,
    get_json,
    is_retryable_error,
)


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


class TestIsRetryableError:
    @pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
    def test_transient_status_codes_are_retryable(self, code):
        assert is_retryable_error(_http_error(code)) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_client_errors_are_not_retryable(self, code):
        assert is_retryable_error(_http_error(code)) is False

    def test_url_error_and_timeout_are_retryable(self):
        assert is_retryable_error(urllib.error.URLError("conn reset")) is True
        assert is_retryable_error(TimeoutError("timed out")) is True

    def test_unrelated_exception_is_not_retryable(self):
        assert is_retryable_error(ValueError("nope")) is False


class TestBackoffSeconds:
    def test_exponential_growth_one_based(self):
        assert backoff_seconds(1) == 1.0
        assert backoff_seconds(2) == 2.0
        assert backoff_seconds(3) == 4.0
        assert backoff_seconds(4) == 8.0


class TestGetJson:
    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_returns_decoded_json_on_success(self, urlopen, sleep):
        urlopen.return_value = _mk_response({"hello": "world"})
        assert get_json("https://api.github.com/x") == {"hello": "world"}
        assert urlopen.call_count == 1
        assert sleep.call_count == 0

    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_sends_accept_and_auth_headers(self, urlopen, sleep):
        urlopen.return_value = _mk_response([])
        get_json("https://api.github.com/x", token="tok")
        req = urlopen.call_args.args[0]
        # urllib normalises header keys to title-case.
        assert req.get_header("Accept") == "application/vnd.github+json"
        assert req.get_header("Authorization") == "token tok"

    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_omits_auth_header_without_token(self, urlopen, sleep):
        urlopen.return_value = _mk_response([])
        get_json("https://api.github.com/x")
        req = urlopen.call_args.args[0]
        assert req.get_header("Authorization") is None

    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_retries_transient_504_then_succeeds(self, urlopen, sleep):
        urlopen.side_effect = [_http_error(504), _mk_response({"ok": 1})]
        assert get_json("https://api.github.com/x") == {"ok": 1}
        assert urlopen.call_count == 2
        assert sleep.call_count == 1  # backed off once before the retry

    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_gives_up_after_max_attempts(self, urlopen, sleep):
        urlopen.side_effect = _http_error(504)
        with pytest.raises(urllib.error.HTTPError):
            get_json("https://api.github.com/x")
        assert urlopen.call_count == _MAX_ATTEMPTS
        assert sleep.call_count == _MAX_ATTEMPTS - 1

    @patch("reviewstats.github_http.time.sleep")
    @patch("reviewstats.github_http.urllib.request.urlopen")
    def test_does_not_retry_non_retryable_error(self, urlopen, sleep):
        urlopen.side_effect = _http_error(404)
        with pytest.raises(urllib.error.HTTPError):
            get_json("https://api.github.com/x")
        assert urlopen.call_count == 1
        assert sleep.call_count == 0
