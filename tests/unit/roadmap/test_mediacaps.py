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


class TestAudioAndVideoAreSeparateGroups:
    """Video and audio codecs are different questions and were interleaved.

    Worst-first sorting mixed them: a container's table ran AC-3, ALAC, E-AC-3,
    xHE-AAC, MP3, Opus, AV1, AAC-LC ... so a reader scanning for video codec
    coverage had to filter audio out by eye. The rows carry `kind` already, so the
    split is free; ordering stays worst-first *within* each group and the groups
    themselves are ordered worst-first, which is the rule everywhere else on the
    page.
    """

    def _groups(self):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
            combo("MP4", "AV1", kind="video", canPlayType="no"),
            combo("MP4", "Opus", kind="audio", canPlayType="probably"),
            combo("MP4", "VP9", kind="video", canPlayType="probably"),
        ])
        cr = result("chrome", "Cr", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
            combo("MP4", "AV1", kind="video", canPlayType="probably"),
            combo("MP4", "Opus", kind="audio", canPlayType="probably"),
            combo("MP4", "VP9", kind="video", canPlayType="probably"),
        ])
        v = build_container_view([ff, cr])
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        return mp4["surfaces"]["playback"]["groups"]

    def test_video_and_audio_are_separate_groups(self):
        kinds = [g["kind"] for g in self._groups()]
        assert "video" in kinds and "audio" in kinds

    def test_no_group_mixes_kinds(self):
        for g in self._groups():
            assert {r["kind"] for r in g["rows"]} == {g["kind"]}

    def test_groups_are_labelled_for_a_reader(self):
        labels = {g["kind"]: g["label"] for g in self._groups()}
        assert labels["video"] == "Video codecs"
        assert labels["audio"] == "Audio codecs"

    def test_the_group_holding_the_gap_comes_first(self):
        """Worst-first, the same rule the cards and sub-cards follow. The AV1 gap
        is in video, so video leads even though audio sorts first by name."""
        assert self._groups()[0]["kind"] == "video"

    def test_rows_stay_worst_first_inside_a_group(self):
        video = [g for g in self._groups() if g["kind"] == "video"][0]
        assert video["rows"][0]["codec"] == "AV1"

    def test_every_displayed_row_appears_in_exactly_one_group(self):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
            combo("MP4", "AV1", kind="video", canPlayType="no"),
        ], bare={"video/mp4": {"canPlayType": "no", "mse": "no",
                               "recorder": "no"}})
        v = build_container_view([ff])
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        st = mp4["surfaces"]["playback"]
        grouped = [r for g in st["groups"] for r in g["rows"]]
        # Grouping partitions the displayed rows: no row is dropped except the
        # ones no engine supports, and none is duplicated across groups.
        keys = [(r["kind"], r["codec"]) for r in grouped]
        assert len(keys) == len(set(keys)), "a row appears in two groups"
        from reviewstats.mediacaps import NONE
        displayable = [(r["kind"], r["codec"]) for r in st["rows"]
                       if r["verdict"] != NONE]
        assert set(keys) == set(displayable)


class TestRowsNoEngineSupportsAreHidden:
    """A combination no browser supports is not a finding about Firefox.

    It is not a gap (nobody has it), not an overclaim, and not a win -- there is
    nothing for the team to do with it, and the probe generates plenty because it
    asks every codec a container could plausibly carry. They are counted and the
    count is stated, so the table is shorter without being silently truncated.
    """

    def _view(self, *combos):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", list(combos))
        cr = result("chrome", "Cr", list(combos))
        v = build_container_view([ff, cr])
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        return mp4["surfaces"]["playback"]

    def test_a_row_nobody_supports_is_not_displayed(self):
        st = self._view(combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
                        combo("MP4", "ALAC", kind="audio", canPlayType="no"))
        shown = [r["codec"] for g in st["groups"] for r in g["rows"]]
        assert "ALAC" not in shown
        assert "AAC-LC" in shown

    def test_how_many_were_hidden_is_reported(self):
        """Silent truncation reads as "we covered everything". The page says how
        many rows it dropped so a reader can tell the difference."""
        st = self._view(combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
                        combo("MP4", "ALAC", kind="audio", canPlayType="no"),
                        combo("MP4", "AC-3", kind="audio", canPlayType="no"))
        assert st["hidden_none"] == 2

    def test_the_hidden_rows_are_still_counted(self):
        """Dropping them from the table must not change the measured totals --
        `counts` feeds the container ranking and the summary line."""
        st = self._view(combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
                        combo("MP4", "ALAC", kind="audio", canPlayType="no"))
        assert st["counts"]["none"] == 1
        assert len(st["rows"]) == 2

    def test_a_group_with_nothing_left_is_dropped_entirely(self):
        """Not an empty "Video codecs" heading with no rows under it."""
        st = self._view(combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
                        combo("MP4", "AV1", kind="video", canPlayType="no"))
        assert [g["kind"] for g in st["groups"]] == ["audio"]

    def test_a_surface_nobody_supports_at_all_yields_no_groups(self):
        """FLAC-in-MSE is this: every engine says no to everything. The caller
        renders the fact rather than an empty table."""
        st = self._view(combo("MP4", "AAC-LC", kind="audio", canPlayType="no"),
                        combo("MP4", "AV1", kind="video", canPlayType="no"))
        assert st["groups"] == []
        assert st["hidden_none"] == 2


