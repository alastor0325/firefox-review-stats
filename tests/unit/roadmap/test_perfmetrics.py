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
        m = re.search(r"function warnIcon\(m\) \{(.*?)\n  \}", t, re.DOTALL)
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
