"""Unit tests for the measured cross-browser codec support table.

The matrix this replaces was written by reading engine source, and that produced
two wrong claims: Chromium lists PCM and AC-3 in its Matroska codec set, but both
are build-flag gated and shipping Chrome answers `no`. So support is measured by
asking browsers, and these tests cover the transform from probe answers to table.
"""

import pytest

from reviewstats.mediacaps import build_api_table, build_support_matrix


def combo(container, codec, kind="audio", **fields):
    """A probe combo. `canPlayType`/`mse` are the legacy fields; `decodeFile` and
    `decodeMse` are the MediaCapabilities ones the playback and streaming surfaces
    actually read. Passing `canPlayType=` sets the matching modern field too, so
    existing tests keep expressing intent rather than plumbing."""
    base = {"container": container, "kind": kind, "codec": codec,
            "codecString": "x", "canPlayType": "no", "mse": "no",
            "recorder": "no", "decodeFile": "no", "decodeMse": "no"}
    base.update(fields)
    if "canPlayType" in fields and "decodeFile" not in fields:
        v = fields["canPlayType"]
        base["decodeFile"] = ("yes" if v == "probably"
                              else "no" if v == "no" else v)
    if "mse" in fields and "decodeMse" not in fields:
        base["decodeMse"] = fields["mse"]
    return base


def result(target, label, combos, **kw):
    base = {"target": target, "label": label, "browser_version": "1.0",
            "combos": combos, "apis": {}, "bare": {}}
    base.update(kw)
    return base


class TestVerdictNormalisation:
    def test_probably_is_yes(self):
        m = build_support_matrix([
            result("firefox", "FF", [combo("MP4", "AAC", canPlayType="probably")]),
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType="no")]),
        ])
        assert m["rows"][0]["support"]["firefox"] == "yes"

    def test_maybe_is_partial_not_yes(self):
        """"maybe" means the container is known but the codec was not confirmed —
        collapsing it into yes would overstate support."""
        m = build_support_matrix([
            result("firefox", "FF", [combo("MP4", "AAC", canPlayType="maybe")]),
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType="probably")]),
        ])
        assert m["rows"][0]["support"]["firefox"] == "partial"

    def test_probe_error_is_unknown_not_no(self):
        """A probe that threw tells us nothing. Read via a row that IS a
        disagreement, since an unknown alone is not one."""
        m = build_support_matrix([
            result("firefox", "FF",
                   [combo("MP4", "AAC", canPlayType="error: bad config")]),
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType="probably")]),
            result("webkit", "WK", [combo("MP4", "AAC", canPlayType="no")]),
        ])
        assert m["rows"][0]["support"]["firefox"] == "unknown"
        assert m["rows"][0]["support"]["chrome"] == "yes"

    def test_absent_api_is_unknown(self):
        m = build_support_matrix([
            result("firefox", "FF", [combo("MP4", "AAC", mse="absent")]),
            result("chrome", "Cr", [combo("MP4", "AAC", mse="yes")]),
            result("webkit", "WK", [combo("MP4", "AAC", mse="no")]),
        ], surface="streaming")
        assert m["rows"][0]["support"]["firefox"] == "unknown"

    def test_an_unanswered_row_is_counted_separately_from_agreement(self):
        """It is a hole in our data, not a finding and not consensus."""
        m = build_support_matrix([
            result("firefox", "FF", [combo("MP4", "AAC", canPlayType="error: x")]),
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType="probably")]),
        ])
        assert m["counts"]["indeterminate"] == 1
        assert m["counts"]["agreed"] == 0


class TestDisagreementsOnly:
    """123 combinations across three engines is unreadable. Only rows where
    engines differ are listed; the rest are counted."""

    def _two(self, ff, cr):
        return build_support_matrix([
            result("firefox", "FF", [combo("MP4", "AAC", canPlayType=ff)]),
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType=cr)]),
        ])

    def test_agreement_is_counted_not_listed(self):
        m = self._two("probably", "probably")
        assert m["rows"] == []
        assert m["counts"]["differing"] == 0
        assert m["counts"]["agreed"] == 1

    def test_disagreement_is_listed(self):
        m = self._two("no", "probably")
        assert len(m["rows"]) == 1
        assert m["counts"]["differing"] == 1

    def test_unknown_alone_does_not_make_a_disagreement(self):
        """If the only difference is that one engine failed to answer, there is
        no finding — just missing data."""
        m = self._two("probably", "error: threw")
        assert m["rows"] == []


