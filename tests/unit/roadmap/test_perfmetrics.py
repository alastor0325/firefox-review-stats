"""Unit tests for the cross-browser metric comparison behind the Metrics subview.

The numbers come from Perfherder; this module is the pure layer that turns raw
per-signature samples into something a reader can compare. Three things carry the
weight:

  * **Direction.** Some metrics are better lower (latency), some better higher
    (score). Perfherder's `lower_is_better` is `None` on most signatures, so
    direction is declared in our own config. Getting it wrong inverts the chart.
  * **Unequal samples.** Firefox runs far more often than Chrome (75 vs 13 over
    30 days), so `n` travels with every summary rather than being averaged away.
  * **Duplicate signatures.** The same (browser, suite, test) can have several
    signature ids differing by build options; blending them would mix builds.
"""

import pytest

from reviewstats.perfmetrics import (
    build_metrics_view,
    compare_to_firefox,
    graph_url,
    matches_test,
    pick_signature,
    select_recent_window,
    summarize,
)


class TestSummarize:
    def test_reports_n_median_and_quartiles(self):
        s = summarize([10, 20, 30, 40, 50])
        assert s["n"] == 5
        assert s["median"] == 30
        assert s["p25"] <= s["median"] <= s["p75"]

    def test_cv_is_a_percentage(self):
        s = summarize([100, 100, 100, 100])
        assert s["cv"] == 0.0
        noisy = summarize([50, 100, 150, 200])
        assert noisy["cv"] > 30

    def test_single_sample_has_no_spread(self):
        s = summarize([42])
        assert s == {"n": 1, "median": 42.0, "p25": 42.0, "p75": 42.0, "cv": 0.0}

    def test_empty_series_is_none_not_zero(self):
        """Zero would plot as a real measurement at the origin."""
        assert summarize([]) is None

    def test_ignores_missing_values(self):
        assert summarize([10, None, 20])["n"] == 2


class TestCompareToFirefox:
    """`advantage` is how many times better Firefox is: above 1 ahead, below 1
    behind. Expressing it that way means one number works for both directions."""

    def test_lower_is_better_firefox_faster_is_ahead(self):
        c = compare_to_firefox(160.0, {"chrome": 288.0}, lower_is_better=True)
        assert c["ahead"] is True
        assert c["factor"] == pytest.approx(1.8, abs=0.01)
        assert c["versus"] == "chrome"

    def test_lower_is_better_firefox_slower_is_behind(self):
        c = compare_to_firefox(288.0, {"chrome": 160.0}, lower_is_better=True)
        assert c["ahead"] is False
        assert c["factor"] == pytest.approx(1.8, abs=0.01)

    def test_higher_is_better_firefox_lower_is_behind(self):
        c = compare_to_firefox(96.0, {"chrome": 316.0}, lower_is_better=False)
        assert c["ahead"] is False
        assert c["factor"] == pytest.approx(3.29, abs=0.01)

    def test_higher_is_better_firefox_higher_is_ahead(self):
        c = compare_to_firefox(316.0, {"chrome": 96.0}, lower_is_better=False)
        assert c["ahead"] is True
        assert c["factor"] == pytest.approx(3.29, abs=0.01)

    def test_compares_against_the_strongest_rival(self):
        """Not the average: 'we are behind Chrome' is the fact that matters, and
        averaging in a weaker browser would flatter us."""
        c = compare_to_firefox(
            96.0, {"chrome": 316.0, "safari": 112.0}, lower_is_better=False
        )
        assert c["versus"] == "chrome"
        assert c["factor"] == pytest.approx(3.29, abs=0.01)

    def test_strongest_rival_respects_direction(self):
        c = compare_to_firefox(
            160.0, {"chrome": 288.0, "safari": 200.0}, lower_is_better=True
        )
        assert c["versus"] == "safari", "lowest wins when lower is better"

    def test_no_rival_is_reported_not_faked(self):
        """media-seek is Firefox-only today. It must read as 'not compared',
        never as a win."""
        c = compare_to_firefox(15.0, {}, lower_is_better=True)
        assert c["ahead"] is None
        assert c["factor"] is None
        assert c["versus"] is None

    def test_zero_firefox_value_does_not_divide_by_zero(self):
        c = compare_to_firefox(0.0, {"chrome": 100.0}, lower_is_better=True)
        assert c["factor"] is None


class TestPickSignature:
    """Several signature ids can share a (browser, suite, test); they differ by
    build options. Blending them would mix builds, so one is chosen."""

    def test_prefers_the_signature_with_most_samples(self):
        got = pick_signature([
            {"id": 1, "samples": [1, 2]},
            {"id": 2, "samples": [1, 2, 3, 4]},
        ])
        assert got["id"] == 2

    def test_ties_break_on_lowest_id_for_determinism(self):
        got = pick_signature([
            {"id": 9, "samples": [1, 2]},
            {"id": 3, "samples": [3, 4]},
        ])
        assert got["id"] == 3

    def test_ignores_signatures_with_no_samples(self):
        got = pick_signature([{"id": 1, "samples": []}, {"id": 2, "samples": [5]}])
        assert got["id"] == 2

    def test_all_empty_yields_nothing(self):
        assert pick_signature([{"id": 1, "samples": []}]) is None

    def test_empty_input_yields_nothing(self):
        assert pick_signature([]) is None


def raw(**kw):
    """Shape the fetcher writes to disk."""
    base = {
        "generated_at": "2026-08-10T00:00:00Z",
        "window_days": 30,
        "metrics": [{
            "id": "vpl.h264",
            "title": "First frame · H.264",
            "group": "First frame latency",
            "unit": "ms",
            "lower_is_better": True,
            "platform": "macosx1470-64-shippable",
            "note": "",
            "series": {
                "firefox": {"n": 75, "median": 160.0, "p25": 160.0,
                            "p75": 161.8, "cv": 1.6},
                "chrome": {"n": 13, "median": 288.0, "p25": 281.4,
                           "p75": 302.3, "cv": 4.3},
            },
        }],
        "coverage": {
            "browsers": ["firefox", "chrome", "safari", "custom-car"],
            "rows": [{"suite": "vpl", "measured": ["firefox", "chrome"],
                      "note": ""}],
        },
    }
    base.update(kw)
    return base


class TestBuildMetricsView:
    def test_carries_the_window_so_the_page_can_state_it(self):
        v = build_metrics_view(raw())
        assert v["window_days"] == 30
        assert v["generated_at"].startswith("2026-08-10")

    def test_attaches_a_comparison_to_each_metric(self):
        v = build_metrics_view(raw())
        m = v["metrics"][0]
        assert m["comparison"]["ahead"] is True
        assert m["comparison"]["factor"] == pytest.approx(1.8, abs=0.01)

    def test_firefox_only_metric_is_flagged_not_dropped(self):
        r = raw()
        r["metrics"][0]["series"].pop("chrome")
        v = build_metrics_view(r)
        m = v["metrics"][0]
        assert m["comparison"]["ahead"] is None
        assert m["compared"] is False

    def test_metric_with_no_firefox_data_is_dropped(self):
        """The whole view is 'where Firefox stands', so a row without us has
        nothing to say."""
        r = raw()
        r["metrics"][0]["series"].pop("firefox")
        v = build_metrics_view(r)
        assert v["metrics"] == []

    def test_axis_max_covers_every_series(self):
        """Bars are drawn against a shared scale per metric group, so the
        maximum has to include the slowest browser or its bar overflows."""
        v = build_metrics_view(raw())
        assert v["metrics"][0]["axis_max"] >= 302.3

    def test_groups_preserve_metric_order(self):
        r = raw()
        r["metrics"].append(dict(r["metrics"][0], id="vpl.vp9",
                                 title="First frame · VP9"))
        v = build_metrics_view(r)
        assert [g["title"] for g in v["groups"]] == ["First frame latency"]
        assert len(v["groups"][0]["metrics"]) == 2

    def test_summary_is_sorted_worst_first(self):
        """The page leads with where we are behind, matching how the roadmap
        orders its cards."""
        r = raw()
        r["metrics"].append({
            "id": "webaudio", "title": "Web Audio score", "group": "Web Audio",
            "unit": "score", "lower_is_better": False,
            "platform": "macosx1470-64-shippable", "note": "",
            "series": {
                "firefox": {"n": 75, "median": 96.0, "p25": 93.0, "p75": 97.0,
                            "cv": 7.1},
                "chrome": {"n": 13, "median": 316.0, "p25": 306.5,
                           "p75": 402.5, "cv": 14.3},
            },
        })
        v = build_metrics_view(r)
        assert v["summary"][0]["id"] == "webaudio", "behind must come first"
        assert v["summary"][0]["comparison"]["ahead"] is False

    def test_uncompared_metrics_sort_last_in_the_summary(self):
        r = raw()
        r["metrics"].append({
            "id": "media-seek.cold", "title": "Seek · cold", "group": "Seek",
            "unit": "ms", "lower_is_better": True,
            "platform": "macosx1470-64-shippable", "note": "",
            "series": {"firefox": {"n": 75, "median": 15.0, "p25": 14.3,
                                   "p75": 19.1, "cv": 22.5}},
        })
        v = build_metrics_view(r)
        assert v["summary"][-1]["id"] == "media-seek.cold"

    def test_coverage_is_carried_through(self):
        v = build_metrics_view(raw())
        assert v["coverage"]["browsers"][0] == "firefox"
        assert v["coverage"]["rows"][0]["measured"] == ["firefox", "chrome"]

    def test_counts_what_can_and_cannot_be_compared(self):
        r = raw()
        r["metrics"].append({
            "id": "media-seek.cold", "title": "Seek · cold", "group": "Seek",
            "unit": "ms", "lower_is_better": True, "platform": "p", "note": "",
            "series": {"firefox": {"n": 75, "median": 15.0, "p25": 14.3,
                                   "p75": 19.1, "cv": 22.5}},
        })
        v = build_metrics_view(r)
        assert v["counts"] == {"total": 2, "compared": 1, "firefox_only": 1}

    def test_noisy_series_is_marked(self):
        """A 23% run-to-run spread is louder than most differences worth
        detecting, so it is called out rather than plotted silently."""
        r = raw()
        r["metrics"][0]["series"]["firefox"]["cv"] = 22.5
        v = build_metrics_view(r)
        assert v["metrics"][0]["noisy"] is True

    def test_tight_series_is_not_marked(self):
        v = build_metrics_view(raw())
        assert v["metrics"][0]["noisy"] is False


