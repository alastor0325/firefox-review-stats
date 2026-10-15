"""Unit tests for naming what caused a flagged recent shift.

A mozilla-central push is a merge of many autoland pushes, so the shift's own
first run cannot name a bug. Perfherder alerts on the autoland twin series can:
each alert summary carries a push range (narrowed by sheriff backfills) and,
once triaged, a linked bug. The pure half -- choosing the alert, and deciding
whether its range is narrow enough to name a bug -- is tested directly; the
fetcher's I/O wrapper is tested with every request mocked.
"""

from reviewstats.perfcause import (
    alert_redirect,
    bugs_in_pushes,
    describe_cause,
    select_alert,
)

DAY = 86400
T = 1_791_855_702


def _summary(sid=1, ts=T, status=0, bug=None, alerts=None, **kw):
    return {"id": sid, "push_timestamp": ts, "status": status,
            "bug_number": bug, "repository": "autoland",
            "revision": "62134d3c511273a73624a31f0bdaa23b0033f168",
            "push_id": 20, "prev_push_id": 10,
            "alerts": alerts if alerts is not None else [_alert()], **kw}


def _alert(sig=99, regression=False, status=0, related=None):
    return {"series_signature": {"id": sig}, "is_regression": regression,
            "status": status, "related_summary_id": related}


def _url_only(route):
    """`_get` is called with a timeout; the routes only care about the URL."""
    return lambda url, **kw: route(url)


def _push(*subjects):
    return {"revisions": [{"comments": s + "\n\nbody"} for s in subjects]}


class TestSelectAlert:
    def test_matching_alert_is_chosen(self):
        s = _summary()
        assert select_alert([s], signature_id=99, improved=True,
                            near_ts=T + 8 * 3600) == (s, s["alerts"][0])

    def test_other_signatures_are_ignored(self):
        assert select_alert([_summary(alerts=[_alert(sig=1)])], signature_id=99,
                            improved=True, near_ts=T) is None

    def test_direction_must_match(self):
        """An improvement must not be explained by a regression alert."""
        assert select_alert([_summary()], signature_id=99, improved=False,
                            near_ts=T) is None

    def test_invalid_alerts_and_summaries_are_skipped(self):
        assert select_alert([_summary(status=3)], signature_id=99,
                            improved=True, near_ts=T) is None
        assert select_alert([_summary(alerts=[_alert(status=3)])],
                            signature_id=99, improved=True, near_ts=T) is None

    def test_an_alert_far_from_the_shift_is_not_the_cause(self):
        assert select_alert([_summary(ts=T - 10 * DAY)], signature_id=99,
                            improved=True, near_ts=T) is None
        assert select_alert([_summary(ts=T + 2 * DAY)], signature_id=99,
                            improved=True, near_ts=T) is None

    def test_the_closest_of_several_wins(self):
        far, near = _summary(sid=1, ts=T - 3 * DAY), _summary(sid=2, ts=T - 3600)
        s, _ = select_alert([far, near], signature_id=99, improved=True,
                            near_ts=T)
        assert s["id"] == 2

    def test_empty_input(self):
        assert select_alert([], signature_id=99, improved=True, near_ts=T) is None
        assert select_alert(None, signature_id=99, improved=True,
                            near_ts=T) is None


class TestAlertRedirect:
    def test_reassigned_and_downstream_point_at_the_real_summary(self):
        assert alert_redirect(_alert(status=2, related=7)) == 7
        assert alert_redirect(_alert(status=1, related=7)) == 7

    def test_others_do_not(self):
        assert alert_redirect(_alert(status=0, related=7)) is None
        assert alert_redirect(_alert(status=2, related=None)) is None