class TestOrdering:
    def test_rows_where_firefox_lacks_support_come_first(self):
        m = build_support_matrix([
            result("firefox", "FF", [
                combo("MP4", "AAC", canPlayType="probably"),
                combo("MKV", "FLAC", canPlayType="no"),
            ]),
            result("chrome", "Cr", [
                combo("MP4", "AAC", canPlayType="no"),
                combo("MKV", "FLAC", canPlayType="probably"),
            ]),
        ])
        assert m["rows"][0]["codec"] == "FLAC", "our gap must lead"
        assert m["counts"]["we_lack"] == 1

    def test_firefox_is_the_first_browser_column(self):
        m = build_support_matrix([
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType="probably")]),
            result("firefox-playwright", "FF",
                   [combo("MP4", "AAC", canPlayType="no")]),
        ])
        assert m["browsers"][0]["target"] == "firefox-playwright"


class TestEvidenceStrength:
    """A `no` is not equally strong from every engine, and the page must say so."""

    def test_proxy_for_safari_is_flagged(self):
        m = build_support_matrix([
            result("firefox", "FF", [combo("MP4", "AAC", canPlayType="probably")]),
            result("webkit", "WebKit", [combo("MP4", "AAC", canPlayType="no")],
                   is_proxy_for_safari=True),
        ])
        wk = [b for b in m["browsers"] if b["target"] == "webkit"][0]
        assert wk["is_proxy_for_safari"] is True

    def test_nonshipping_build_is_flagged(self):
        m = build_support_matrix([
            result("firefox-playwright", "FF",
                   [combo("MP4", "AAC", canPlayType="probably")],
                   is_nonshipping_build=True),
            result("chrome", "Cr", [combo("MP4", "AAC", canPlayType="no")]),
        ])
        assert m["browsers"][0]["is_nonshipping_build"] is True


class TestSurfaces:
    def test_each_surface_can_be_tabulated(self):
        rs = [
            result("firefox", "FF", [combo("WebM", "VP8", recorder="yes")]),
            result("chrome", "Cr", [combo("WebM", "VP8", recorder="no")]),
        ]
        m = build_support_matrix(rs, surface="recording")
        assert m["surface"] == "recording"
        assert m["rows"][0]["support"]["firefox"] == "yes"

    def test_unknown_surface_is_rejected(self):
        with pytest.raises(ValueError):
            build_support_matrix([], surface="telepathy")


class TestEmptyInput:
    def test_no_results_is_empty_not_an_error(self):
        m = build_support_matrix([])
        assert m["rows"] == [] and m["browsers"] == []

    def test_results_without_combos_are_ignored(self):
        m = build_support_matrix([result("firefox", "FF", [])])
        assert m["browsers"] == []


class TestApiTable:
    def test_lists_every_api_seen(self):
        rs = [
            result("firefox", "FF", [combo("MP4", "AAC")],
                   apis={"MediaSource": True, "ManagedMediaSource": False}),
            result("chrome", "Cr", [combo("MP4", "AAC")],
                   apis={"MediaSource": True, "VideoDecoder": True}),
        ]
        t = build_api_table(rs)
        assert [x["api"] for x in t] == ["MediaSource", "ManagedMediaSource",
                                        "VideoDecoder"]

    def test_a_browser_with_no_api_data_is_excluded_not_all_false(self):
        """Absence of data is not absence of the feature — rendering an empty
        probe as all-false would turn a collection failure into a claim."""
        rs = [
            result("firefox", "FF", [], apis={"VideoDecoder": True}),
            result("chrome", "Cr", [], apis={}),
        ]
        t = build_api_table(rs)
        row = [x for x in t if x["api"] == "VideoDecoder"][0]
        assert row["support"] == {"firefox": True}

    def test_api_missing_from_one_probe_reads_false_when_others_recorded_it(self):
        rs = [
            result("firefox", "FF", [], apis={"VideoDecoder": True}),
            result("chrome", "Cr", [], apis={"MediaSource": True}),
        ]
        t = build_api_table(rs)
        row = [x for x in t if x["api"] == "VideoDecoder"][0]
        assert row["support"] == {"firefox": True, "chrome": False}