class TestRivalCount:
    """Comparing against the strongest rival hides that others were measured,
    unless the count travels with it. Web Audio has both Chrome and Safari; the
    row names only Chrome."""

    def test_counts_every_measured_rival(self):
        c = compare_to_firefox(
            96.0, {"chrome": 316.0, "safari": 112.0}, lower_is_better=False
        )
        assert c["rival_count"] == 2
        assert c["versus"] == "chrome"

    def test_single_rival_counts_one(self):
        c = compare_to_firefox(160.0, {"chrome": 288.0}, lower_is_better=True)
        assert c["rival_count"] == 1

    def test_no_rivals_counts_zero(self):
        assert compare_to_firefox(15.0, {}, lower_is_better=True)["rival_count"] == 0


class TestStaleMetrics:
    """A suite that has stopped producing must not silently borrow the page's
    window. ve-* (WebCodecs encode) had zero samples in 30 days and real data at
    180, so the row has to say which window it used."""

    def _doc(self):
        r = raw()
        r["metrics"][0].update({"window_days": 30, "stale": True,
                                "days_behind": 150,
                                "window_end": "2026-03-14"})
        return r

    def test_window_length_stays_the_page_default(self):
        """Only the window's position slides, so medians remain like-for-like."""
        v = build_metrics_view(self._doc())
        assert v["metrics"][0]["window_days"] == 30

    def test_stale_flag_is_carried(self):
        v = build_metrics_view(self._doc())
        assert v["metrics"][0]["stale"] is True

    def test_window_end_and_lag_are_carried(self):
        v = build_metrics_view(self._doc())
        assert v["metrics"][0]["window_end"] == "2026-03-14"
        assert v["metrics"][0]["days_behind"] == 150

    def test_fresh_metric_is_not_marked_stale(self):
        v = build_metrics_view(raw())
        assert v["metrics"][0]["stale"] is False


class TestSelectRecentWindow:
    """A suite that has stopped producing gets the most recent 30-day window that
    has data, not a widened one. Fixed length keeps medians like-for-like; only
    the window's position moves, and the caller reports how far behind it is."""

    DAY = 86400

    def _pts(self, *offsets_days, base=1_800_000_000):
        return [{"value": 10.0 + i, "push_timestamp": base - int(d * self.DAY)}
                for i, d in enumerate(offsets_days)]

    def test_takes_everything_inside_the_window(self):
        now = 1_800_000_000
        w = select_recent_window(self._pts(0, 5, 10, 20), days=30, now_ts=now)
        assert len(w["values"]) == 4
        assert w["days_behind"] == 0

    def test_excludes_samples_older_than_the_window(self):
        now = 1_800_000_000
        w = select_recent_window(self._pts(0, 10, 45, 90), days=30, now_ts=now)
        assert len(w["values"]) == 2, "45 and 90 days back fall outside"

    def test_window_is_anchored_to_the_newest_sample_not_to_now(self):
        """The point of the whole function: a suite last seen 5 months ago still
        gets a 30-day window, just an old one."""
        now = 1_800_000_000
        pts = self._pts(150, 155, 160, 200)   # nothing recent at all
        w = select_recent_window(pts, days=30, now_ts=now)
        assert len(w["values"]) == 3, "150/155/160 are within 30d of each other"
        assert w["days_behind"] == 150

    def test_window_length_is_constant_regardless_of_staleness(self):
        now = 1_800_000_000
        fresh = select_recent_window(self._pts(0, 29), days=30, now_ts=now)
        stale = select_recent_window(self._pts(200, 229), days=30, now_ts=now)
        assert (fresh["window_end"] - fresh["window_start"]
                == stale["window_end"] - stale["window_start"])

    def test_reports_how_far_behind_the_window_ends(self):
        now = 1_800_000_000
        w = select_recent_window(self._pts(42), days=30, now_ts=now)
        assert w["days_behind"] == 42

    def test_no_points_reports_nothing_rather_than_zero(self):
        w = select_recent_window([], days=30, now_ts=1_800_000_000)
        assert w["values"] == []
        assert w["window_end"] is None
        assert w["days_behind"] is None

    def test_ignores_points_without_a_timestamp_or_value(self):
        now = 1_800_000_000
        pts = [{"value": 1.0, "push_timestamp": now},
               {"value": None, "push_timestamp": now},
               {"value": 2.0}]
        w = select_recent_window(pts, days=30, now_ts=now)
        assert w["values"] == [1.0]


class TestGraphUrl:
    """Each card links to Perfherder's graph for the exact series it charted, so
    a reader can check the numbers rather than take them on trust."""

    def test_one_link_covers_every_browser_on_the_metric(self):
        u = graph_url({"firefox": {"signature_id": 111},
                       "chrome": {"signature_id": 222}}, days=30)
        assert "series=mozilla-central,111,1,13" in u
        assert "series=mozilla-central,222,1,13" in u

    def test_series_are_ordered_so_the_url_is_stable(self):
        a = graph_url({"firefox": {"signature_id": 222},
                       "chrome": {"signature_id": 111}}, days=30)
        b = graph_url({"chrome": {"signature_id": 111},
                       "firefox": {"signature_id": 222}}, days=30)
        assert a == b

    def test_timerange_matches_the_window(self):
        assert "timerange=2592000" in graph_url(
            {"firefox": {"signature_id": 1}}, days=30)

    def test_timerange_snaps_up_to_an_allowed_value(self):
        """Perfherder only accepts a fixed set of ranges, and it must round UP:
        rounding down would clip the window and show an incomplete graph."""
        u = graph_url({"firefox": {"signature_id": 1}}, days=45)
        assert "timerange=5184000" in u   # 60d, the next allowed value up

    def test_timerange_covers_the_lag_for_a_stale_metric(self):
        """The bug this guards: Perfherder counts back from now, not from the
        window we charted. ve-* was 100 days stale on a 30-day window and its
        link opened an empty graph, which reads as fabricated data."""
        u = graph_url({"firefox": {"signature_id": 1}}, days=30, days_behind=100)
        assert "timerange=31536000" in u, (
            "130 days back needs the 365-day range; 90 days would still be empty"
        )

    def test_fresh_metric_keeps_the_tight_range(self):
        u = graph_url({"firefox": {"signature_id": 1}}, days=30, days_behind=0)
        assert "timerange=2592000" in u

    def test_lag_beyond_every_allowed_range_uses_the_largest(self):
        u = graph_url({"firefox": {"signature_id": 1}}, days=30, days_behind=900)
        assert "timerange=31536000" in u

    def test_stale_metric_url_is_built_from_the_metric_itself(self):
        r = raw()
        r["metrics"][0]["series"]["firefox"]["signature_id"] = 7
        r["metrics"][0].update({"days_behind": 100, "stale": True})
        v = build_metrics_view(r)
        assert "timerange=31536000" in v["metrics"][0]["graph_url"]

    def test_no_link_when_no_signature_is_known(self):
        """A dead 'see the data' link is worse than no link."""
        assert graph_url({"firefox": {"median": 1.0}}, days=30) == ""
        assert graph_url({}, days=30) == ""

    def test_metric_carries_its_graph_url(self):
        r = raw()
        r["metrics"][0]["series"]["firefox"]["signature_id"] = 999
        v = build_metrics_view(r)
        assert "999" in v["metrics"][0]["graph_url"]


class TestTheWeeklyRefreshKeepsMetricsHonest:
    """The metrics were refreshed by hand and by nothing else.

    `fetch_perf_metrics.py` appeared in no workflow, so `data_metrics.json` only
    moved when someone ran it locally. The page showed its date, which reads as
    provenance rather than as a warning, so a fetcher that quietly stopped running
    would look like a fresh page with old numbers.
    """

    def test_the_weekly_workflow_fetches_metrics(self):
        import pathlib
        wf = pathlib.Path(".github/workflows/refresh.yml").read_text(
            encoding="utf-8")
        assert "fetch_perf_metrics.py" in wf, (
            "nothing refreshes the Metrics subview on a schedule"
        )

    def test_metrics_are_fetched_before_the_page_is_generated(self):
        """analyze_git.py reads data_metrics.json off disk, so fetching after it
        would publish the previous week's numbers.

        Compares the `run:` lines, not any mention: the file names also appear in
        comments earlier in the workflow, and matching those passed while the real
        order was wrong.
        """
        import pathlib
        lines = pathlib.Path(".github/workflows/refresh.yml").read_text(
            encoding="utf-8").splitlines()
        def step(cmd):
            for i, ln in enumerate(lines):
                if ln.strip().startswith("run:") and cmd in ln:
                    return i
            raise AssertionError(f"no step runs {cmd}")
        assert step("fetch_perf_metrics.py") < step("analyze_git.py")

    def test_a_perfherder_outage_does_not_fail_the_weekly_build(self):
        """The report is mostly review data; losing one panel must not lose all of
        it. The fetcher already leaves the old file alone and exits 1, so the step
        has to tolerate that exit."""
        import pathlib
        wf = pathlib.Path(".github/workflows/refresh.yml").read_text(
            encoding="utf-8")
        i = wf.index("fetch_perf_metrics.py")
        window = wf[max(0, i - 400):i + 200]
        assert "continue-on-error: true" in window, window

    def test_the_probe_workflow_runs_rarely_not_weekly(self):
        """Codec support moves in release cycles, and the job needs a macOS runner
        plus three browser installs. Weekly would be waste."""
        import pathlib
        wf = pathlib.Path(".github/workflows/media-caps.yml").read_text(
            encoding="utf-8")
        cron = [l for l in wf.splitlines() if "cron:" in l][0]
        # Month field must not be '*': that would be monthly or more often.
        fields = cron.split("'")[1].split()
        assert fields[3] != "*", f"runs every month or oftener: {cron.strip()}"


