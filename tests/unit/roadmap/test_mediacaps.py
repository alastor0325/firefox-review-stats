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

    def test_video_always_comes_before_audio(self):
        """A fixed order, not a computed one. Ordering groups worst-first moved
        the sections around between cards -- audio led MP4, video led WebM -- so
        the eye had to re-find the video block on every card. Worst-first still
        governs the rows inside a group, where it costs nothing."""
        assert [g["kind"] for g in self._groups()] == ["video", "audio"]

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


class TestChipCountsWhatWeSupport:
    """The chip counted gaps; it now counts support.

    `4/14` meant "14 combinations work in some engine and we lack 4 of them" --
    a number that goes *up* as things get worse, which is the wrong direction for
    a figure read at a glance next to a green/amber badge. It now reads `10/14`:
    how many of the 14 we support.
    """

    def _counts(self, *combos):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [c[0] for c in combos])
        cr = result("chrome", "Cr", [c[1] for c in combos])
        v = build_container_view([ff, cr])
        return v["containers"][0]["surfaces"]["playback"]["counts"]

    def _pair(self, codec, ours, theirs):
        return (combo("MP4", codec, kind="audio", canPlayType=ours),
                combo("MP4", codec, kind="audio", canPlayType=theirs))

    def test_ours_counts_the_rows_firefox_supports(self):
        c = self._counts(self._pair("AAC-LC", "probably", "probably"),
                         self._pair("AC-3", "no", "probably"))
        assert c["ours"] == 1
        assert c["supported"] == 2

    def test_ours_and_gaps_account_for_every_supported_row(self):
        c = self._counts(self._pair("AAC-LC", "probably", "probably"),
                         self._pair("AC-3", "no", "probably"),
                         self._pair("MP3", "probably", "no"))
        assert c["ours"] + c["gap"] == c["supported"]


class TestThreeSupportLevels:
    """One badge with three levels, replacing behind / verified parity.

    Those two read as a boolean -- anything short of perfect was "behind" --
    so a container we support 13 of 14 combinations in looked the same as one we
    support none of. The level is computed from how much of the *achievable* set
    we cover, using the same good/mixed/weak vocabulary the roadmap ratings use.
    """

    def test_full_support_when_we_match_every_engine(self):
        from reviewstats.mediacaps import support_level
        assert support_level(14, 14) == "full"

    def test_partial_when_we_have_some_but_not_all(self):
        from reviewstats.mediacaps import support_level
        assert support_level(10, 14) == "partial"

    def test_none_when_we_have_nothing_others_do(self):
        from reviewstats.mediacaps import support_level
        assert support_level(0, 14) == "none"

    def test_an_unsupportable_container_is_its_own_level(self):
        """Nobody supports anything here, so we are not behind -- there is
        nothing to be behind on. Calling that "full support" would be absurd."""
        from reviewstats.mediacaps import support_level
        assert support_level(0, 0) == "empty"

    def test_the_container_carries_its_level(self):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
            combo("MP4", "AC-3", kind="audio", canPlayType="no")])
        cr = result("chrome", "Cr", [
            combo("MP4", "AAC-LC", kind="audio", canPlayType="probably"),
            combo("MP4", "AC-3", kind="audio", canPlayType="probably")])
        c = build_container_view([ff, cr])["containers"][0]
        assert c["level"] == "partial"

    def test_levels_are_ordered_worst_first_across_containers(self):
        """The section already sorts containers worst-first; the level has to
        agree with that order or the badges look shuffled."""
        from reviewstats.mediacaps import LEVEL_RANK
        assert (LEVEL_RANK["none"] < LEVEL_RANK["partial"]
                < LEVEL_RANK["full"] <= LEVEL_RANK["empty"])

    def test_containers_are_ordered_by_level(self):
        """The badges are the first thing scanned down the column, so the order
        has to agree with them. Sorting by the old verdict left "no support" cards
        below "partial" ones, which read as unsorted."""
        from reviewstats.mediacaps import LEVEL_RANK, build_container_view

        def pair(container, codec, ours, theirs):
            return (combo(container, codec, kind="audio", canPlayType=ours),
                    combo(container, codec, kind="audio", canPlayType=theirs))

        spec = [
            pair("MP4", "AAC-LC", "probably", "probably"),   # MP4 -> full
            pair("Ogg", "Vorbis", "probably", "probably"),   # Ogg -> partial
            pair("Ogg", "Opus", "no", "probably"),
            pair("WAV", "PCM", "no", "probably"),            # WAV -> none
        ]
        v = build_container_view([
            result("firefox", "FF", [a for a, _ in spec]),
            result("chrome", "Cr", [b for _, b in spec]),
        ])
        ranks = [LEVEL_RANK[c["level"]] for c in v["containers"]]
        assert ranks == sorted(ranks), (
            "container order disagrees with the level badges: "
            + ", ".join(f'{c["name"]}={c["level"]}' for c in v["containers"])
        )