class TestClassify:
    """A difference is not automatically a gap, and the distinction decides what a
    reader should do: implement support, or fix our own conformance."""

    def test_we_lack_it_and_another_engine_has_it_is_a_gap(self):
        from reviewstats.mediacaps import GAP, classify
        assert classify("no", ["yes", "no"]) == GAP

    def test_we_alone_claim_it_is_an_overclaim(self):
        """Firefox answers `probably` to audio/flac with any codecs parameter,
        including ac-3 and alac. That is a conformance bug, not a win."""
        from reviewstats.mediacaps import OVERCLAIM, classify
        assert classify("yes", ["no", "no"]) == OVERCLAIM

    def test_we_have_it_and_one_engine_does_not_is_ahead(self):
        from reviewstats.mediacaps import AHEAD, classify
        assert classify("yes", ["yes", "no"]) == AHEAD

    def test_everyone_agreeing_is_parity(self):
        from reviewstats.mediacaps import PARITY, classify
        assert classify("yes", ["yes", "yes"]) == PARITY

    def test_nobody_supporting_it_is_its_own_state(self):
        """Distinct from parity: "we all support this" and "none of us do" are
        not the same finding."""
        from reviewstats.mediacaps import NONE, classify
        assert classify("no", ["no", "no"]) == NONE

    def test_partial_counts_as_having_it(self):
        from reviewstats.mediacaps import AHEAD, classify
        assert classify("partial", ["yes", "no"]) == AHEAD


class TestContainerView:
    def _results(self):
        from tests.unit.roadmap.test_mediacaps import combo, result
        ff = result("firefox", "FF", [
            combo("MP4", "AAC-LC", canPlayType="probably", mse="yes"),
            combo("MP4", "AC-3", canPlayType="no", mse="no"),
            combo("WebM", "Opus", canPlayType="probably", mse="yes"),
        ], bare={"video/mp4": {"canPlayType": "maybe", "mse": "yes",
                               "recorder": "no"}})
        cr = result("chrome", "Cr", [
            combo("MP4", "AAC-LC", canPlayType="probably", mse="yes"),
            combo("MP4", "AC-3", canPlayType="probably", mse="yes"),
            combo("WebM", "Opus", canPlayType="probably", mse="yes"),
        ], bare={"video/mp4": {"canPlayType": "probably", "mse": "yes",
                               "recorder": "no"}})
        return [ff, cr]

    def test_every_probed_container_is_present(self):
        """The disagreements-only table made WebM vanish because engines agree,
        so a reader could not tell tested-and-fine from never-tested."""
        from reviewstats.mediacaps import build_container_view
        v = build_container_view(self._results())
        assert "WebM" in [c["name"] for c in v["containers"]]

    def test_containers_with_gaps_sort_first(self):
        from reviewstats.mediacaps import build_container_view
        v = build_container_view(self._results())
        assert v["containers"][0]["name"] == "MP4"

    def test_container_carries_a_measured_bare_header(self):
        """A container header is measured, not derived — that is why the view is
        grouped by container rather than codec."""
        from reviewstats.mediacaps import build_container_view
        v = build_container_view(self._results())
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        assert mp4["surfaces"]["playback"]["bare"]["chrome"] == "yes"
        assert mp4["surfaces"]["playback"]["bare"]["firefox"] == "partial"

    def test_supported_denominator_excludes_rows_nobody_supports(self):
        """0 of 5 is verified parity; 0 of 0 is nobody supports it. A bare zero
        merges two different facts. The count includes the synthetic
        container-only row, which is a real measured answer."""
        from reviewstats.mediacaps import build_container_view
        v = build_container_view(self._results())
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        counts = mp4["surfaces"]["playback"]["counts"]
        assert counts["supported"] == counts["gap"] + counts["overclaim"] \
            + counts["ahead"] + counts["parity"]
        assert counts["supported"] >= 2

    def test_codec_index_answers_the_codec_shaped_question(self):
        from reviewstats.mediacaps import build_container_view
        v = build_container_view(self._results())
        gaps = v["codec_gaps"]["playback"]
        assert gaps[0]["codec"] == "AC-3"
        assert gaps[0]["containers"] == ["MP4"]

    def test_hls_is_listed_even_with_no_codec_combinations(self):
        """Container-level probe only. Invisible is worse than 'not probed'."""
        from reviewstats.mediacaps import build_container_view
        v = build_container_view(self._results())
        hls = [c for c in v["containers"] if c["name"] == "HLS"]
        assert hls and hls[0]["probed"] is False

    def test_empty_input_is_safe(self):
        from reviewstats.mediacaps import build_container_view
        assert build_container_view([])["containers"] == []