class TestEmptyResultsDoNotOverwriteGoodData:
    """A successful fetch that finds nothing must not blank the subview.

    The network failure path was handled -- leave the file, exit 1 -- but a
    response with zero usable signatures took the success path and wrote an empty
    metrics file over a good one. Perfherder renaming a suite is enough to cause
    that, and it is how the Metrics subview would silently empty out.
    """

    def test_an_empty_fetch_is_refused_when_data_already_exists(self):
        from reviewstats.perfmetrics import is_safe_to_write
        ok, why = is_safe_to_write(new_count=0, existing_count=10)
        assert not ok and "empty" in why.lower()

    def test_an_empty_fetch_is_allowed_on_a_first_run(self):
        from reviewstats.perfmetrics import is_safe_to_write
        ok, _ = is_safe_to_write(new_count=0, existing_count=0)
        assert ok

    def test_a_normal_fetch_is_allowed(self):
        from reviewstats.perfmetrics import is_safe_to_write
        ok, _ = is_safe_to_write(new_count=10, existing_count=10)
        assert ok

    def test_a_large_drop_is_refused_as_well(self):
        """Ten metrics becoming one is not a refresh, it is a broken query."""
        from reviewstats.perfmetrics import is_safe_to_write
        ok, why = is_safe_to_write(new_count=1, existing_count=10)
        assert not ok and "fewer" in why.lower()

    def test_a_modest_drop_is_allowed(self):
        from reviewstats.perfmetrics import is_safe_to_write
        ok, _ = is_safe_to_write(new_count=9, existing_count=10)
        assert ok


class TestCapabilityQueryLatencyIsCharted:
    """The media-capabilities Raptor suite is charted.

    It was missing because it did not exist when the metric table was written: the
    suite started producing data on 2026-08-06. It is Firefox-only, like media-seek,
    and it measures how long `decodingInfo()` takes rather than what it answers -
    which is the natural companion to the support matrix on the same page.
    """

    def _entries(self):
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm", pathlib.Path("fetch_perf_metrics.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["fpm"] = m
        spec.loader.exec_module(m)
        return [e for e in m.METRICS if e["suite"] == "media-capabilities"]

    def test_the_suite_is_present(self):
        assert self._entries(), "media-capabilities is not charted"

    def test_it_has_its_own_group(self):
        groups = {e["group"] for e in self._entries()}
        assert groups == {"Capability query latency"}, groups

    def test_cold_and_hot_are_both_charted_for_one_codec(self):
        """The gap between them is the finding: a first query costs far more than a
        repeat, and a reader cannot see that from one number."""
        tests = {e["test"] for e in self._entries()}
        assert "decode-file-video-avc-cold" in tests
        assert "decode-file-video-avc-hot" in tests

    def test_more_than_one_surface_is_charted(self):
        """Plain file, Media Source and Worker answers differ for the same codec."""
        tests = {e["test"] for e in self._entries()}
        assert any("media-source" in t for t in tests)
        assert any(t.startswith("worker-") for t in tests)

    def test_every_entry_declares_direction_and_unit(self):
        """lower_is_better is None on most Perfherder signatures, so it is declared
        locally or a chart silently inverts."""
        for e in self._entries():
            assert e["lower_is_better"] is True, e["id"]
            assert e["unit"] == "ms", e["id"]

    def test_the_cold_outlier_carries_its_caveat(self):
        """H.264's cold query measures far above the other codecs. Whether that is
        H.264 or one-time initialisation attributed to whichever codec runs first is
        not established, and the note must say so rather than implying a codec
        finding."""
        notes = " ".join(e.get("note", "") for e in self._entries()).lower()
        assert "initialis" in notes or "initializ" in notes or "first" in notes


class TestCoverageMeansDataNotJustASignature:
    """"Measured" must mean a suite produced numbers, not that a signature exists.

    Perfherder registers a signature when a test is *defined*; data follows only if
    it actually runs, and lingers long after it stops. So signature-existence alone
    reported `media-capabilities -> ['firefox']` for months before the suite emitted
    a single point, and it would keep reporting that forever if the suite were
    retired. This is the same mistake as the ve-* graph links, which pointed at empty
    charts because the signature outlived the data.
    """

    def _fn(self):
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm2", pathlib.Path("fetch_perf_metrics.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["fpm2"] = m
        spec.loader.exec_module(m)
        return m.build_coverage

    def _sigs(self):
        return {
            "1": {"suite": "vpl-h264", "application": "firefox"},
            "2": {"suite": "vpl-h264", "application": "chrome"},
            "3": {"suite": "media-capabilities", "application": "firefox"},
        }

    def test_a_signature_with_no_data_is_not_counted_as_measured(self):
        cov = self._fn()(self._sigs(), has_data=lambda sid: sid != "3")
        row = [r for r in cov["rows"] if r["suite"] == "media-capabilities"][0]
        assert row["measured"] == [], (
            "a suite with a signature but no data is still reported as measured"
        )

    def test_a_signature_with_data_is_counted(self):
        cov = self._fn()(self._sigs(), has_data=lambda sid: True)
        row = [r for r in cov["rows"] if r["suite"] == "vpl"][0]
        assert set(row["measured"]) == {"firefox", "chrome"}

    def test_the_probe_is_optional_so_callers_need_not_hit_the_network(self):
        """Without a probe it degrades to the old behaviour rather than failing --
        but the caller that publishes must pass one."""
        cov = self._fn()(self._sigs())
        assert [r for r in cov["rows"] if r["suite"] == "media-capabilities"]

    def test_the_publishing_path_passes_a_probe(self):
        import pathlib, re
        src = pathlib.Path("fetch_perf_metrics.py").read_text(encoding="utf-8")
        call = re.search(r"build_coverage\(([^)]*)\)", src[src.index("def collect"):])
        assert call and "has_data" in call.group(1), (
            "collect() calls build_coverage without a data probe, so what it "
            "publishes is signature existence again"
        )


class TestTooFewSamplesIsAlsoAWarning:
    """The `!` marker also fires when a median rests on very few runs.

    The rule was stale-or-noisy, and it was applied consistently -- seek latency
    warns at 22% spread, the capability-query metrics sit at 2.6-12.5% and did not.
    But it ignored sample count entirely, and the new metrics have 15 runs against
    72-75 for everything else, because their suite is a week old. A median over 15
    runs is weaker evidence than one over 75 and the page said nothing about it.

    The threshold is a month of daily runs. A new suite therefore warns until it has
    a month of history and then stops on its own, which is the behaviour we want
    rather than a flag someone has to remember to clear.
    """

    def _view(self, n, cv=3.0, stale=False):
        from reviewstats.perfmetrics import build_metrics_view
        raw = {
            "generated_at": "2026-08-12T00:00:00Z", "window_days": 30,
            "metrics": [{
                "id": "x", "group": "G", "title": "T", "unit": "ms",
                "lower_is_better": True, "platform": "macosx1470-64-shippable",
                "note": "", "stale": stale, "days_behind": 102 if stale else 0,
                "window_end": "2026-08-12",
                "series": {"firefox": {"n": n, "median": 5.0, "p25": 4.9,
                                       "p75": 5.1, "cv": cv, "signature_id": 1}},
            }],
        }
        return build_metrics_view(raw)["metrics"][0]

    def test_a_thin_sample_is_flagged(self):
        assert self._view(n=15)["low_samples"] is True

    def test_a_full_month_is_not_flagged(self):
        assert self._view(n=75)["low_samples"] is False

    def test_the_threshold_is_about_a_month_of_daily_runs(self):
        from reviewstats.perfmetrics import MIN_SAMPLES
        assert 20 <= MIN_SAMPLES <= 40, MIN_SAMPLES

    def test_firefoxs_own_count_decides_not_the_smallest(self):
        """Rival suites legitimately run less often - Chrome lands 13 runs where
        Firefox lands 75 - so a minimum-across-browsers rule fired on all 17 cards,
        and a marker that is always on conveys nothing. The subject of the card is
        Firefox's number; per-browser counts are in the expansion."""
        from reviewstats.perfmetrics import build_metrics_view
        raw = {
            "generated_at": "2026-08-12T00:00:00Z", "window_days": 30,
            "metrics": [{
                "id": "x", "group": "G", "title": "T", "unit": "ms",
                "lower_is_better": True, "platform": "macosx1470-64-shippable",
                "note": "", "stale": False, "days_behind": 0,
                "window_end": "2026-08-12",
                "series": {
                    "firefox": {"n": 75, "median": 5.0, "p25": 4.9, "p75": 5.1,
                                "cv": 2.0, "signature_id": 1},
                    "chrome": {"n": 4, "median": 6.0, "p25": 5.9, "p75": 6.1,
                               "cv": 2.0, "signature_id": 2}},
            }],
        }
        assert build_metrics_view(raw)["metrics"][0]["low_samples"] is False

    def test_the_icon_and_the_expansion_both_report_it(self):
        """The icon's tooltip promises "expand for detail", so the detail has to be
        there or the promise is empty."""
        import pathlib
        t = pathlib.Path("templates/index.html.tmpl").read_text(encoding="utf-8")
        assert "m.low_samples" in t
        assert t.count("m.low_samples") >= 2, (
            "low_samples reaches the icon or the expansion but not both"
        )


class TestTheWarningRuleIsUncomparableOrDead:
    """`!` means: do not lean on this number as a cross-browser result.

    Two conditions, per the rule we settled on:
      * nothing else measures it, so there is no comparison to read
      * the suite has stopped producing, so it describes the past

    Spread and thin samples stay as extra lines in the tooltip. They never fire
    alone on a card that is both compared and live, so they add detail without
    diluting the marker.

    Two rules were tried and rejected first. Stale-or-noisy alone left the
    Firefox-only cards unmarked, which is what prompted the question. Then
    minimum-samples-across-browsers fired on all 17 cards, because rival suites
    legitimately run 13 times where Firefox runs 75 - and a marker that is always on
    conveys nothing.
    """

    def _icon_src(self):
        import pathlib, re
        t = pathlib.Path("templates/index.html.tmpl").read_text(encoding="utf-8")
        m = re.search(r"function warnIcon\(m[^)]*\) \{(.*?)\n  \}", t, re.DOTALL)
        assert m, "warnIcon not found"
        return m.group(1)

    def test_an_uncompared_metric_warns(self):
        src = self._icon_src()
        assert "m.compared" in src, (
            "the icon ignores whether anything else measures this metric"
        )

    def test_a_dead_suite_warns(self):
        assert "m.stale" in self._icon_src()

    def test_spread_and_thin_samples_remain_as_detail(self):
        src = self._icon_src()
        assert "m.noisy" in src and "m.low_samples" in src

    def test_the_expansion_explains_being_uncompared(self):
        import pathlib
        t = pathlib.Path("templates/index.html.tmpl").read_text(encoding="utf-8")
        assert "no other browser" in t.lower()

    def test_a_compared_live_metric_is_unmarked(self):
        """The point of the marker is that some cards do not carry it."""
        from reviewstats.perfmetrics import build_metrics_view
        raw = {"generated_at": "2026-08-12T00:00:00Z", "window_days": 30,
               "metrics": [{
                   "id": "x", "group": "G", "title": "T", "unit": "ms",
                   "lower_is_better": True,
                   "platform": "macosx1470-64-shippable", "note": "",
                   "stale": False, "days_behind": 0, "window_end": "2026-08-12",
                   "series": {
                       "firefox": {"n": 75, "median": 5.0, "p25": 4.9, "p75": 5.1,
                                   "cv": 2.0, "signature_id": 1},
                       "chrome": {"n": 13, "median": 6.0, "p25": 5.9, "p75": 6.1,
                                  "cv": 3.0, "signature_id": 2}}}]}
        m = build_metrics_view(raw)["metrics"][0]
        assert m["compared"] is True
        assert m["stale"] is False
        assert m["noisy"] is False
        assert m["low_samples"] is False


