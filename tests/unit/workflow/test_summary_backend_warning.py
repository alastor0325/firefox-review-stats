"""Tests for the dead-backend warning.

Motivation: GitHub Models was retired on 2026-07-30. The next weekly
refresh made ~35 inference calls, every one of them returned 410 Gone,
and the run still exited green — the missing overviews were only noticed
by looking at the published page. A total wipeout must be loud.
"""

from collections import Counter

from reviewstats.summarize import dead_backend_warning


def test_silent_when_everything_succeeded():
    stats = Counter(generated=12, reused=40, failed=0, calls=2, call_failures=0)
    assert dead_backend_warning(stats) is None


def test_silent_when_only_some_calls_failed():
    # One bad batch out of three self-heals next run — not worth a warning.
    stats = Counter(generated=10, reused=5, failed=2, calls=3, call_failures=1)
    assert dead_backend_warning(stats) is None


def test_warns_when_every_call_failed():
    stats = Counter(generated=0, reused=10, failed=19, calls=2, call_failures=2)
    warning = dead_backend_warning(stats)
    assert warning is not None
    assert "2 call" in warning   # judged on calls...
    assert "19" in warning       # ...but reports the area impact


def test_judged_on_calls_not_areas():
    # Batching means one failed call covers ~12 areas. Reading `failed` as
    # 12 independent failures would turn a single flaky invocation into a
    # "backend is broken" alarm, so a run with a surviving call stays quiet.
    stats = Counter(generated=12, reused=0, failed=12, calls=2, call_failures=1)
    assert dead_backend_warning(stats) is None


def test_silent_on_a_cache_only_run():
    # No backend configured: no calls were made, so nothing to judge.
    stats = Counter(generated=0, reused=10, failed=0, calls=0, call_failures=0)
    assert dead_backend_warning(stats) is None


def test_silent_on_an_empty_run():
    # A team with no commits contributes an empty Counter; missing keys
    # must not KeyError.
    assert dead_backend_warning(Counter()) is None