class TestEverySpellingIsAsked:
    """Each codec is probed under every accepted spelling, best answer wins.

    One spelling is not enough, and which one is right turned out to depend on the
    *surface*, not the container. Measured in WebM:

        video/webm; codecs="vp9"              decodingInfo: Chrome no,  recorder: Chrome yes
        video/webm; codecs="vp09.00.10.08"    decodingInfo: Chrome yes, recorder: Chrome no

    So either choice alone writes a false `no` into the table. Asking `vp09.*`
    reported "Chrome cannot record VP9"; switching to `vp9` reported "Chrome
    cannot play VP9". Both are wrong about a browser that has shipped VP9 for
    years. A browser supports the codec if it accepts any valid spelling.
    """

    def _page(self):
        import pathlib
        return pathlib.Path("media-capabilities/index.html").read_text(
            encoding="utf-8")

    def test_vp9_and_av1_have_both_spellings(self):
        page = self._page()
        assert "'VP9': ['vp09.00.10.08', 'vp9']" in page
        assert "'AV1': ['av01.0.04M.08', 'av1']" in page

    def test_the_probe_takes_the_best_answer_across_spellings(self):
        page = self._page()
        assert "if (rank(v) > rank(out))" in page

    def test_a_hedged_yes_outranks_a_no(self):
        """`maybe` is a real answer; ranking it below `no` would let one spelling's
        flat rejection mask another's partial acceptance."""
        page = self._page()
        i, j = page.index("if (s === 'maybe')"), page.index("if (s === 'no')")
        assert i < j

    def test_an_error_never_beats_a_real_answer(self):
        page = self._page()
        assert "if (s.startsWith('error')) return 1" in page

    def test_a_container_override_exists_only_for_a_collision(self):
        """Aliases handle spellings; an override handles a *collision*, which
        aliases cannot.

        `1` is the WAV format tag for linear PCM. Chrome also accepts `1` in
        Matroska -- but as a legacy numeric id meaning something else, since it
        answers `no` to both `pcm` and `A_PCM/INT/LIT` there while answering
        `probably` to `1` and to `mp3`. Best-of-aliases read that as "Chrome
        supports PCM in Matroska", which is false, and it put a gap in the roadmap
        that does not exist. So Matroska asks for PCM by its Matroska name only.

        Chrome answers `no` to a deliberately invalid codec, so this is not it
        being lax -- it is resolving a real, different codec.
        """
        page = self._page()
        mkv = page[page.index("name: 'Matroska'"):page.index("name: 'Ogg'")]
        assert "codecStrings: { 'PCM': 'A_PCM/INT/LIT' }" in mkv
        wav_start = page.index("name: 'WAV'")
        wav = page[wav_start:page.index("];", wav_start)]
        assert "codecStrings" not in wav, "WAV must keep the format tag 1"


