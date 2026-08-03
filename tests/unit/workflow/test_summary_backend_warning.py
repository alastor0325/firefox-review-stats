"""Tests for the dead-backend warning.

Motivation: GitHub Models was retired on 2026-07-30. The next weekly
refresh made ~35 inference calls, every one of them returned 410 Gone,
and the run still exited green — the missing overviews were only noticed
by looking at the published page. A total wipeout must be loud.
"""

from collections import Counter

from reviewstats.summarize import dead_backend_warning


def test_silent_when_everything_succeeded():
    stats = Counter(generated=12, reused=40, failed=0)
    assert dead_backend_warning(stats) is None


def test_silent_on_partial_failure():
    # A few flaky areas self-heal next run — not worth a warning.
    stats = Counter(generated=10, reused=5, failed=2)
    assert dead_backend_warning(stats) is None


def test_warns_when_every_call_failed():
    stats = Counter(generated=0, reused=10, failed=19)
    warning = dead_backend_warning(stats)
    assert warning is not None
    assert "19" in warning


def test_silent_on_a_cache_only_run():
    # No backend configured: nothing generated, but nothing failed either.
    # `failed` is only incremented when a backend is actually invoked, so
    # this can never be mistaken for a dead backend.
    stats = Counter(generated=0, reused=10, failed=0)
    assert dead_backend_warning(stats) is None


def test_silent_on_an_empty_run():
    # A team with no commits contributes an empty Counter; missing keys
    # must not KeyError.
    assert dead_backend_warning(Counter()) is None