class TestBugsInPushes:
    def test_bug_numbers_in_order_without_repeats(self):
        pushes = [_push("Bug 2 - Part 2. r=x", "Bug 2 - Part 1. r=x"),
                  _push("Bug 1: thing r=y")]
        assert bugs_in_pushes(pushes) == [2, 1]

    def test_backouts_still_count(self):
        """A backout changes the build as much as a landing does."""
        assert bugs_in_pushes([_push('Revert "Bug 5 - x" for failures')]) == [5]

    def test_only_the_subject_line_is_read(self):
        """Bodies mention other bugs in passing; the subject names the change."""
        assert bugs_in_pushes([{"revisions": [
            {"comments": "No Bug, HSTS update\n\nsee bug 9"}]}]) == []


class TestDescribeCause:
    def test_a_single_push_with_one_bug_names_it(self):
        s = _summary(bug=None)
        c = describe_cause(s, s["alerts"][0],
                           [_push("Bug 2080876 - Part 2", "Bug 2080876 - Part 1")])
        assert c["bug_id"] == 2080876
        assert c["bug_source"] == "push"
        assert c["push_count"] == 1
        assert c["alert_id"] == 1
        assert c["alert_url"].endswith("perfherder/alerts?id=1")
        assert c["revision"] == "62134d3c5112"
        assert c["status"] == "untriaged"

    def test_a_wide_range_names_no_bug(self):
        """Forty pushes: the alert's own push is only where the test happened to
        run, so naming its bug would blame the wrong change."""
        s = _summary()
        c = describe_cause(s, s["alerts"][0],
                           [_push(f"Bug {n} - x") for n in range(40)])
        assert c["bug_id"] is None
        assert c["push_count"] == 40

    def test_a_sheriff_linked_bug_is_used_when_the_range_is_wide(self):
        s = _summary(bug=777)
        c = describe_cause(s, s["alerts"][0],
                           [_push("Bug 1 - x"), _push("Bug 2 - y")])
        assert c["bug_id"] == 777
        assert c["bug_source"] == "alert"

    def test_the_push_beats_the_alert_link_when_it_is_one_push(self):
        """For a regression the linked bug is often the tracking bug sheriffs
        filed; a one-push range names the landing itself."""
        s = _summary(bug=777)
        c = describe_cause(s, s["alerts"][0], [_push("Bug 5 - x")])
        assert (c["bug_id"], c["bug_source"]) == (5, "push")

    def test_one_push_with_two_bugs_falls_back(self):
        s = _summary(bug=None)
        c = describe_cause(s, s["alerts"][0], [_push("Bug 5 - x", "Bug 6 - y")])
        assert c["bug_id"] is None

    def test_a_capped_range_says_so(self):
        s = _summary()
        c = describe_cause(s, s["alerts"][0], [_push("x")] * 3, push_cap=3)
        assert c["push_count_capped"] is True

    def test_a_push_sourced_bug_is_the_landing(self):
        s = _summary(alerts=[_alert(regression=True)])
        c = describe_cause(s, s["alerts"][0], [_push("Bug 5 - x")])
        assert c["bug_role"] == "landing"

    def test_a_linked_bug_on_a_regression_is_the_tracker(self):
        s = _summary(bug=777, alerts=[_alert(regression=True)])
        c = describe_cause(s, s["alerts"][0], [_push("a"), _push("b")])
        assert c["bug_role"] == "tracker"

    def test_a_linked_bug_on_an_improvement_is_the_landing(self):
        s = _summary(bug=777)
        c = describe_cause(s, s["alerts"][0], [_push("a"), _push("b")])
        assert c["bug_role"] == "landing"

    def test_no_bug_has_no_role(self):
        s = _summary()
        assert describe_cause(s, s["alerts"][0], [])["bug_role"] is None

    def test_bugzilla_fields_default_to_empty(self):
        s = _summary()
        c = describe_cause(s, s["alerts"][0], [])
        assert c["bug_summary"] is None and c["regressed_by"] == []
        assert c["bug_state"] is None and c["accepted"] is False