class TestPayloadIsDerivedNotStored:
    """The caps payload is rebuilt from the raw probe results every render.

    It used to be a committed derived file (`playback/data_mediacaps.json`) that
    only `build_matrix.py` refreshed. Changing the builder and regenerating the
    site therefore produced a page built from the *old* transform: the container
    rows still read "container only" after that label had been replaced, and
    nothing failed, because on-disk JSON is not something a test looks at. The raw
    probe results are tracked, so the derived shape does not need to be.
    """

    def test_build_payload_produces_every_section_the_page_reads(self):
        from reviewstats.mediacaps import SURFACES, build_payload
        payload = build_payload([_probe_result("firefox", "FF"),
                                 _probe_result("chrome", "Cr")])
        for key in ("probed_at", "browsers", "surfaces", "by_container",
                    "apis"):
            assert key in payload, key
        # No conformance: that section was removed from the page, and shipping
        # data nothing renders is how it comes back by accident. The check still
        # runs -- build_matrix.py reports it.
        assert "conformance" not in payload
        assert set(payload["surfaces"]) == set(SURFACES)

    def test_empty_results_give_no_payload_rather_than_a_broken_one(self):
        from reviewstats.mediacaps import build_payload
        assert build_payload([]) is None

    def test_the_generator_does_not_read_a_prebaked_caps_file(self):
        """The staleness this class exists to prevent."""
        import pathlib
        src = pathlib.Path("analyze_git.py").read_text(encoding="utf-8")
        assert "data_mediacaps.json" not in src, (
            "the generator reads a stored derived file again — a builder change "
            "will silently render the previous transform"
        )
        assert "build_payload" in src


def _probe_result(target, label):
    return {
        "target": target, "label": label, "browser_version": "1",
        "is_proxy_for_safari": False, "is_nonshipping_build": False,
        "probedAt": "2026-08-10T12:00:00Z",
        "combos": [combo("MP4", "AAC-LC", kind="audio", canPlayType="probably")],
        "bare": {"video/mp4": {"canPlayType": "no", "mse": "no",
                               "recorder": "no"}},
        "conformance": [{"type": 'audio/flac; codecs="ac-3"',
                         "canPlayType": "no"}],
        "apis": {"MediaSource in Worker": True},
    }


class TestContainerRowsAreGone:
    """The bare-MIME rows are no longer part of the table.

    They were introduced because HLS had no codec combinations at all, so without
    them HLS read as "no engine support". The probe now asks HLS codec
    combinations too, and those carry the same fact -- Firefox `no` to
    H.264-in-HLS where Chrome and WebKit say `yes` -- so the extra group was a
    second way of saying it, under a heading that repeated the row label.
    """

    def _view(self):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably")],
            bare={"video/mp4": {"canPlayType": "no", "mse": "no",
                                "recorder": "no"}})
        cr = result("chrome", "Cr", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably")],
            bare={"video/mp4": {"canPlayType": "probably", "mse": "yes",
                                "recorder": "no"}})
        v = build_container_view([ff, cr])
        return [c for c in v["containers"] if c["name"] == "MP4"][0]

    def test_no_container_kind_group_is_produced(self):
        assert all(g["kind"] != "container"
                   for st in self._view()["surfaces"].values()
                   for g in st["groups"])

    def test_no_container_kind_row_is_produced(self):
        assert all(r["kind"] != "container"
                   for st in self._view()["surfaces"].values()
                   for r in st["rows"])

    def test_bare_rows_do_not_inflate_the_not_listed_count(self):
        """The count means "no engine supports this". Dropping container rows
        into it would claim two unsupported combinations that do not exist."""
        st = self._view()["surfaces"]["playback"]
        assert st["hidden_none"] == 0