class TestSubtestMatchingIsAnchoredNotSubstring:
    """A subtest name must be matched by suffix, not by "contains".

    The WebCodecs encode suites were re-cut by frame source on 2026-05-02: one
    subtest per suite became three, distinguished by an input-source prefix
    (`RGBX canvas`, `I420 canvas`, `camera`). The old bare name
    `avc1.42001E (annexb) realtime encode - frame-to-frame mean (non key)` stopped
    that day and its replacements started the next push, with no gap in the data.

    Because the old name is a *substring* of all three new ones, a `contains` match
    keeps matching -- so the config went on selecting the dead series while the live
    one sat right next to it. The old code compounded this by explicitly excluding
    any name containing `RGBX` or `I420`, which is precisely the successor set: the
    exclusion was written to keep the bare variant and, once that died, it blocked
    the only rows still reporting.

    Anchoring on the suffix makes the variant part of the identity, so a rename
    fails loudly (no match, metric absent) instead of silently reading a corpse.
    """

    BARE = "avc1.42001E (annexb) realtime encode - frame-to-frame mean (non key)"
    RGBX = ("avc1.42001E (annexb) RGBX canvas realtime encode"
            " - frame-to-frame mean (non key)")
    I420 = ("avc1.42001E (annexb) I420 canvas realtime encode"
            " - frame-to-frame mean (non key)")
    CAM = "avc1.42001E (annexb) camera realtime encode - frame-to-frame mean (non key)"

    def _spec(self, suffix):
        return {"test": None, "test_suffix": suffix}

    def test_a_suffix_selects_only_its_own_variant(self):
        spec = self._spec("RGBX canvas realtime encode - frame-to-frame mean (non key)")
        assert matches_test(spec, self.RGBX) is True
        assert matches_test(spec, self.I420) is False
        assert matches_test(spec, self.CAM) is False
        assert matches_test(spec, self.BARE) is False

    def test_the_dead_bare_variant_does_not_match_a_variant_suffix(self):
        """The regression this guards: the whole point is that the corpse is
        excluded, not preferred."""
        spec = self._spec("RGBX canvas realtime encode - frame-to-frame mean (non key)")
        assert matches_test(spec, self.BARE) is False

    def test_a_bare_suffix_still_sweeps_up_the_variants(self):
        """The limit of suffix matching, asserted so nobody mistakes it for a
        guarantee it does not give.

        The old bare name is a genuine *suffix* of all three successors, not just a
        substring, so anchoring the tail cannot separate them. Anchoring buys
        precision in the direction we need (a full variant suffix excludes the other
        variants and the corpse) but it does not make a vague suffix safe. That is
        what `ambiguous_matches` is for.
        """
        spec = self._spec("realtime encode - frame-to-frame mean (non key)")
        assert matches_test(spec, self.BARE) is True
        assert matches_test(spec, self.RGBX) is True
        assert matches_test(spec, self.I420) is True

    def test_exact_test_names_still_match_exactly(self):
        spec = {"test": "seekedColdLatency"}
        assert matches_test(spec, "seekedColdLatency") is True
        assert matches_test(spec, "seekedWarmLatency") is False
        assert matches_test(spec, None) is False

    def test_a_suite_level_score_wants_no_subtest(self):
        """webaudio charts the suite score, so a row carrying a subtest name is the
        wrong row."""
        spec = {"test": None}
        assert matches_test(spec, None) is True
        assert matches_test(spec, "") is True
        assert matches_test(spec, "some-subtest") is False


class TestWebCodecsChartsTheLiveVariant:
    """The four WebCodecs encode cards must point at subtests that still report.

    They read 102 days stale because they were configured for the pre-2026-05-02
    bare variant. This asserts the config moved to the live cross-browser variant
    and records why that particular one: `RGBX canvas` is the only input source all
    three browsers run.
    """

    def _entries(self):
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm", pathlib.Path("fetch_perf_metrics.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["fpm"] = m
        spec.loader.exec_module(m)
        return [e for e in m.METRICS if e["group"] == "WebCodecs encode"]

    def test_all_four_codecs_are_still_charted(self):
        assert {e["id"] for e in self._entries()} == {
            "ve.h264", "ve.vp8", "ve.vp9", "ve.av1"}

    def test_every_card_anchors_on_the_rgbx_canvas_variant(self):
        for e in self._entries():
            assert e.get("test_suffix") == (
                "RGBX canvas realtime encode - frame-to-frame mean (non key)"), e["id"]

    def test_no_card_still_uses_the_dead_bare_variant(self):
        """`test_contains` is gone as a field name too, so a stale config cannot be
        reintroduced by copy-paste from an old revision."""
        for e in self._entries():
            assert "test_contains" not in e, e["id"]

    def test_the_h264_card_says_it_is_480p(self):
        """`ve-h264-rt-sd` is 640x480 while every other codec here is 1920x1080,
        because Chrome refuses WebCodecs H.264 encode above SD. A reader comparing
        H.264's number to VP9's without knowing that is reading a resolution
        difference as a codec difference."""
        h264 = [e for e in self._entries() if e["id"] == "ve.h264"][0]
        label = (h264["title"] + " " + h264.get("note", "")).lower()
        assert "480" in label, label

    def test_the_1080p_cards_say_so(self):
        for e in self._entries():
            if e["id"] == "ve.h264":
                continue
            label = (e["title"] + " " + e.get("note", "")).lower()
            assert "1080" in label, e["id"]

    def test_the_note_no_longer_claims_canvas_variants_are_excluded(self):
        """That comment described the pre-rename world. Canvas is now the only input
        path, so the claim inverted from true to false without anyone editing it."""
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm", pathlib.Path("fetch_perf_metrics.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["fpm"] = m
        spec.loader.exec_module(m)
        src = pathlib.Path("fetch_perf_metrics.py").read_text()
        needle = "canvas-source variants are " + "excluded"
        assert needle not in src, "stale pre-rename comment still present"


class TestAVagueSubtestMatchIsReported:
    """If a metric's match covers more than one subtest, say so.

    This is the guard that would have caught the WebCodecs staleness at the moment
    it happened. Suffix anchoring alone cannot: the old bare name is a suffix of all
    three of its successors, so on 2026-05-02 the config's match went from selecting
    one row to selecting four, and `pick_signature` quietly resolved that by sample
    count -- picking the one with the longest history, which was the one that had
    just died.

    Selecting several distinct subtests for one card is never intended. It means the
    upstream test was re-cut and the config has not caught up.
    """

    def test_one_subtest_per_browser_is_fine(self):
        from reviewstats.perfmetrics import ambiguous_matches
        rows = [{"application": "firefox", "test": "a"},
                {"application": "chrome", "test": "a"}]
        assert ambiguous_matches(rows) == {}

    def test_duplicate_signatures_of_the_same_subtest_are_fine(self):
        """Several ids sharing a (browser, suite, test) is normal -- they differ by
        build options, and `pick_signature` exists to choose between them."""
        from reviewstats.perfmetrics import ambiguous_matches
        rows = [{"application": "firefox", "test": "a", "id": 1},
                {"application": "firefox", "test": "a", "id": 2}]
        assert ambiguous_matches(rows) == {}

    def test_two_different_subtests_for_one_browser_is_reported(self):
        from reviewstats.perfmetrics import ambiguous_matches
        rows = [
            {"application": "firefox", "test": "bare realtime encode - mean"},
            {"application": "firefox", "test": "RGBX canvas realtime encode - mean"},
        ]
        got = ambiguous_matches(rows)
        assert set(got) == {"firefox"}
        assert got["firefox"] == ["RGBX canvas realtime encode - mean",
                                  "bare realtime encode - mean"], "sorted for stability"

    def test_reports_every_affected_browser(self):
        from reviewstats.perfmetrics import ambiguous_matches
        rows = [
            {"application": "firefox", "test": "x - mean"},
            {"application": "firefox", "test": "y - mean"},
            {"application": "chrome", "test": "x - mean"},
            {"application": "chrome", "test": "y - mean"},
            {"application": "custom-car", "test": "x - mean"},
        ]
        got = ambiguous_matches(rows)
        assert set(got) == {"firefox", "chrome"}

    def test_rows_without_a_browser_are_ignored(self):
        from reviewstats.perfmetrics import ambiguous_matches
        assert ambiguous_matches([{"test": "a"}, {"test": "b"}]) == {}

    def test_empty_input_is_not_ambiguous(self):
        from reviewstats.perfmetrics import ambiguous_matches
        assert ambiguous_matches([]) == {}