class TestAcceptedMove:
    """A tracker closed WONTFIX means the move was explained and accepted, not
    left broken -- the AV1 encode regression was exactly that."""

    def test_a_wontfix_tracker_is_accepted(self):
        from reviewstats.perfcause import accepted_move
        assert accepted_move("tracker", "WONTFIX") is True

    def test_an_open_or_fixed_tracker_is_not(self):
        from reviewstats.perfcause import accepted_move
        assert accepted_move("tracker", "NEW") is False
        assert accepted_move("tracker", "FIXED") is False

    def test_a_landing_never_is(self):
        """A landing closed WONTFIX says nothing about this move."""
        from reviewstats.perfcause import accepted_move
        assert accepted_move("landing", "WONTFIX") is False
        assert accepted_move(None, None) is False


class TestResolveCauseInTheFetcher:
    """The I/O wrapper: autoland twin by signature hash, its alerts, the push
    range, the bug title. Every request is mocked; a failure anywhere must
    leave the card without a cause rather than fail the fetch."""

    def _fpm(self):
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm_cause", pathlib.Path("fetch_perf_metrics.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["fpm_cause"] = m
        spec.loader.exec_module(m)
        return m

    SHIFT = {"improved": True, "first_ts": T + 8 * 3600}

    def _routes(self, url):
        if "/project/autoland/performance/signatures/" in url:
            return {"5929950": {"id": 5929950, "signature_hash": "abc"}}
        if "alertsummary/?alerts__series_signature=5929950" in url:
            return {"results": [_summary(alerts=[_alert(sig=5929950)],
                                         bug=2080876)]}
        if "/project/autoland/push/" in url:
            assert "id__gt=10" in url and "id__lte=20" in url
            return {"results": [_push("Bug 2080876 - Part 2",
                                      "Bug 2080876 - Part 1")]}
        if "bugzilla.mozilla.org/rest/bug" in url:
            return {"bugs": [{"id": 2080876, "summary": "Prime video fails",
                              "status": "RESOLVED", "resolution": "FIXED"}]}
        raise AssertionError(url)

    def test_happy_path_names_the_bug_and_its_title(self, monkeypatch):
        m = self._fpm()
        monkeypatch.setattr(m, "_get", _url_only(self._routes))
        c = m.resolve_cause("abc", self.SHIFT)
        assert c["bug_id"] == 2080876
        assert c["bug_summary"] == "Prime video fails"
        assert c["bug_state"] == "FIXED"
        assert c["accepted"] is False, "an improvement's landing is never 'accepted'"
        assert c["push_count"] == 1

    def test_a_moved_alert_follows_to_its_new_summary(self, monkeypatch):
        m = self._fpm()

        def routes(url):
            if "alertsummary/?alerts__series_signature=" in url:
                return {"results": [_summary(
                    sid=1, alerts=[_alert(sig=5929950, status=2, related=8)])]}
            if "alertsummary/?id=8" in url:
                return {"results": [_summary(sid=8, bug=4242)]}
            return self._routes(url)
        monkeypatch.setattr(m, "_get", _url_only(routes))
        c = m.resolve_cause("abc", self.SHIFT)
        assert c["alert_id"] == 8

    def test_a_restricted_bug_keeps_its_number_without_a_title(self, monkeypatch):
        m = self._fpm()

        def routes(url):
            if "bugzilla" in url:
                return {"bugs": []}
            return self._routes(url)
        monkeypatch.setattr(m, "_get", _url_only(routes))
        c = m.resolve_cause("abc", self.SHIFT)
        assert c["bug_id"] == 2080876 and c["bug_summary"] is None

    def test_a_failing_bugzilla_still_keeps_the_alert(self, monkeypatch):
        import urllib.error
        m = self._fpm()

        def routes(url):
            if "bugzilla" in url:
                raise urllib.error.URLError("down")
            return self._routes(url)
        monkeypatch.setattr(m, "_get", _url_only(routes))
        c = m.resolve_cause("abc", self.SHIFT)
        assert c["alert_id"] == 1 and c["bug_summary"] is None

    def test_a_failing_treeherder_yields_no_cause(self, monkeypatch):
        import urllib.error
        m = self._fpm()

        def boom(url):
            raise urllib.error.URLError("down")
        monkeypatch.setattr(m, "_get", _url_only(boom))
        assert m.resolve_cause("abc", self.SHIFT) is None

    def test_a_tracking_bug_follows_regressed_by_to_the_culprit(self, monkeypatch):
        """For a regression the linked bug is the one sheriffs filed; the
        landing that caused it is its `regressed_by`, once they know it."""
        m = self._fpm()

        def routes(url):
            if "bugzilla" in url and "id=2080876" in url:
                return {"bugs": [{"id": 2080876, "summary": "tracker",
                                  "status": "RESOLVED", "resolution": "WONTFIX",
                                  "regressed_by": [2051892]}]}
            if "bugzilla" in url and "id=2051892" in url:
                return {"bugs": [{"id": 2051892, "summary": "precise timers",
                                  "status": "RESOLVED", "resolution": "FIXED"}]}
            if "/project/autoland/push/" in url:
                return {"results": [_push("Bug 1 - a"), _push("Bug 2 - b")]}
            return self._routes(url)
        def regression(url):
            if "alertsummary/?alerts__series_signature=" in url:
                return {"results": [_summary(
                    alerts=[_alert(sig=5929950, regression=True)], bug=2080876)]}
            return routes(url)
        monkeypatch.setattr(m, "_get", _url_only(regression))
        c = m.resolve_cause("abc",
                            {"improved": False, "first_ts": T + 8 * 3600})
        assert c["bug_source"] == "alert"
        assert c["regressed_by"] == [{"id": 2051892, "summary": "precise timers",
                                      "state": "FIXED"}]
        assert c["bug_state"] == "WONTFIX" and c["accepted"] is True

    def test_an_improvement_does_not_follow_regressed_by(self, monkeypatch):
        """For an improvement the linked bug is the landing itself, and its
        regressed_by is whatever that fix repaired -- not this move. Following
        it pinned the 2026-10-13 speed-up on the bug it fixed."""
        m = self._fpm()

        def routes(url):
            if "bugzilla" in url and "id=2080876" in url:
                return {"bugs": [{"id": 2080876, "summary": "the fix",
                                  "regressed_by": [2051510]}]}
            if "bugzilla" in url:
                raise AssertionError("regressed_by must not be fetched")
            if "/project/autoland/push/" in url:
                return {"results": [_push("Bug 1 - a"), _push("Bug 2 - b")]}
            return self._routes(url)
        monkeypatch.setattr(m, "_get", _url_only(routes))
        c = m.resolve_cause("abc", self.SHIFT)
        assert c["bug_id"] == 2080876 and c["regressed_by"] == []

    def test_no_regressed_by_is_an_empty_list(self, monkeypatch):
        m = self._fpm()
        monkeypatch.setattr(m, "_get", _url_only(self._routes))
        assert m.resolve_cause("abc", self.SHIFT)["regressed_by"] == []

    def test_no_first_run_means_no_lookup(self, monkeypatch):
        m = self._fpm()
        def no_request(url):
            raise AssertionError("no request expected")
        monkeypatch.setattr(m, "_get", _url_only(no_request))
        assert m.resolve_cause("abc", {"improved": True, "first_ts": None}) is None

    def test_no_twin_or_no_alert_yields_no_cause(self, monkeypatch):
        m = self._fpm()

        def routes(url):
            if "alertsummary" in url:
                return {"results": []}
            return self._routes(url)
        monkeypatch.setattr(m, "_get", _url_only(routes))
        assert m.resolve_cause("abc", self.SHIFT) is None
        assert m.resolve_cause("unknown", self.SHIFT) is None