class TestTwoSectionsDecodingAndEncoding:
    """A card expands to two sections, browser-major, surface nested.

    Five separate per-surface tables meant the same codec appeared five times and
    a question like "can we encode AV1 at all" needed cross-referencing between
    two of them. Decoding and encoding are the two questions actually asked, so
    they are the two sections, and each browser carries its surfaces beneath it.
    """

    def _sections(self):
        from reviewstats.mediacaps import build_container_view
        spec = [
            # kind, codec, per-surface (ff, cr, wk)
            ("video", "AV1", {"decodeFile": ("yes", "yes", "no"),
                              "decodeMse": ("yes", "yes", "no"),
                              "recorder": ("no", "yes", "yes"),
                              "wcDecode": ("yes", "yes", "yes"),
                              "wcEncode": ("yes", "yes", "yes")}),
            # Nobody plays VP8 in MP4, but every engine encodes it via WebCodecs:
            # the row has to survive on the strength of one surface.
            ("video", "VP8", {"decodeFile": ("no", "no", "no"),
                              "decodeMse": ("no", "no", "no"),
                              "recorder": ("no", "no", "no"),
                              "wcDecode": ("yes", "yes", "yes"),
                              "wcEncode": ("yes", "yes", "yes")}),
        ]
        targets = ["firefox-playwright", "chrome", "webkit"]
        results = []
        for i, t in enumerate(targets):
            combos = []
            for kind, codec, fields in spec:
                c = {"container": "MP4", "kind": kind, "codec": codec,
                     "codecString": codec.lower(), "canPlayType": "no",
                     "mse": "no", "recorder": "no"}
                for f, vals in fields.items():
                    c[f] = vals[i]
                c["canPlayType"] = ("probably" if fields["decodeFile"][i] == "yes"
                                    else "no")
                c["mse"] = fields["decodeMse"][i]
                combos.append(c)
            results.append({"target": t, "label": t.split("-")[0].title(),
                            "browser_version": "1", "combos": combos, "bare": {}})
        v = build_container_view(results)
        return v["containers"][0]["sections"]

    def test_there_are_exactly_two_sections(self):
        assert [s["key"] for s in self._sections()] == ["decoding", "encoding"]

    def test_decoding_holds_three_surfaces_in_reading_order(self):
        dec = self._sections()[0]
        assert [x["key"] for x in dec["surfaces"]] == [
            "playback", "streaming", "wcdecode"]

    def test_encoding_holds_two_surfaces(self):
        enc = self._sections()[1]
        assert [x["key"] for x in enc["surfaces"]] == ["recording", "wcencode"]

    def test_surfaces_are_labelled_with_api_vocabulary(self):
        """`File` and `MSE` are MediaCapabilities' own terms (`type: 'file'`,
        `type: 'media-source'`); "url" is not an API concept."""
        dec, enc = self._sections()
        assert [x["label"] for x in dec["surfaces"]] == ["File", "MSE", "WC"]
        assert [x["label"] for x in enc["surfaces"]] == ["Rec", "WC"]
        for x in dec["surfaces"] + enc["surfaces"]:
            assert x["full"], "each short label needs a full name for the tooltip"

    def test_a_row_carries_one_cell_per_browser_per_surface(self):
        dec = self._sections()[0]
        row = [r for g in dec["groups"] for r in g["rows"]
               if r["codec"] == "AV1"][0]
        assert row["cells"]["webkit"]["playback"] == "no"
        assert row["cells"]["webkit"]["wcdecode"] == "yes"
        assert row["cells"]["firefox-playwright"]["playback"] == "yes"

    def test_a_surface_no_engine_supports_reads_as_a_dash_not_a_no(self):
        """VP8-in-MP4 File: all three say no. That is "nobody does this", which is
        not a Firefox gap, so it must not look like three failures."""
        dec = self._sections()[0]
        row = [r for g in dec["groups"] for r in g["rows"]
               if r["codec"] == "VP8"][0]
        assert row["cells"]["firefox-playwright"]["playback"] == "none"
        assert row["cells"]["firefox-playwright"]["wcdecode"] == "yes"

    def test_a_row_survives_on_the_strength_of_one_surface(self):
        """VP8 would vanish if the old per-surface rule were applied to the whole
        row -- yet WebCodecs encodes it in every engine."""
        enc = self._sections()[1]
        assert any(r["codec"] == "VP8" for g in enc["groups"] for r in g["rows"])

    def test_video_and_audio_remain_separate_groups_inside_a_section(self):
        for s in self._sections():
            for g in s["groups"]:
                assert {r["kind"] for r in g["rows"]} == {g["kind"]}

    def test_the_row_verdict_is_the_worst_across_the_section(self):
        """AV1 encoding is a gap on MediaRecorder and parity on WebCodecs; the row
        must sort and colour as the gap, or a real gap hides behind a win."""
        enc = self._sections()[1]
        row = [r for g in enc["groups"] for r in g["rows"]
               if r["codec"] == "AV1"][0]
        assert row["verdict"] == "gap"