class TestAStaleRivalSeriesIsMarkedNotBlended:
    """A rival browser that stopped reporting must not be drawn as current.

    `stale` / `days_behind` were per *metric* and took the freshest series, so a card
    whose Firefox data is current reads `stale: false` even when a rival's bar is
    weeks old. custom-car is the live example: it stopped producing WebCodecs encode
    numbers on 2026-06-28, yet its bar still appears beside current Firefox and
    Chrome bars because each series' window is measured from its own newest point.

    That is the same defect that made the cards stale in the first place, one layer
    down: a dead series that looks identical to a healthy one.
    """

    def _metric(self, **series):
        return {"generated_at": "2026-08-13T00:00:00Z", "window_days": 30,
                "metrics": [{
                    "id": "ve.av1", "group": "WebCodecs encode", "title": "AV1 1080p",
                    "unit": "ms", "lower_is_better": True, "note": "",
                    "platform": "macosx1470-64-shippable",
                    "stale": False, "days_behind": 0, "window_end": "2026-08-13",
                    "series": series}]}

    def _s(self, median, n, days_behind):
        return {"n": n, "median": median, "p25": median, "p75": median,
                "cv": 1.0, "signature_id": 1, "days_behind": days_behind}

    def test_a_current_rival_is_not_marked(self):
        raw = self._metric(firefox=self._s(25.0, 76, 0), chrome=self._s(5.7, 13, 1))
        m = build_metrics_view(raw)["metrics"][0]
        assert m["series"]["chrome"]["stale"] is False

    def test_a_rival_weeks_behind_is_marked(self):
        raw = self._metric(firefox=self._s(25.0, 76, 0),
                           safari=self._s(5.7, 23, 46))
        m = build_metrics_view(raw)["metrics"][0]
        assert m["series"]["safari"]["stale"] is True
        assert m["series"]["safari"]["days_behind"] == 46

    def test_the_metric_reports_that_some_series_is_stale(self):
        """The card-level flag the `!` marker reads. The metric is not stale itself --
        Firefox is current -- but it is mixing timeframes, and that is worth a mark."""
        raw = self._metric(firefox=self._s(25.0, 76, 0),
                           safari=self._s(5.7, 23, 46))
        m = build_metrics_view(raw)["metrics"][0]
        assert m["stale"] is False, "Firefox is current, so the card is not stale"
        assert m["mixed_windows"] is True
        assert m["stale_browsers"] == ["safari"]

    def test_no_mixing_when_every_series_is_current(self):
        raw = self._metric(firefox=self._s(25.0, 76, 0), chrome=self._s(5.7, 13, 2))
        m = build_metrics_view(raw)["metrics"][0]
        assert m["mixed_windows"] is False
        assert m["stale_browsers"] == []

    def test_a_series_without_freshness_data_is_not_guessed_stale(self):
        """Older data_metrics.json files predate the per-series field. Absent must
        read as unknown-but-not-flagged, not as stale."""
        s = self._s(5.7, 13, 0)
        del s["days_behind"]
        raw = self._metric(firefox=self._s(25.0, 76, 0), chrome=s)
        m = build_metrics_view(raw)["metrics"][0]
        assert m["series"]["chrome"]["stale"] is False
        assert m["mixed_windows"] is False

    def test_firefox_being_behind_still_makes_the_whole_card_stale(self):
        """Unchanged existing behaviour: this is about rivals, not a new rule for us."""
        raw = self._metric(firefox=self._s(25.0, 76, 40))
        raw["metrics"][0]["stale"] = True
        raw["metrics"][0]["days_behind"] = 40
        m = build_metrics_view(raw)["metrics"][0]
        assert m["stale"] is True


class TestAStaleRivalDoesNotWinTheComparison:
    """A series that stopped reporting must not be the headline comparator.

    Marking it was not enough. On VP8 1080p, custom-car's 45-day-old 6.7 ms beat
    Chrome's current 6.8 ms by a rounding error, so it took both the "best" label and
    the `versus` slot -- the card's headline number was measured against data from
    other weeks while a current rival sat next to it.

    When any rival is current, the comparison uses current rivals only. When every
    rival is stale the comparison still runs against them, because "no comparison at
    all" would be a bigger lie than an old one -- and the card already carries the
    marker saying so.
    """

    def _metric(self, **series):
        return {"generated_at": "2026-08-13T00:00:00Z", "window_days": 30,
                "metrics": [{
                    "id": "ve.vp8", "group": "WebCodecs encode", "title": "VP8 1080p",
                    "unit": "ms", "lower_is_better": True, "note": "",
                    "platform": "macosx1470-64-shippable",
                    "stale": False, "days_behind": 0, "window_end": "2026-08-13",
                    "series": series}]}

    def _s(self, median, n, days_behind):
        return {"n": n, "median": median, "p25": median, "p75": median,
                "cv": 1.0, "signature_id": 1, "days_behind": days_behind}

    def test_a_current_rival_is_preferred_even_when_the_stale_one_looks_better(self):
        m = build_metrics_view(self._metric(
            firefox=self._s(16.3, 75, 0),
            chrome=self._s(6.8, 12, 1),
            **{"custom-car": self._s(6.7, 23, 45)},
        ))["metrics"][0]
        assert m["comparison"]["versus"] == "chrome"

    def test_the_stale_rival_is_still_shown(self):
        """Excluded from the verdict, not from the plot -- it is real data."""
        m = build_metrics_view(self._metric(
            firefox=self._s(16.3, 75, 0),
            chrome=self._s(6.8, 12, 1),
            safari=self._s(6.7, 23, 45),
        ))["metrics"][0]
        assert "safari" in m["series"]
        assert m["series"]["safari"]["stale"] is True

    def test_the_stale_rival_is_not_the_leader(self):
        """The `best` label is computed from this flag rather than from the medians,
        so the template does not need its own opinion about freshness."""
        m = build_metrics_view(self._metric(
            firefox=self._s(16.3, 75, 0),
            chrome=self._s(6.8, 12, 1),
            **{"custom-car": self._s(6.7, 23, 45)},
        ))["metrics"][0]
        assert m["leader"] == "chrome"

    def test_firefox_can_be_the_leader(self):
        m = build_metrics_view(self._metric(
            firefox=self._s(3.0, 75, 0), chrome=self._s(6.8, 12, 1),
        ))["metrics"][0]
        assert m["leader"] == "firefox"

    def test_higher_is_better_picks_the_highest_current(self):
        raw = self._metric(firefox=self._s(100.0, 75, 0),
                           chrome=self._s(90.0, 12, 1),
                           **{"custom-car": self._s(300.0, 23, 45)})
        raw["metrics"][0]["lower_is_better"] = False
        m = build_metrics_view(raw)["metrics"][0]
        assert m["leader"] == "firefox"
        assert m["comparison"]["versus"] == "chrome"

    def test_when_every_rival_is_stale_the_comparison_still_happens(self):
        """Better an old comparison, marked, than pretending nobody measures it."""
        m = build_metrics_view(self._metric(
            firefox=self._s(16.3, 75, 0),
            safari=self._s(6.7, 23, 45),
        ))["metrics"][0]
        assert m["comparison"]["versus"] == "safari"
        assert m["compared"] is True
        assert m["mixed_windows"] is True

    def test_a_firefox_only_metric_is_unaffected(self):
        m = build_metrics_view(self._metric(
            firefox=self._s(16.3, 75, 0)))["metrics"][0]
        assert m["compared"] is False
        assert m["leader"] == "firefox"


class TestAConfiguredMetricThatResolvedToNothingIsReported:
    """Adding a metric that matches no signature must not be a silent no-op.

    The failure is quiet by construction: `collect` appends the spec with an empty
    `series`, `_render_metric` drops it for having no Firefox data, and the page
    renders one card short. `is_safe_to_write` does not catch it either -- it guards
    against losing half the table, not against never gaining one row.

    So a typo in `suite`, a platform that does not run the suite, or a subtest that
    was renamed all look identical to "I never added it".
    """

    def test_a_metric_with_no_series_is_named(self):
        from reviewstats.perfmetrics import unresolved_metrics
        got = unresolved_metrics([
            {"id": "vpl.h264", "series": {"firefox": {"n": 5}}},
            {"id": "ve.new", "series": {}},
        ])
        assert got == ["ve.new"]

    def test_a_metric_with_only_rivals_is_named(self):
        """The view is "where Firefox stands", so rival-only data still renders
        nothing -- and the reason is worth distinguishing from no data at all."""
        from reviewstats.perfmetrics import unresolved_metrics
        got = unresolved_metrics([{"id": "x", "series": {"chrome": {"n": 5}}}])
        assert got == ["x"]

    def test_everything_resolved_is_empty(self):
        from reviewstats.perfmetrics import unresolved_metrics
        assert unresolved_metrics([
            {"id": "a", "series": {"firefox": {"n": 1}}}]) == []

    def test_order_is_stable(self):
        from reviewstats.perfmetrics import unresolved_metrics
        got = unresolved_metrics([
            {"id": "b", "series": {}}, {"id": "a", "series": {}}])
        assert got == ["b", "a"], "config order, so it reads like the METRICS list"

    def test_empty_input(self):
        from reviewstats.perfmetrics import unresolved_metrics
        assert unresolved_metrics([]) == []

    def test_the_fetcher_reports_them(self):
        """Wired up, not merely available."""
        import pathlib
        src = pathlib.Path("fetch_perf_metrics.py").read_text()
        assert "unresolved_metrics" in src, "the guard is never called"


class TestEveryMetricDeclaresWhatTheRendererNeeds:
    """A config-shape check over the whole METRICS table, not one suite.

    The renderer reads `unit`, `lower_is_better`, `group`, `title` and `platform`
    off every entry, and `collect` copies exactly those keys -- so a missing one is a
    KeyError at fetch time, and a wrong `lower_is_better` silently inverts a chart
    (Perfherder reports `None` for it on most signatures, so nothing upstream
    corrects us). This was previously asserted only for `media-capabilities`.
    """

    def _metrics(self):
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm_all", pathlib.Path("fetch_perf_metrics.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["fpm_all"] = m
        spec.loader.exec_module(m)
        return m.METRICS

    def test_required_keys_are_present_on_every_entry(self):
        need = ("id", "group", "title", "suite", "platform", "unit",
                "lower_is_better", "note")
        for e in self._metrics():
            missing = [k for k in need if k not in e]
            assert not missing, f"{e.get('id')} missing {missing}"

    def test_direction_is_an_explicit_bool(self):
        """Not truthy-by-accident: `None` would read as 'lower is better' and
        invert the verdict on a score metric."""
        for e in self._metrics():
            assert isinstance(e["lower_is_better"], bool), e["id"]

    def test_ids_are_unique(self):
        ids = [e["id"] for e in self._metrics()]
        assert len(ids) == len(set(ids)), "duplicate metric id"

    def test_units_are_non_empty(self):
        for e in self._metrics():
            assert str(e["unit"]).strip(), e["id"]

    def test_a_group_is_internally_consistent(self):
        """Cards in one group share an axis and a direction, so mixed units or
        directions inside a group would draw incomparable bars on one scale."""
        from collections import defaultdict
        by_group = defaultdict(list)
        for e in self._metrics():
            by_group[e["group"]].append(e)
        for g, entries in by_group.items():
            assert len({e["unit"] for e in entries}) == 1, f"{g}: mixed units"
            assert len({e["lower_is_better"] for e in entries}) == 1, \
                f"{g}: mixed directions"
            assert len({e["platform"] for e in entries}) == 1, \
                f"{g}: mixed platforms"

    def test_subtest_selection_is_declared_exactly_one_way(self):
        """`test` and `test_suffix` are alternatives; declaring both would make the
        precedence rule load-bearing for no reason."""
        for e in self._metrics():
            assert not (e.get("test") is not None and e.get("test_suffix")), e["id"]

    def test_no_entry_uses_the_removed_test_contains_field(self):
        """It was replaced by anchored-suffix matching. An entry still carrying it
        would be matched as a suite-level score and silently pick the wrong row."""
        for e in self._metrics():
            assert "test_contains" not in e, e["id"]