class TestTheVerdictBarAnswersWhetherFirefoxIsCovered:
    """The left-hand bar went through two wrong versions before this one.

    First parity had no bar at all, so the most common row read as unstyled.
    Then it got a neutral grey one -- which was worse in a different way: a row
    where all three engines answer `yes` is a *good* state, and grey said "nothing
    to report here" about full support. A reader reasonably asked why universally
    supported codecs were not green.

    So the bar encodes Firefox's position rather than the shape of the agreement:
    green when we support it (whether or not everyone else does), and a warning
    colour when we do not, or when we accept something no other engine will.
    `ahead` and `parity` therefore share green on purpose -- for the team reading
    this, both mean covered.
    """

    def _css(self):
        import pathlib
        return pathlib.Path("templates/index.html.tmpl").read_text(encoding="utf-8")

    def _rule(self, verdict):
        import re
        m = re.search(r"tr\.pm-v-%s td:first-child \{([^}]*)\}" % verdict,
                      self._css())
        assert m, f"no bar rule for {verdict}"
        return m.group(1)

    def test_every_verdict_that_can_be_displayed_has_a_bar(self):
        """`none` is excluded from the table, so the other four all need one."""
        for verdict in ("gap", "overclaim", "ahead", "parity"):
            assert self._rule(verdict)

    def test_parity_is_green_because_every_engine_supports_it(self):
        assert "--pm-ahead" in self._rule("parity")

    def test_parity_and_ahead_read_the_same(self):
        """Both mean Firefox is covered. Distinguishing them by colour implied a
        difference in whether the team should act, and there is none."""
        assert self._rule("parity").strip() == self._rule("ahead").strip()

    def test_parity_is_not_grey(self):
        """The regression this replaces: grey read as "no data" on a row with
        three yeses."""
        assert "--rule" not in self._rule("parity")

    def test_a_gap_is_not_green(self):
        assert "--pm-ahead" not in self._rule("gap")


class TestFlacIsACodecNotAContainer:
    """FLAC is probed as a codec only; `audio/flac` is not listed as a container.

    Its container card held exactly one row -- the FLAC codec in a FLAC stream --
    which the codec checks in MP4, Matroska and Ogg already answer. The
    conformance list still asks about `audio/flac` type strings, so the Firefox
    bug found there (FlacDecoder::IsSupportedType never reads the codecs
    parameter) is still detected; that list is independent of the container set.
    """

    def test_flac_is_not_a_container(self):
        from reviewstats.mediacaps import CONTAINER_MIMES
        assert "FLAC" not in CONTAINER_MIMES

    def test_no_audio_flac_container_mime_is_probed(self):
        from reviewstats.mediacaps import CONTAINER_MIMES
        mimes = [m for ms in CONTAINER_MIMES.values() for m in ms]
        assert "audio/flac" not in mimes

    def test_the_probe_page_still_asks_for_flac_as_a_codec(self):
        """Removing the container must not remove the codec -- FLAC in MP4 is a
        real gap question, and FLAC in Matroska is one of the measured
        differences."""
        import pathlib
        page = pathlib.Path("media-capabilities/index.html").read_text(
            encoding="utf-8")
        assert "'FLAC'" in page

    def test_the_probe_page_no_longer_declares_a_flac_container(self):
        import pathlib, re
        page = pathlib.Path("media-capabilities/index.html").read_text(
            encoding="utf-8")
        assert not re.search(r"name:\s*'FLAC'", page)

    def test_conformance_still_covers_the_flac_bug(self):
        import pathlib
        page = pathlib.Path("media-capabilities/index.html").read_text(
            encoding="utf-8")
        assert 'audio/flac; codecs="ac-3"' in page


class TestBrowsersAreNamedPlainly:
    """The browser list shows a short name and a version, nothing else.

    The probe's own labels carry their caveat in the name -- "Firefox (Playwright
    Gecko build)", "WebKit (Playwright build, not Safari)" -- which put the
    qualification in the one place it cannot be shortened. The caveat is real and
    survives as a tooltip; the visible line is the browser and its version.
    """

    def _browsers(self):
        from reviewstats.mediacaps import build_payload
        results = []
        for target, label in (("firefox-playwright", "Firefox (Playwright Gecko build)"),
                              ("chrome", "Chrome"),
                              ("webkit", "WebKit (Playwright build, not Safari)")):
            results.append({
                "target": target, "label": label, "browser_version": "1.0",
                "probedAt": "2026-08-10T00:00:00Z", "combos": [],
                "bare": {}, "conformance": [], "apis": {},
            })
        return build_payload(results)["browsers"]

    def test_every_browser_has_a_short_name(self):
        assert [b["name"] for b in self._browsers()] == [
            "Firefox", "Chrome", "WebKit"]

    def test_the_short_name_carries_no_parenthetical(self):
        for b in self._browsers():
            assert "(" not in b["name"]

    def test_the_full_label_is_still_available_for_the_caveat(self):
        labels = [b["label"] for b in self._browsers()]
        assert "Firefox (Playwright Gecko build)" in labels

    def test_the_container_view_browsers_carry_the_short_name_too(self):
        """There are two browser lists in the payload, and the table reads the one
        inside `by_container`. Adding the field to only the top-level list left the
        page showing the long labels with every test passing."""
        from reviewstats.mediacaps import build_container_view
        v = build_container_view([{
            "target": "firefox-playwright",
            "label": "Firefox (Playwright Gecko build)",
            "browser_version": "1.0", "bare": {},
            "combos": [combo("MP4", "AAC-LC", kind="audio",
                             canPlayType="probably")],
        }])
        assert [b["name"] for b in v["browsers"]] == ["Firefox"]