class TestSupportIsNotDecidedByOneResolution:
    """A codec's support cell takes the best answer across resolution tiers.

    Probing a single resolution conflates "this codec is unsupported" with "this
    resolution is unsupported". Measured: this WebKit answers `no` to
    `video/mp4; codecs="av01.0.04M.08"` at 1920x1080 and `yes+hw` at 854x480, and
    says `probably` / `yes` / `yes` through canPlayType, MSE and WebCodecs. Asking
    1080p alone therefore recorded "WebKit has no AV1", when what it has is an AV1
    decoder with a ceiling -- the same shape as the codec-spelling false negative.
    """

    def _page(self):
        import pathlib
        return pathlib.Path("media-capabilities/index.html").read_text(
            encoding="utf-8")

    def test_a_low_tier_is_probed_not_just_1080p_and_4k(self):
        page = self._page()
        assert "'480p'" in page, (
            "without a tier below 1080p, a decoder with a 1080p ceiling reads as "
            "no support at all"
        )

    def test_the_decode_surfaces_take_the_best_tier(self):
        page = self._page()
        assert "bestRes(t => r => decoding(t, isVideo, 'file', r))" in page

    def test_the_best_of_helper_spans_spellings_and_resolutions(self):
        """Both axes, or the fix only half applies."""
        page = self._page()
        i = page.index("const bestRes")
        body = page[i:i + 400]
        assert "for (const t of types)" in body
        assert "for (const res of RESOLUTIONS)" in body

    def test_the_4k_column_still_asks_4k_specifically(self):
        """`decodeFile4k` is a different question -- what the ceiling is -- so it
        must not be folded into the best-of."""
        page = self._page()
        assert "RES_BY_LABEL['4K']" in page


def _res(target, *, probed_at="2026-08-11T00:00:00Z", system="Darwin",
         machine="arm64", **kw):
    r = {
        "target": target, "label": target.title(), "browser_version": "1",
        "probedAt": probed_at,
        "platform": {"system": system, "machine": machine, "release": "25.5"},
        "combos": [combo("MP4", "AAC-LC", kind="audio", canPlayType="probably")],
        "bare": {}, "conformance": [], "apis": {},
    }
    r.update(kw)
    return r


class TestThePayloadRefusesToHideAStaleRun:
    """The matrix is only meaningful if every engine was asked at the same time,
    on the same machine. Three ways it silently was not:

      * A target whose browser is missing is skipped, and its JSON from the
        previous run stays on disk. `probed_at` took `max()` of the timestamps, so
        one month-old file hid behind two fresh ones and the page still claimed a
        current date.
      * Codec support is platform-specific -- HEVC comes from VideoToolbox on
        macOS -- so results from two operating systems do not form a matrix.
      * Nothing said how old the data was.
    """

    def test_probed_at_is_the_oldest_not_the_newest(self):
        from reviewstats.mediacaps import build_payload
        p = build_payload([
            _res("chrome", probed_at="2026-06-01T00:00:00Z"),
            _res("firefox", probed_at="2026-08-11T00:00:00Z"),
        ])
        assert p["probed_at"].startswith("2026-06-01"), (
            "the newest timestamp lets a stale engine hide behind a fresh one"
        )

    def test_a_split_run_is_flagged(self):
        from reviewstats.mediacaps import build_payload
        p = build_payload([
            _res("chrome", probed_at="2026-06-01T00:00:00Z"),
            _res("firefox", probed_at="2026-08-11T00:00:00Z"),
        ])
        assert any("not probed together" in w for w in p["warnings"]), p["warnings"]

    def test_one_run_on_one_machine_produces_no_warnings(self):
        from reviewstats.mediacaps import build_payload
        p = build_payload([_res("chrome"), _res("firefox"), _res("webkit")])
        assert p["warnings"] == []

    def test_mixed_platforms_are_flagged(self):
        from reviewstats.mediacaps import build_payload
        p = build_payload([_res("chrome", system="Linux"),
                           _res("firefox", system="Darwin")])
        assert any("platform" in w.lower() for w in p["warnings"]), p["warnings"]

    def test_the_platform_is_reported_so_the_page_can_say_it(self):
        from reviewstats.mediacaps import build_payload
        p = build_payload([_res("chrome"), _res("firefox")])
        assert p["platform"] == "Darwin arm64"

    def test_a_result_with_no_platform_is_flagged_not_assumed(self):
        """Older result files predate the field; guessing macOS would be a lie."""
        from reviewstats.mediacaps import build_payload
        r = _res("chrome")
        del r["platform"]
        p = build_payload([r])
        assert any("platform" in w.lower() for w in p["warnings"])