class TestAThinlySampledRivalStillCompares:
    """A rival with very few runs is compared anyway, and its `n` carries the caveat.

    This reverses an earlier rule. When Safari arrived on `vpl-h264` and Chrome on
    `media-seek` with one run each, both were withheld from the verdict on the grounds
    that one run is not a median -- which meant a brand-new cross-browser number, the
    thing this view exists to surface, showed as "not compared" for its first week.

    The call is that a rough comparison, labelled, beats none: sample size is reported
    per browser in the expansion (`n=1`), so the reader can weigh it. Nothing here
    hides how thin the evidence is; it just stops suppressing the number.
    """

    def _metric(self, **series):
        return {"generated_at": "2026-08-21T00:00:00Z", "window_days": 30,
                "metrics": [{
                    "id": "media-seek.warm", "group": "Seek latency",
                    "title": "Decoder warm", "unit": "ms",
                    "lower_is_better": True, "note": "",
                    "platform": "macosx1470-64-shippable",
                    "stale": False, "days_behind": 0, "window_end": "2026-08-21",
                    "series": series}]}

    def _s(self, median, n, days_behind=0, cv=1.0):
        return {"n": n, "median": median, "p25": median, "p75": median,
                "cv": cv, "signature_id": 1, "days_behind": days_behind}

    def test_a_single_run_rival_sets_the_verdict(self):
        m = build_metrics_view(self._metric(
            firefox=self._s(14.1, 76), chrome=self._s(6.9, 1)))["metrics"][0]
        assert m["compared"] is True
        assert m["comparison"]["versus"] == "chrome"
        assert m["comparison"]["ahead"] is False

    def test_a_single_run_rival_can_take_the_best_label(self):
        m = build_metrics_view(self._metric(
            firefox=self._s(14.1, 76), chrome=self._s(6.9, 1)))["metrics"][0]
        assert m["leader"] == "chrome"

    def test_its_sample_count_survives_for_the_expansion(self):
        """The only place the thinness is recorded, so it must not be dropped."""
        m = build_metrics_view(self._metric(
            firefox=self._s(14.1, 76), chrome=self._s(6.9, 1)))["metrics"][0]
        assert m["series"]["chrome"]["n"] == 1

    def test_a_single_sample_still_reports_no_spread_rather_than_zero(self):
        """Unchanged: cv 0.0 from one run renders as "CV 0%" and reads as rock-steady,
        which is the one thing about n=1 that is actively misleading."""
        m = build_metrics_view(self._metric(
            firefox=self._s(14.1, 76), chrome=self._s(6.9, 1, cv=0.0)))["metrics"][0]
        assert m["series"]["chrome"]["cv_known"] is False
        assert m["series"]["firefox"]["cv_known"] is True

    def test_a_stale_rival_is_still_held_back_from_the_verdict(self):
        """Staleness and thin sampling are different faults, and only one was
        reversed: an old number is still deprioritised behind a current one."""
        m = build_metrics_view(self._metric(
            firefox=self._s(16.3, 75),
            chrome=self._s(6.8, 12),
            safari=self._s(6.7, 23, days_behind=45)))["metrics"][0]
        assert m["comparison"]["versus"] == "chrome"
        assert m["stale_browsers"] == ["safari"]

    def test_no_metric_carries_a_provisional_field_any_more(self):
        """Guards the removal: a leftover flag that nothing reads is worse than none,
        because the next reader assumes it still gates something."""
        m = build_metrics_view(self._metric(
            firefox=self._s(14.1, 76), chrome=self._s(6.9, 1)))["metrics"][0]
        assert "provisional_browsers" not in m
        assert "provisional" not in m["series"]["chrome"]


class TestOnlyChromeAndSafariAreCompared:
    """`custom-car` is excluded from the view entirely.

    It is a Chromium build tracking Chrome, so its bar restated Chrome's to within a
    rounding error -- 6.7 ms against 6.8 ms on VP8 -- while dragging in its own
    staleness caveat, which then earned the card a warning marker and two extra lines
    of text. Two lines of caveat for no extra information.

    Filtered in the data layer so the verdict, the plot and the warnings cannot
    disagree about who is in the comparison.
    """

    def _view(self, **series):
        return build_metrics_view({
            "generated_at": "2026-08-21T00:00:00Z", "window_days": 30,
            "metrics": [{
                "id": "ve.vp8", "group": "WebCodecs encode", "title": "VP8 1080p",
                "unit": "ms", "lower_is_better": True, "note": "",
                "platform": "macosx1470-64-shippable",
                "stale": False, "days_behind": 0, "window_end": "2026-08-21",
                "series": {b: {"n": n, "median": v, "p25": v, "p75": v, "cv": 1.0,
                               "signature_id": 1, "days_behind": d}
                           for b, (v, n, d) in series.items()}}]})["metrics"][0]

    def test_custom_car_is_dropped_from_the_series(self):
        m = self._view(firefox=(16.3, 75, 0), chrome=(6.8, 12, 0),
                       **{"custom-car": (6.7, 23, 45)})
        assert set(m["series"]) == {"firefox", "chrome"}

    def test_it_cannot_be_the_verdict(self):
        """It used to win: 6.7 beat 6.8, so a 45-day-old Chromium build set the
        headline for a card whose point is the gap to Chrome."""
        m = self._view(firefox=(16.3, 75, 0), chrome=(6.8, 12, 0),
                       **{"custom-car": (6.7, 23, 45)})
        assert m["comparison"]["versus"] == "chrome"
        assert m["leader"] == "chrome"

    def test_it_is_not_listed_as_a_rival(self):
        m = self._view(firefox=(16.3, 75, 0), chrome=(6.8, 12, 0),
                       **{"custom-car": (6.7, 23, 45)})
        assert [r["browser"] for r in m["rivals"]] == ["chrome"]

    def test_its_staleness_no_longer_warns(self):
        """The mixed-window marker was firing on all four WebCodecs cards purely
        because of custom-car."""
        m = self._view(firefox=(16.3, 75, 0), chrome=(6.8, 12, 0),
                       **{"custom-car": (6.7, 23, 45)})
        assert m["mixed_windows"] is False
        assert m["stale_browsers"] == []

    def test_safari_is_kept(self):
        m = self._view(firefox=(160.0, 77, 0), chrome=(287.8, 14, 0),
                       safari=(367.9, 1, 0))
        assert set(m["series"]) == {"firefox", "chrome", "safari"}

    def test_a_firefox_only_metric_is_unaffected(self):
        m = self._view(firefox=(15.0, 76, 0))
        assert set(m["series"]) == {"firefox"}
        assert m["compared"] is False


