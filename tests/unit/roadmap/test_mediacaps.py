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


class TestVacuousBareRowsAreDropped:
    """A bare-type row where every engine answers `maybe` is not a finding.

    `maybe` is the spec-correct answer for a type with no codecs parameter -- the
    browser genuinely cannot know -- so three identical maybes say only "this is a
    container we all recognise". Six such rows were on the page (MP4 video+audio,
    WebM video+audio, Ogg audio, WAV) taking a full row each to say nothing.

    The rule is unanimous-`maybe` specifically, not unanimous-anything: three
    identical `no`s mean nobody supports the container, which is real news, and
    the informative bare rows are load-bearing -- HLS has no codec combinations
    at all, so its bare rows are the only place its support appears.
    """

    def _view(self, ff_bare, cr_bare):
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [combo("MP4", "AAC-LC", canPlayType="probably")],
                    bare={"video/mp4": ff_bare})
        cr = result("chrome", "Cr", [combo("MP4", "AAC-LC", canPlayType="probably")],
                    bare={"video/mp4": cr_bare})
        v = build_container_view([ff, cr])
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        return mp4["surfaces"]["playback"]["rows"]

    def _bare_rows(self, rows):
        # Keyed on `kind`, not on a display label. Keying on the words
        # "container only" broke when the row started showing the MIME type,
        # which is a rename rather than a behaviour change.
        return [r for r in rows if r["kind"] == "container"]

    def test_a_unanimous_maybe_row_is_not_rendered(self):
        rows = self._view({"canPlayType": "maybe"}, {"canPlayType": "maybe"})
        assert self._bare_rows(rows) == []

    def test_a_disagreeing_bare_row_survives(self):
        """The HLS case: Firefox no, others maybe. Dropping this loses HLS."""
        rows = self._view({"canPlayType": "no"}, {"canPlayType": "maybe"})
        assert len(self._bare_rows(rows)) == 1

    def test_a_unanimous_no_row_survives(self):
        """Nobody supports the container — that is information, not noise."""
        rows = self._view({"canPlayType": "no"}, {"canPlayType": "no"})
        assert len(self._bare_rows(rows)) == 1

    def test_a_unanimous_yes_row_survives(self):
        rows = self._view({"canPlayType": "probably"}, {"canPlayType": "probably"})
        assert len(self._bare_rows(rows)) == 1

    def test_codec_rows_are_untouched_by_the_rule(self):
        """The rule is about bare types only. A real codec answering `maybe`
        everywhere would be a genuine oddity worth seeing."""
        from reviewstats.mediacaps import build_container_view
        ff = result("firefox", "FF", [combo("MP4", "AAC-LC", canPlayType="maybe")])
        cr = result("chrome", "Cr", [combo("MP4", "AAC-LC", canPlayType="maybe")])
        v = build_container_view([ff, cr])
        mp4 = [c for c in v["containers"] if c["name"] == "MP4"][0]
        codecs = [r for r in mp4["surfaces"]["playback"]["rows"]
                  if r["kind"] != "container"]
        assert len(codecs) == 1


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
                    "conformance", "apis"):
            assert key in payload, key
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