class TestTheProbeIsRunnableInCi:
    """The gathering process has to be reproducible by a machine, not just by me.

    Four things blocked that, all of them real: the Chrome path was macOS-only so
    a Linux runner silently skipped it; the exit code was 0 if *any* engine
    answered, so a partial run looked successful; nothing recorded the platform;
    and a skipped engine kept its previous result, letting stale answers ride under
    a fresh date.
    """

    def _runner(self):
        import pathlib
        return pathlib.Path("tools/media-caps/run_probe.py").read_text(
            encoding="utf-8")

    def test_chrome_is_looked_up_per_platform(self):
        src = self._runner()
        assert "CHROME_CANDIDATES" in src
        for osname in ("Darwin", "Linux", "Windows"):
            assert f'"{osname}"' in src, osname

    def test_chrome_path_can_be_overridden_by_env(self):
        assert 'os.environ.get("CHROME_PATH")' in self._runner()

    def test_chrome_is_required_not_optional(self):
        """Playwright's Chromium is not a substitute: it ships without H.264, AAC
        and HEVC, so probing it would describe a Chrome that does not exist."""
        assert '"required": True' in self._runner()

    def test_a_partial_run_exits_nonzero(self):
        src = self._runner()
        assert "no fresh result for" in src
        assert 'if any("error" not in s for s in summary)' not in src, (
            "the old any() rule is back: a run that lost an engine exits 0"
        )

    def test_the_platform_is_recorded_with_every_result(self):
        assert '"platform": platform_summary()' in self._runner()

    def test_a_workflow_exists_and_runs_on_macos(self):
        """It must match the committed results' platform, or check_run rejects the
        mix -- and it needs Homebrew Chrome, which Linux runners cannot give."""
        import pathlib
        wf = pathlib.Path(".github/workflows/media-caps.yml")
        assert wf.exists(), "no workflow refreshes the probe data"
        text = wf.read_text(encoding="utf-8")
        assert "runs-on: macos" in text, "must be macOS to match the results"
        assert "google-chrome" in text
        assert "playwright install firefox webkit" in text
        assert "chromium" not in text.split("# Chromium deliberately")[1][:200]

    def test_the_workflow_validates_before_committing(self):
        import pathlib
        text = pathlib.Path(".github/workflows/media-caps.yml").read_text(
            encoding="utf-8")
        assert text.index("build_matrix.py") < text.index("git commit"), (
            "results would be committed before the run is validated"
        )

    def test_the_runner_is_pinned_to_an_architecture(self):
        """`macos-latest` drifts between images and architectures, and the arch is
        load-bearing: the committed results are Darwin arm64, and if the label
        resolved to x86_64 the probe would overwrite all three files with the new
        platform. They would then agree, so `check_run` raises nothing, and the
        matrix changes meaning with no warning anywhere."""
        import pathlib
        wf = pathlib.Path(".github/workflows/media-caps.yml").read_text(
            encoding="utf-8")
        import re
        runner = re.search(r"^\s*runs-on:\s*(\S+)", wf, re.M)
        assert runner, "no runs-on directive"
        assert runner.group(1) == "macos-14", (
            f"runner is {runner.group(1)}: an unpinned or non-arm64 image can "
            "change the platform without any warning firing"
        )

    def test_only_one_probe_runs_at_a_time(self):
        """A manual dispatch during the scheduled run would have two jobs writing
        the same files and pushing the same branch."""
        import pathlib
        wf = pathlib.Path(".github/workflows/media-caps.yml").read_text(
            encoding="utf-8")
        assert "concurrency:" in wf
        assert "cancel-in-progress: false" in wf, (
            "cancelling mid-probe leaves results that mix two runs"
        )

    def test_the_push_can_survive_a_moved_branch(self):
        """The weekly refresh commits every Monday and this runs on the 1st, so a
        plain push can be rejected and lose a quarter's probe."""
        import pathlib
        wf = pathlib.Path(".github/workflows/media-caps.yml").read_text(
            encoding="utf-8")
        assert "pull --rebase" in wf