class TestEveryRivalIsNamedWithItsOwnFactor:
    """The verdict names each rival and its factor instead of saying "best of 2".

    Picking only the strongest rival hid that another browser was measured at all:
    with Safari on vpl-h264 the card read `1.80x ahead / chrome / (of 2)` and never
    mentioned Safari, even though we beat it by more. `rival_breakdown` gives the
    page one line per rival so it can say so.

    Order is load-bearing: the first comparable entry must be the one the headline
    verdict is computed from, or the big number and the list would disagree.
    """

    def _series(self, **kw):
        out = {}
        for b, (median, n, stale, prov) in kw.items():
            out[b] = {"n": n, "median": median, "p25": median, "p75": median,
                      "cv": 1.0, "signature_id": 1, "stale": stale,
                      "provisional": prov}
        return out

    def test_one_line_per_rival_firefox_excluded(self):
        from reviewstats.perfmetrics import rival_breakdown
        got = rival_breakdown(160.0, self._series(
            firefox=(160.0, 77, False, False),
            chrome=(287.8, 14, False, False),
            safari=(367.9, 20, False, False)), lower_is_better=True)
        assert [r["browser"] for r in got] == ["chrome", "safari"]

    def test_each_carries_its_own_factor_and_direction(self):
        from reviewstats.perfmetrics import rival_breakdown
        got = {r["browser"]: r for r in rival_breakdown(160.0, self._series(
            firefox=(160.0, 77, False, False),
            chrome=(287.8, 14, False, False),
            safari=(367.9, 20, False, False)), lower_is_better=True)}
        assert got["chrome"]["factor"] == pytest.approx(1.80, abs=0.01)
        assert got["chrome"]["ahead"] is True
        assert got["safari"]["factor"] == pytest.approx(2.30, abs=0.01)
        assert got["safari"]["ahead"] is True

    def test_strongest_comparable_rival_is_first(self):
        """Must agree with the headline, which compares against the strongest."""
        from reviewstats.perfmetrics import rival_breakdown
        got = rival_breakdown(160.0, self._series(
            firefox=(160.0, 77, False, False),
            safari=(367.9, 20, False, False),
            chrome=(287.8, 14, False, False)), lower_is_better=True)
        assert got[0]["browser"] == "chrome", "lowest median is strongest here"

    def test_direction_is_per_rival_not_shared(self):
        """We can be behind one browser and ahead of another on one metric; a single
        shared ahead/behind word would be wrong for one of them."""
        from reviewstats.perfmetrics import rival_breakdown
        got = {r["browser"]: r for r in rival_breakdown(160.0, self._series(
            firefox=(160.0, 77, False, False),
            chrome=(80.0, 14, False, False),
            safari=(320.0, 20, False, False)), lower_is_better=True)}
        assert got["chrome"]["ahead"] is False
        assert got["safari"]["ahead"] is True

    def test_higher_is_better_inverts_strength(self):
        from reviewstats.perfmetrics import rival_breakdown
        got = rival_breakdown(96.0, self._series(
            firefox=(96.0, 77, False, False),
            chrome=(316.0, 14, False, False),
            safari=(112.0, 20, False, False)), lower_is_better=False)
        assert got[0]["browser"] == "chrome", "highest wins when higher is better"
        assert got[0]["ahead"] is False

    def test_a_thinly_sampled_rival_still_gets_a_factor(self):
        """Reversed deliberately: withholding it meant a brand-new cross-browser
        number read as "not compared" for its first week. `n` travels with it."""
        from reviewstats.perfmetrics import rival_breakdown
        got = {r["browser"]: r for r in rival_breakdown(160.0, self._series(
            firefox=(160.0, 77, False, False),
            chrome=(287.8, 14, False, False),
            safari=(367.9, 1, False, False)), lower_is_better=True)}
        assert got["safari"]["factor"] == pytest.approx(2.30, abs=0.01)
        assert got["safari"]["ahead"] is True
        assert got["safari"]["n"] == 1

    def test_sorting_is_by_strength_once_sample_size_stops_mattering(self):
        from reviewstats.perfmetrics import rival_breakdown
        got = rival_breakdown(160.0, self._series(
            firefox=(160.0, 77, False, False),
            safari=(100.0, 1, False, False),
            chrome=(287.8, 14, False, False)), lower_is_better=True)
        assert [r["browser"] for r in got] == ["safari", "chrome"], (
            "lowest median is strongest, whatever its n")

    def test_a_stale_rival_keeps_its_factor_but_is_marked(self):
        """Real data, just from other weeks -- so the number stands and the label
        says when."""
        from reviewstats.perfmetrics import rival_breakdown
        got = {r["browser"]: r for r in rival_breakdown(16.3, self._series(
            firefox=(16.3, 75, False, False),
            chrome=(6.8, 12, False, False),
            **{"custom-car": (6.7, 23, True, False)}), lower_is_better=True)}
        assert got["custom-car"]["stale"] is True
        assert got["custom-car"]["factor"] == pytest.approx(2.43, abs=0.01)
        assert got["chrome"]["stale"] is False

    def test_stale_rivals_sort_after_current_ones(self):
        from reviewstats.perfmetrics import rival_breakdown
        got = rival_breakdown(16.3, self._series(
            firefox=(16.3, 75, False, False),
            **{"custom-car": (6.7, 23, True, False)},
            chrome=(6.8, 12, False, False)), lower_is_better=True)
        assert [r["browser"] for r in got] == ["chrome", "custom-car"]

    def test_no_rivals_is_an_empty_list(self):
        from reviewstats.perfmetrics import rival_breakdown
        assert rival_breakdown(15.0, self._series(
            firefox=(15.0, 76, False, False)), lower_is_better=True) == []

    def test_it_is_attached_to_the_metric(self):
        m = build_metrics_view({
            "generated_at": "2026-08-21T00:00:00Z", "window_days": 30,
            "metrics": [{
                "id": "vpl.h264", "group": "First frame latency", "title": "H.264",
                "unit": "ms", "lower_is_better": True, "note": "",
                "platform": "macosx1470-64-shippable",
                "stale": False, "days_behind": 0, "window_end": "2026-08-21",
                "series": {
                    "firefox": {"n": 77, "median": 160.0, "p25": 158.0,
                                "p75": 162.0, "cv": 2.0, "signature_id": 1,
                                "days_behind": 0},
                    "chrome": {"n": 14, "median": 287.8, "p25": 280.0,
                               "p75": 295.0, "cv": 4.0, "signature_id": 2,
                               "days_behind": 0},
                    "safari": {"n": 1, "median": 367.9, "p25": 367.9,
                               "p75": 367.9, "cv": 0.0, "signature_id": 3,
                               "days_behind": 0}}}]})["metrics"][0]
        assert [r["browser"] for r in m["rivals"]] == ["chrome", "safari"]
        assert m["rivals"][0]["browser"] == m["comparison"]["versus"], (
            "the list and the headline must agree")
        assert m["rivals"][1]["factor"] == pytest.approx(2.30, abs=0.01)


class TestFirefoxOnlyGroupsAreSeparated:
    """Groups with no rival are split out so they stop reading as failed comparisons.

    Eight cards can never be compared -- seek cold, and all seven capability-query
    cards, whose suite is Firefox-only by design. Rendered inline among compared
    cards they all show the same hatched "no other browser measured yet" bar, which
    makes a deliberate Firefox-only measurement look like a broken one.

    The split is at GROUP level and derived from the data: a group is Firefox-only
    when none of its metrics has a rival. Splitting per card instead would tear
    `Seek latency` in half to isolate one card, which costs the reader the cold/warm
    pairing to gain very little.
    """

    def _raw(self, *specs):
        metrics = []
        for mid, group, series in specs:
            metrics.append({
                "id": mid, "group": group, "title": mid, "unit": "ms",
                "lower_is_better": True, "note": "",
                "platform": "macosx1470-64-shippable",
                "stale": False, "days_behind": 0, "window_end": "2026-08-21",
                "series": {b: {"n": n, "median": v, "p25": v, "p75": v, "cv": 1.0,
                               "signature_id": 1, "days_behind": 0}
                           for b, (v, n) in series.items()}})
        return {"generated_at": "2026-08-21T00:00:00Z", "window_days": 30,
                "metrics": metrics}

    def test_a_group_with_a_rival_is_compared(self):
        v = build_metrics_view(self._raw(
            ("vpl.h264", "First frame latency",
             {"firefox": (160.0, 77), "chrome": (287.8, 14)})))
        assert [g["title"] for g in v["groups_compared"]] == ["First frame latency"]
        assert v["groups_firefox_only"] == []

    def test_a_group_with_no_rival_anywhere_is_separated(self):
        v = build_metrics_view(self._raw(
            ("mc.first", "Capability query latency", {"firefox": (5.0, 40)}),
            ("mc.avc", "Capability query latency", {"firefox": (9.0, 40)})))
        assert v["groups_compared"] == []
        assert [g["title"] for g in v["groups_firefox_only"]] == [
            "Capability query latency"]

    def test_a_mixed_group_is_split_per_card(self):
        """Seek: cold has no rival, warm does, and they belong in different halves --
        warm is a comparison, cold is a trend line. Splitting whole groups instead
        left a hatched card in the compared half that could never be filled in."""
        v = build_metrics_view(self._raw(
            ("seek.cold", "Seek latency", {"firefox": (14.8, 76)}),
            ("seek.warm", "Seek latency",
             {"firefox": (14.1, 76), "chrome": (6.9, 20)})))
        assert [g["title"] for g in v["groups_compared"]] == ["Seek latency"]
        assert [m["id"] for m in v["groups_compared"][0]["metrics"]] == ["seek.warm"]
        assert [g["title"] for g in v["groups_firefox_only"]] == ["Seek latency"]
        assert [m["id"] for m in v["groups_firefox_only"][0]["metrics"]] == [
            "seek.cold"]

    def test_each_half_scales_to_what_it_draws(self):
        """`axis_max` is recomputed per half; inheriting the whole group's would
        squash the surviving bars against a maximum nothing on screen reaches."""
        v = build_metrics_view(self._raw(
            ("seek.cold", "Seek latency", {"firefox": (400.0, 76)}),
            ("seek.warm", "Seek latency",
             {"firefox": (14.1, 76), "chrome": (6.9, 20)})))
        assert v["groups_compared"][0]["axis_max"] < 100

    def test_a_thinly_sampled_rival_makes_a_group_compared(self):
        """Chrome at n=1 on seek is a comparison now, so `Decoder warm` belongs in
        the compared half rather than sitting among the Firefox-only cards."""
        v = build_metrics_view(self._raw(
            ("seek.warm", "Seek latency",
             {"firefox": (14.1, 76), "chrome": (6.9, 1)})))
        assert [g["title"] for g in v["groups_compared"]] == ["Seek latency"]
        assert v["groups_firefox_only"] == []

    def test_every_card_lands_in_exactly_one_half(self):
        """Groups may appear in both halves now, but a *card* must appear once --
        dropping one would lose a measurement, duplicating one would double-count."""
        v = build_metrics_view(self._raw(
            ("vpl.h264", "First frame latency",
             {"firefox": (160.0, 77), "chrome": (287.8, 14)}),
            ("seek.cold", "Seek latency", {"firefox": (14.8, 76)}),
            ("seek.warm", "Seek latency",
             {"firefox": (14.1, 76), "chrome": (6.9, 1)}),
            ("mc.first", "Capability query latency", {"firefox": (5.0, 40)})))
        placed = [m["id"] for half in ("groups_compared", "groups_firefox_only")
                  for g in v[half] for m in g["metrics"]]
        assert sorted(placed) == sorted(m["id"] for m in v["metrics"])
        assert len(placed) == len(set(placed)), "a card was placed twice"

    def test_the_undivided_group_list_is_still_published(self):
        """Kept so nothing that reads `groups` breaks, and so the split stays a
        presentation concern rather than a change to the underlying data."""
        v = build_metrics_view(self._raw(
            ("vpl.h264", "First frame latency",
             {"firefox": (160.0, 77), "chrome": (287.8, 14)})))
        assert [g["title"] for g in v["groups"]] == ["First frame latency"]

    def test_each_group_says_whether_it_is_compared(self):
        v = build_metrics_view(self._raw(
            ("vpl.h264", "First frame latency",
             {"firefox": (160.0, 77), "chrome": (287.8, 14)}),
            ("mc.first", "Capability query latency", {"firefox": (5.0, 40)})))
        flags = {g["title"]: g["compared"] for g in v["groups"]}
        assert flags == {"First frame latency": True,
                         "Capability query latency": False}