class TestSurfaceFallback:
    """Which API answers each surface, and what happens when it refuses.

    Neither API generation covers everything: MediaCapabilities is precise but
    errors on a bare container type, and `encodingInfo` throws on Chrome for
    every configuration. So each surface names a primary field and a fallback.
    """

    def test_playback_prefers_mediacapabilities_over_canplaytype(self):
        from reviewstats.mediacaps import answer
        c = combo("MP4", "AAC", canPlayType="maybe", decodeFile="yes")
        assert answer(c, "playback") == "yes"

    def test_an_api_that_throws_falls_back_rather_than_reporting_unknown(self):
        """The WebKit/Matroska case. `decodingInfo` raises a TypeError for every
        Matroska config while `canPlayType` answers "" — a measured no. Reporting
        unknown would blame the format for an API quirk."""
        from reviewstats.mediacaps import answer
        c = combo("Matroska", "VP9", canPlayType="no",
                  decodeFile="error: Type error")
        assert answer(c, "playback") == "no"

    def test_unknown_survives_when_neither_api_answered(self):
        from reviewstats.mediacaps import answer
        c = combo("Matroska", "VP9", canPlayType="absent",
                  decodeFile="error: Type error")
        assert answer(c, "playback") == "unknown"

    def test_bare_rows_read_the_legacy_field_only(self):
        """MediaCapabilities requires a codecs parameter, so it cannot answer a
        bare type at all — it is not a fallback, it is unavailable. HLS support
        is only visible through these rows."""
        from reviewstats.mediacaps import answer
        entry = {"canPlayType": "maybe", "decodeFile": "error: Container missing"}
        assert answer(entry, "playback", bare=True) == "partial"

    def test_recording_uses_mediarecorder_not_encodinginfo(self):
        """`encodingInfo({type:'record'})` threw for all 49 configs on Chrome.
        Driving the column with it would report Chrome as recording nothing."""
        from reviewstats.mediacaps import SURFACE_FIELDS
        assert SURFACE_FIELDS["recording"]["codec"] == "recorder"


class TestSurfaceKeysAreOwnedHere:
    """Renaming the surfaces crashed `analyze_git.py` -- which spelled one key as
    a literal -- while all 877 tests stayed green, because the generator shell is
    I/O and nothing unit-tests it. These pin the contract instead."""

    def test_matrix_keys_are_exactly_the_declared_surfaces(self):
        from reviewstats.mediacaps import SURFACES, build_support_matrix
        for surf in SURFACES:
            m = build_support_matrix(
                [result("firefox", "FF", [combo("MP4", "AAC")])], surface=surf)
            assert "counts" in m, f"{surf} produced no counts"

    def test_every_surface_has_a_label_a_source_and_fields(self):
        from reviewstats.mediacaps import (
            SURFACES, SURFACE_FIELDS, SURFACE_LABELS, SURFACE_SOURCE)
        assert set(SURFACE_FIELDS) == set(SURFACES)
        assert set(SURFACE_LABELS) == set(SURFACES)
        assert set(SURFACE_SOURCE) == set(SURFACES)

    def test_the_generator_does_not_hardcode_a_surface_name(self):
        """The actual regression: a literal key in the shell that no test reads."""
        import pathlib
        from reviewstats.mediacaps import SURFACES
        src = pathlib.Path("analyze_git.py").read_text(encoding="utf-8")
        assert "SURFACES[" in src, "the caps summary vanished — update this guard"
        # A surface name as a literal subscript is the bug; importing the tuple
        # and indexing it is the fix.
        for name in SURFACES + ("canPlayType", "mse", "recorder"):
            assert f'["{name}"]' not in src, (
                f'surface key "{name}" spelled literally in the generator — '
                "renaming it will crash the build with every test green"
            )