class TestAFirefoxOnlyCardCanCompareAgainstItsSibling:
    """A card with no rival browser can still carry a ratio -- against another of our
    own measurements.

    `Decoder cold` has no rival and never will: no other browser reports a cold seek.
    But it has a natural counterpart in `Decoder warm`, and the ratio between them is
    the cost of re-initialising the decoder, which is a real finding about our own
    code. Showing `1.05x warm` says more than "no other browser measured yet".

    Declared per card rather than inferred, because "the other metric in this group"
    is not a rule -- the capability-query group has seven cards with no such pairing.
    """

    def _raw(self, cold=14.8, warm=14.1, lower=True):
        def m(mid, title, median, **kw):
            return {"id": mid, "group": "Seek latency", "title": title,
                    "unit": "ms", "lower_is_better": lower, "note": "",
                    "platform": "macosx1470-64-shippable",
                    "stale": False, "days_behind": 0, "window_end": "2026-08-21",
                    "series": {"firefox": {"n": 76, "median": median,
                                           "p25": median, "p75": median, "cv": 1.0,
                                           "signature_id": 1, "days_behind": 0}},
                    **kw}
        return {"generated_at": "2026-08-21T00:00:00Z", "window_days": 30,
                "metrics": [
                    m("media-seek.cold", "Decoder cold", cold,
                      baseline="media-seek.warm", baseline_label="warm"),
                    m("media-seek.warm", "Decoder warm", warm)]}

    def _cold(self, **kw):
        v = build_metrics_view(self._raw(**kw))
        return [m for m in v["metrics"] if m["id"] == "media-seek.cold"][0]

    def test_the_ratio_is_attached(self):
        b = self._cold()["baseline_comparison"]
        assert b["factor"] == pytest.approx(1.05, abs=0.01)
        assert b["label"] == "warm"

    def test_it_says_which_way_the_ratio_runs(self):
        """Cold is the slower of the two, and the card must not imply otherwise."""
        b = self._cold()["baseline_comparison"]
        assert b["worse"] is True

    def test_a_faster_card_reports_the_other_direction(self):
        b = self._cold(cold=10.0, warm=14.1)["baseline_comparison"]
        assert b["worse"] is False
        assert b["factor"] == pytest.approx(1.41, abs=0.01)

    def test_direction_follows_the_metric_not_the_arithmetic(self):
        """On a higher-is-better metric a larger number is the better one."""
        b = self._cold(cold=14.8, warm=14.1, lower=False)["baseline_comparison"]
        assert b["worse"] is False

    def test_the_sibling_itself_gets_no_ratio(self):
        v = build_metrics_view(self._raw())
        warm = [m for m in v["metrics"] if m["id"] == "media-seek.warm"][0]
        assert warm["baseline_comparison"] is None

    def test_a_card_with_no_baseline_configured_gets_none(self):
        v = build_metrics_view({
            "generated_at": "x", "window_days": 30,
            "metrics": [{"id": "mc.first", "group": "Capability query latency",
                         "title": "First query", "unit": "ms",
                         "lower_is_better": True, "note": "",
                         "platform": "macosx1470-64-shippable",
                         "stale": False, "days_behind": 0,
                         "window_end": "2026-08-21",
                         "series": {"firefox": {"n": 40, "median": 5.0, "p25": 5.0,
                                                "p75": 5.0, "cv": 1.0,
                                                "signature_id": 1,
                                                "days_behind": 0}}}]})
        assert v["metrics"][0]["baseline_comparison"] is None

    def test_a_missing_sibling_is_not_an_error(self):
        """The sibling can vanish -- a renamed suite, a metric that resolved to
        nothing. That must leave the card plain, not raise."""
        raw = self._raw()
        raw["metrics"] = [raw["metrics"][0]]
        v = build_metrics_view(raw)
        assert v["metrics"][0]["baseline_comparison"] is None

    def test_identical_values_read_as_parity_not_as_a_gap(self):
        b = self._cold(cold=14.1, warm=14.1)["baseline_comparison"]
        assert b["factor"] == pytest.approx(1.0, abs=0.001)

    def test_it_does_not_claim_a_cross_browser_result(self):
        """`compared` means a rival BROWSER, and a sibling ratio is not one -- the
        flag stays False so nothing downstream reads it as a competitive verdict.

        It does move the card out of the Firefox-only section, though: that section is
        for cards with nothing to show, and this one now has a chart.
        """
        cold = self._cold()
        assert cold["compared"] is False
        assert cold["charted"] is True
        v = build_metrics_view(self._raw())
        solo = [m["id"] for g in v["groups_firefox_only"] for m in g["metrics"]]
        assert "media-seek.cold" not in solo


class TestASelfComparisonCardDrawsAChart:
    """`Decoder cold` charts against `Decoder warm` like a two-browser card.

    It had a ratio in the corner but a hatched "nothing to compare" bar, and its
    expansion showed one lonely `firefox` row. Both are wrong now that the card has a
    real second measurement: the bar should show the gap and the plot should show both
    figures, labelled `firefox cold` and `firefox warm`.

    Still not a cross-browser result -- `compared` stays False and the colour stays
    neutral -- but it is a comparison, and it belongs among the charts.
    """

    def _raw(self, cold=14.8, warm=14.1):
        def m(mid, title, median, **kw):
            return {"id": mid, "group": "Seek latency", "title": title,
                    "unit": "ms", "lower_is_better": True, "note": "",
                    "platform": "macosx1470-64-shippable",
                    "stale": False, "days_behind": 0, "window_end": "2026-08-21",
                    "series": {"firefox": {"n": 76, "median": median,
                                           "p25": median * 0.9, "p75": median * 1.1,
                                           "cv": 5.0,
                                           "signature_id": kw.pop("sig", 1),
                                           "days_behind": 0}},
                    **kw}
        return {"generated_at": "2026-08-21T00:00:00Z", "window_days": 30,
                "metrics": [
                    m("media-seek.cold", "Decoder cold", cold, sig=5889016,
                      baseline="media-seek.warm", baseline_label="warm",
                      self_label="cold"),
                    m("media-seek.warm", "Decoder warm", warm, sig=5889017)]}

    def _cold(self, **kw):
        v = build_metrics_view(self._raw(**kw))
        return [m for m in v["metrics"] if m["id"] == "media-seek.cold"][0]

    def test_both_rows_are_carried_for_the_plot(self):
        b = self._cold()["baseline_comparison"]
        assert b["self_label"] == "cold"
        assert b["label"] == "warm"
        assert b["series"]["median"] == 14.1, "the sibling's own figures"
        assert b["series"]["n"] == 76

    def test_the_axis_covers_the_sibling_too(self):
        """The plot draws two rows now, so a maximum from one of them would run the
        other off the end."""
        cold = self._cold(cold=10.0, warm=40.0)
        assert cold["axis_max"] >= 40.0

    def test_it_is_still_not_a_cross_browser_comparison(self):
        cold = self._cold()
        assert cold["compared"] is False
        assert cold["comparison"]["factor"] is None

    def test_it_is_charted_rather_than_set_aside(self):
        """A card with a chart does not belong under "no other browser measures
        these" -- that section is for cards with nothing to show."""
        v = build_metrics_view(self._raw())
        charted = [m["id"] for g in v["groups_compared"] for m in g["metrics"]]
        solo = [m["id"] for g in v["groups_firefox_only"] for m in g["metrics"]]
        assert "media-seek.cold" in charted
        assert "media-seek.cold" not in solo

    def test_a_card_with_no_sibling_is_still_set_aside(self):
        """The capability cards have nothing to compare against at all, and must stay
        in the Firefox-only section."""
        v = build_metrics_view({
            "generated_at": "x", "window_days": 30,
            "metrics": [{"id": "mc.first", "group": "Capability query latency",
                         "title": "First query", "unit": "ms",
                         "lower_is_better": True, "note": "",
                         "platform": "macosx1470-64-shippable",
                         "stale": False, "days_behind": 0,
                         "window_end": "2026-08-21",
                         "series": {"firefox": {"n": 40, "median": 5.0, "p25": 5.0,
                                                "p75": 5.0, "cv": 1.0,
                                                "signature_id": 1,
                                                "days_behind": 0}}}]})
        assert [m["id"] for g in v["groups_firefox_only"]
                for m in g["metrics"]] == ["mc.first"]
        assert v["groups_compared"] == []

    def test_the_sibling_card_is_unchanged(self):
        """`Decoder warm` compares against Chrome in the ordinary way; it must not
        acquire a mirror-image self comparison."""
        v = build_metrics_view(self._raw())
        warm = [m for m in v["metrics"] if m["id"] == "media-seek.warm"][0]
        assert warm["baseline_comparison"] is None

    def test_the_graph_link_covers_both_series(self):
        """"open these exact series in Perfherder" must open both rows the card draws.

        This assertion used to be `assert cold["graph_url"]` -- true whenever a link
        existed at all, so it passed while the link plotted only the cold series and
        silently omitted the warm one it was being compared against. A link that opens
        half the chart is worse than no link: it looks like corroboration.
        """
        cold = self._cold()
        own = cold["series"]["firefox"]["signature_id"]
        sibling = cold["baseline_comparison"]["series"]["signature_id"]
        assert sibling != own, "the fixture must use two distinct signatures"
        assert f",{own}," in cold["graph_url"], "own series missing"
        assert f",{sibling}," in cold["graph_url"], "sibling series missing"

    def test_the_link_does_not_grow_for_a_card_with_no_sibling(self):
        v = build_metrics_view(self._raw())
        warm = [m for m in v["metrics"] if m["id"] == "media-seek.warm"][0]
        assert warm["graph_url"].count("series=") == 1


class TestEveryConfigKeyReachesTheRenderer:
    """A key declared in METRICS but not copied by `collect` is silently dropped.

    This has now bitten three times -- `baseline`, `baseline_label` and `self_label`
    each had to be added in two places, and the middle failure rendered a row labelled
    "firefox this" because the label never left the config. The fetcher copies an
    explicit key list, which is the right call (it stops junk reaching the page) but
    means additions must be made twice.
    """

    def _module(self):
        import importlib.util, pathlib, sys
        spec = importlib.util.spec_from_file_location(
            "fpm_keys", pathlib.Path("fetch_perf_metrics.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["fpm_keys"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_no_configured_key_is_dropped_on_the_way_out(self):
        import pathlib, re
        mod = self._module()
        src = pathlib.Path("fetch_perf_metrics.py").read_text(encoding="utf-8")
        # Keys the fetcher consumes itself rather than passing on.
        consumed = {"suite", "test", "test_suffix"}
        declared = {k for e in mod.METRICS for k in e} - consumed
        for key in sorted(declared):
            assert re.search(rf'["\']{re.escape(key)}["\']', src), key
            # It must appear somewhere that writes the output, not only in the table.
            body = src[src.index("def collect("):]
            assert key in body, (
                f"{key!r} is configured but `collect` never writes it, so the page "
                f"never sees it")

    def test_the_baseline_keys_specifically_survive(self):
        """Named so the failure message points at the feature, not just a key."""
        mod = self._module()
        cold = [e for e in mod.METRICS if e["id"] == "media-seek.cold"][0]
        assert cold["baseline"] == "media-seek.warm"
        assert cold["baseline_label"] == "warm"
        assert cold["self_label"] == "cold"
