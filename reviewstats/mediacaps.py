"""Turn media-capability probe results into a cross-browser support table.

The container/codec matrix on the dashboard was originally written by reading
Firefox and Chromium source. That is what produced two wrong claims: Chromium's
`mkv_audio_codecs` lists PCM and AC-3, but both are build-flag gated and shipping
Chrome answers `no`. Reading a codec list tells you what the code mentions, not
what a shipped browser does.

So support is now measured by asking browsers directly — `tools/media-caps/`
drives a probe page across engines — and this module is the pure layer that turns
those answers into a table.

Two decisions shape the output.

**Grouped by container, then split into video and audio.** Disagreements turn out
to be container-shaped in practice: WebKit implements no Matroska at all, so 12
"differences" are one fact. Within a container, video and audio are separate
questions, so they are separate groups. The codec framing is served by a derived
index rather than a second grouping.

**A difference is not automatically a gap.** Splitting by direction matters more
than counting: of 36 playback differences, 13 are gaps (we lack it, another engine
has it), 11 are Firefox *over-claiming* (`audio/flac` answers `probably` to every
codecs parameter, including `ac-3` and `alac` -- a conformance bug of the opposite
sign, tracked separately because the fix is different), and the rest are places we
are ahead. Ranking containers by raw difference count would put Matroska first
when it is third, because most of its differences are our wins.

**A `no` is not equally strong from every engine.** Playwright's WebKit lacks the
platform codec integration Safari gets from the OS, and Playwright's Gecko is not
a shipping Firefox configuration. Both are marked so a reader weighs them
accordingly rather than treating every cell as equivalent.
"""

# canPlayType answers, ranked. "maybe" means the container is known but the codec
# parameter was not given or could not be confirmed.
_PLAYS = ("probably", "maybe")

# The surfaces a probe reports, in reading order. These are driven by the
# MediaCapabilities answers, not the legacy ones: decodingInfo gives a definite
# boolean, where canPlayType gives a deliberately vague tri-state whose "maybe" is
# unreadable without explanation. The legacy fields are still collected, and are
# still what answers a surface when the precise call refuses -- see `answer`.
SURFACES = ("playback", "streaming", "recording", "wcdecode", "wcencode")

# Which probe field answers each surface, and what to fall back to. Not one API
# everywhere, because neither covers everything:
#
#   * MediaCapabilities is precise and reports powerEfficient, but it REQUIRES a
#     codecs parameter -- it errors on a bare container type. So bare rows, which
#     are how HLS and single-codec containers are actually queried, fall back to
#     the legacy call.
#   * `encodingInfo({type:'record'})` throws on Chrome for every configuration we
#     tried, so the recording surface uses MediaRecorder.isTypeSupported. Using
#     encodingInfo there would report Chrome as supporting nothing.
SURFACE_FIELDS = {
    "playback":  {"codec": "decodeFile", "bare": "canPlayType"},
    "streaming": {"codec": "decodeMse",  "bare": "mse"},
    "recording": {"codec": "recorder",   "bare": "recorder"},
    # WebCodecs is a separate API with its own registries, and it answers a
    # different question: raw codec access with no container. It is kept apart
    # from the three above rather than folded in, because the answers genuinely
    # differ -- Firefox's VideoEncoder does VP9 and AV1 that its MediaRecorder
    # refuses, so reporting MediaRecorder alone made "we cannot record VP9" read
    # as "we cannot encode VP9". Only the first is true.
    #
    # There is no bare fallback: WebCodecs takes a codec, never a container type,
    # so a container-level question has no meaning here.
    "wcdecode":  {"codec": "wcDecode",   "bare": "wcDecode"},
    "wcencode":  {"codec": "wcEncode",   "bare": "wcEncode"},
}

SURFACE_LABELS = {
    "playback": "Playback", "streaming": "Streaming", "recording": "Recording",
    "wcdecode": "WebCodecs decode", "wcencode": "WebCodecs encode",
}

# Which API actually answered, so the page can say so rather than implying all
# three columns are equally precise.
SURFACE_SOURCE = {
    "playback": "mediaCapabilities.decodingInfo({type:'file'})",
    "streaming": "mediaCapabilities.decodingInfo({type:'media-source'})",
    "recording": "MediaRecorder.isTypeSupported "
                 "(encodingInfo throws on Chrome)",
    "wcdecode": "VideoDecoder/AudioDecoder.isConfigSupported",
    "wcencode": "VideoEncoder/AudioEncoder.isConfigSupported",
}

# `powerEfficient` and `smooth` are deliberately NOT surfaced, though the probe
# collects both. Two reasons, either sufficient:
#
#   * powerEfficient is not a hardware-decode flag. Firefox and Chrome both report
#     it for MP3, FLAC, Vorbis and AAC, and neither ships a hardware decoder for
#     any of them -- cheap software decoding satisfies the spec.
#   * Both are **per device**. The answer describes whichever machine ran the
#     probe, so putting it in a general cross-browser table invites reading
#     "Firefox has hardware AV1 decode" off one laptop's GPU.
#
# The probe page still reports them, which is where a per-device fact belongs: a
# reader who runs it locally gets an answer about their own hardware. So
# `hw-decode-matrix` still needs a real per-configuration answer -- nothing here
# closes it.

# Bare MIME types the probe asks about, grouped to the container they belong to.
# These no longer produce rows of their own -- MediaCapabilities cannot answer a
# bare type, and the group repeating them was dropped -- but they are still what
# `answer` falls back to when the precise call refuses, so the mapping stays.
CONTAINER_MIMES = {
    "MP4": ["video/mp4", "audio/mp4"],
    "WebM": ["video/webm", "audio/webm"],
    "Matroska": ["video/x-matroska", "audio/x-matroska"],
    "Ogg": ["video/ogg", "audio/ogg"],
    "MPEG-2 TS": ["video/mp2t"],
    "ADTS/AAC": ["audio/aac"],
    "MP3": ["audio/mpeg"],
    "WAV": ["audio/wav"],
    # No FLAC: a single-codec container whose one row the FLAC codec checks in
    # MP4, Matroska and Ogg already answer.
    "HLS": ["application/vnd.apple.mpegurl", "application/x-mpegurl"],
}

# How a row compares. The distinction drives what a reader should do about it.
GAP = "gap"              # we lack it, another engine has it -> implement
OVERCLAIM = "overclaim"  # we claim it, nobody else does -> fix conformance
AHEAD = "ahead"          # we have it, some engine does not
PARITY = "parity"        # everyone agrees, and at least one supports it
NONE = "none"            # no engine supports it


# Three levels of how well we cover what is achievable, plus the degenerate case
# where nothing is achievable. Reuses the roadmap's good/mixed/weak vocabulary
# rather than inventing a fourth colour scheme for the same idea.
LEVELS = ("none", "partial", "full", "empty")
LEVEL_RANK = {"none": 0, "partial": 1, "full": 2, "empty": 3}


def support_level(ours: int, universe: int) -> str:
    """How much of what any engine supports do we support.

    Replaces a behind/parity pair that behaved like a boolean: anything short of
    perfect read as "behind", so a container we cover 13 of 14 combinations in
    looked identical to one we cover none of.

    `universe` is combinations at least one engine supports, which is what makes
    the ratio meaningful -- 0 of 0 is "nobody can do this", not a failing on our
    part, so it gets its own level rather than counting as full marks.
    """
    if universe <= 0:
        return "empty"
    if ours >= universe:
        return "full"
    return "none" if ours <= 0 else "partial"


def short_name(label: str, target: str) -> str:
    """The engine's name with the build caveat stripped off.

    The probe labels its engines "Firefox (Playwright Gecko build)" and "WebKit
    (Playwright build, not Safari)", which puts the qualification inside the name,
    where it cannot be shortened away. The caveat still travels on `label` for the
    tooltip; this is what the list shows.
    """
    name = str(label or "").split("(")[0].strip()
    return name or str(target or "").split("-")[0].title()


def classify(firefox: str, others: list) -> str:
    """Which of the five states a row is in, from Firefox's point of view."""
    yes_others = [v for v in others if v in ("yes", "partial")]
    we_have = firefox in ("yes", "partial")
    if not we_have and yes_others:
        return GAP
    if we_have and not yes_others:
        # Nobody else claims it. Either we are alone in supporting it or we are
        # answering a question we should not -- the caller cannot tell from here,
        # but in practice on this data it is the latter.
        return OVERCLAIM if others else PARITY
    if we_have and len(yes_others) < len(others):
        return AHEAD
    if not we_have and not yes_others:
        return NONE
    return PARITY


def _verdict(value: object) -> str:
    """Normalise one probe answer to yes / partial / no / unknown."""
    v = str(value or "").strip()
    if v.startswith("error:") or v in ("", "absent"):
        return "unknown"
    if v == "probably" or v.startswith("yes"):
        return "yes"
    if v == "maybe":
        return "partial"
    return "no"


def _plays(value: object) -> bool:
    return str(value or "") in _PLAYS


KIND_LABELS = {"video": "Video codecs", "audio": "Audio codecs"}

# Worst first, the rule the roadmap cards and sub-cards also follow.
_VERDICT_RANK = {GAP: 0, OVERCLAIM: 1, AHEAD: 2, PARITY: 3, NONE: 4}


# The two questions a card is actually asked, and which surfaces answer each.
# Short labels because they head a nested column group; `full` is the tooltip.
#
# "File" and "MSE" are MediaCapabilities' own vocabulary (`type: 'file'` and
# `type: 'media-source'`), which is why they are not called "url" and "stream".
SECTIONS = (
    {
        "key": "decoding", "label": "Decoding",
        "surfaces": (
            ("playback", "File", "Plain <video>/<audio> playback — "
                                 "decodingInfo, type: file"),
            ("streaming", "MSE", "Adaptive streaming — decodingInfo, "
                                 "type: media-source"),
            ("wcdecode", "WC", "WebCodecs decoder — raw codec, no container"),
        ),
    },
    {
        "key": "encoding", "label": "Encoding",
        "surfaces": (
            ("recording", "Rec", "Capture to a file — "
                                  "MediaRecorder.isTypeSupported"),
            ("wcencode", "WC", "WebCodecs encoder — not MediaRecorder's "
                               "registry, often a different answer"),
        ),
    },
)


def build_sections(surfaces: dict, browsers: list) -> list:
    """Regroup the per-surface tables into Decoding and Encoding.

    Five separate tables repeated every codec five times, and answering "can we
    encode AV1 at all" meant cross-referencing two of them -- which is exactly
    the comparison that matters, since Firefox's MediaRecorder refuses VP9 and AV1
    while its WebCodecs encoder accepts both.

    So the two questions become the two sections, browser-major with the surfaces
    nested beneath each browser. A row lives or dies on the whole section rather
    than per surface: VP8 in MP4 is played by nobody, yet every engine encodes it
    through WebCodecs, so dropping it per-surface would have lost a real answer.
    Where a surface genuinely has no engine support, the cell reads `none` -- that
    is "nobody does this", which must not look like three separate failures.

    The row's verdict is the worst across the section, so a gap on one surface
    cannot hide behind parity on another.
    """
    targets = [b["target"] for b in browsers]
    out = []
    for spec in SECTIONS:
        keys = [k for k, _, _ in spec["surfaces"] if k in surfaces]
        # Every codec named by any surface in this section, and the strongest
        # (kind, codec) identity for it.
        rows_by_id, verdicts = {}, {}
        for key in keys:
            for r in surfaces[key]["rows"]:
                ident = (r["kind"], r["codec"])
                entry = rows_by_id.setdefault(ident, {
                    "kind": r["kind"], "codec": r["codec"],
                    "codec_string": r.get("codec_string", ""),
                    "cells": {t: {} for t in targets},
                })
                if not entry["codec_string"]:
                    entry["codec_string"] = r.get("codec_string", "")
                for t in targets:
                    entry["cells"][t][key] = (
                        "none" if r["verdict"] == NONE
                        else r["support"].get(t, "unknown"))
                verdicts.setdefault(ident, []).append(r["verdict"])
        rows = []
        for ident, entry in rows_by_id.items():
            seen = verdicts[ident]
            # Nothing anywhere in the section -> the row says nothing.
            if all(v == NONE for v in seen):
                continue
            entry["verdict"] = min(
                (v for v in seen if v != NONE),
                key=lambda v: _VERDICT_RANK[v], default=NONE)
            rows.append(entry)
        rows.sort(key=lambda r: (_VERDICT_RANK[r["verdict"]], r["kind"],
                                 r["codec"]))
        out.append({
            "key": spec["key"], "label": spec["label"],
            "surfaces": [{"key": k, "label": lbl, "full": full}
                         for k, lbl, full in spec["surfaces"] if k in surfaces],
            "groups": group_by_kind(rows),
        })
    return out


def group_by_kind(rows: list) -> list:
    """Split rows into video and audio groups, worst first.

    Video and audio are different questions, and worst-first sorting interleaved
    them -- a container's table ran AC-3, ALAC, E-AC-3, xHE-AAC, MP3, Opus, AV1,
    AAC-LC, so finding the video codecs meant filtering audio out by eye.

    Rows **no engine supports** are left out. They are not a gap, not an
    overclaim and not a win, so there is nothing to act on, and the probe produces
    many of them because it asks every codec a container could plausibly carry.
    They remain in `counts`.

    Group order is fixed: **video first, then audio**, never sorted by verdict.
    Ordering the groups worst-first made the sections move around between cards --
    audio led MP4 and video led WebM -- so the eye had to re-find the video block
    on every card. Worst-first still applies to the rows *inside* a group, where
    it costs nothing. An emptied group is omitted rather than left as a heading.
    """
    groups = []
    for kind in ("video", "audio"):
        shown = [r for r in rows
                 if r["kind"] == kind and r["verdict"] != NONE]
        if not shown:
            continue
        groups.append({
            "kind": kind,
            "label": KIND_LABELS.get(kind, kind.title()),
            "rows": shown,
            "worst": min(_VERDICT_RANK[r["verdict"]] for r in shown),
        })
    # No sort: the ("video", "audio") loop above already fixes the order.
    return groups



def answer(combo: dict, surface: str, *, bare: bool = False) -> str:
    """The verdict for one combo on one surface, preferring the precise API.

    Reads the field that surface is driven by, and falls back to the legacy field
    when the precise one gave no usable answer -- WebKit throws a TypeError from
    `decodingInfo` for every Matroska configuration, yet answers `canPlayType`
    for the same input with a clear "". Reporting that as unknown would hide a
    real, measured `no` behind an API quirk.

    `bare=True` reads the legacy field directly: MediaCapabilities requires a
    codecs parameter and errors on a bare container type, so there is nothing to
    prefer.
    """
    fields = SURFACE_FIELDS[surface]
    if bare:
        return _verdict(combo.get(fields["bare"]))
    verdict = _verdict(combo.get(fields["codec"]))
    if verdict == "unknown":
        fallback = _verdict(combo.get(fields["bare"]))
        if fallback != "unknown":
            return fallback
    return verdict


def build_support_matrix(results: list, *, surface: str = "playback") -> dict:
    """Cross-browser support for one surface, keeping only disagreements.

    `results` are the per-browser probe dumps. Returns browsers (Firefox first,
    since the page is about where Firefox stands), the differing rows, and counts
    so the reader knows how much was collapsed.
    """
    if surface not in SURFACES:
        raise ValueError(f"Unknown surface {surface!r}. Expected one of {SURFACES}.")

    usable = [r for r in results or [] if r.get("combos")]
    if not usable:
        return {"surface": surface, "browsers": [], "rows": [],
                "counts": {"total": 0, "differing": 0, "agreed": 0}}

    def order(r):
        # Firefox first; the question is always "where do we stand".
        return (0 if "firefox" in str(r.get("target", "")).lower() else 1,
                str(r.get("label", "")))

    usable.sort(key=order)
    browsers = [{
        "target": r.get("target", ""),
        "label": r.get("label", ""),
        "version": r.get("browser_version", ""),
        # Weaker evidence, and the page must say so rather than imply parity.
        "is_proxy_for_safari": bool(r.get("is_proxy_for_safari")),
        "is_nonshipping_build": bool(r.get("is_nonshipping_build")),
    } for r in usable]

    # Key on the combination itself so browsers line up even if their probe
    # emitted a different order.
    by_key: dict[tuple, dict] = {}
    for r in usable:
        for c in r["combos"]:
            key = (c.get("container", ""), c.get("kind", ""), c.get("codec", ""))
            row = by_key.setdefault(key, {
                "container": key[0], "kind": key[1], "codec": key[2],
                "codec_string": c.get("codecString", ""),
                "support": {},
            })
            row["support"][r["target"]] = answer(c, surface)

    rows, agreed, indeterminate = [], 0, 0
    targets = [b["target"] for b in browsers]
    for row in by_key.values():
        verdicts = [row["support"].get(t, "unknown") for t in targets]
        known = [v for v in verdicts if v != "unknown"]
        row["firefox"] = row["support"].get(targets[0], "unknown")
        if len(set(known)) > 1:
            # Engines that answered disagree: the actionable case.
            rows.append(row)
        elif len(known) < len(verdicts):
            # Someone could not answer. Not agreement -- a gap in our data.
            indeterminate += 1
        else:
            agreed += 1

    # Where Firefox is the one saying no, first: that is the actionable set.
    def rank(row):
        ff = row.get("firefox")
        others = [v for t, v in row["support"].items() if t != targets[0]]
        we_lack = ff in ("no", "unknown") and "yes" in others
        return (0 if we_lack else 1, row["container"], row["kind"], row["codec"])

    rows.sort(key=rank)
    return {
        "surface": surface,
        "browsers": browsers,
        "rows": rows,
        "counts": {
            "total": len(by_key),
            "differing": len(rows),
            "agreed": agreed,
            "indeterminate": indeterminate,
            "we_lack": sum(1 for r in rows if rank(r)[0] == 0),
        },
    }


def build_conformance(results: list) -> dict:
    """Invalid container/codec pairs every engine should reject.

    A separate check from support, because it detects the opposite kind of fault:
    an engine that ignores the codecs parameter and answers `probably` to a
    combination that cannot exist. A site feature-detecting gets a false positive.
    """
    usable = [r for r in results or [] if r.get("conformance")]
    if not usable:
        return {"browsers": [], "rows": []}
    usable.sort(key=lambda r: (
        0 if "firefox" in str(r.get("target", "")).lower() else 1, r.get("label", "")))
    types: list[tuple] = []
    for r in usable:
        for c in r["conformance"]:
            key = (c.get("type"), c.get("why"))
            if key not in types:
                types.append(key)
    rows = []
    for mime, why in types:
        answers = {}
        for r in usable:
            for c in r["conformance"]:
                if c.get("type") == mime:
                    answers[r["target"]] = _verdict(c.get("canPlayType"))
        rows.append({"type": mime, "why": why, "support": answers,
                     "wrong": [t for t, v in answers.items()
                               if v in ("yes", "partial")]})
    rows.sort(key=lambda r: (-len(r["wrong"]), r["type"]))
    return {
        "browsers": [{"target": r["target"], "label": r["label"]} for r in usable],
        "rows": rows,
        "counts": {t["target"]: sum(1 for r in rows if t["target"] in r["wrong"])
                   for t in [{"target": r["target"]} for r in usable]},
    }


def build_api_table(results: list) -> list:
    """Which media APIs each engine exposes at all.

    Cheap to collect and it answers questions the codec table cannot — whether
    MediaSource can be constructed in a worker, whether ManagedMediaSource
    exists, whether WebCodecs is present.
    """
    usable = [r for r in results or [] if r.get("apis")]
    if not usable:
        return []
    # Note: a probe with no `apis` recorded is excluded rather than rendered as
    # all-false. Absence of data is not absence of the feature.
    names: list[str] = []
    for r in usable:
        for k in r["apis"]:
            if k not in names:
                names.append(k)
    return [{
        "api": n,
        "support": {r.get("target", ""): bool(r["apis"].get(n)) for r in usable},
    } for n in names]


def build_container_view(results: list) -> dict:
    """Container-first view: one group per container, all three surfaces inside.

    Every probed container is present whether or not it has a disagreement --
    the previous disagreements-only table made WebM, MP3 and WAV vanish entirely,
    so a reader could not tell "tested and fine" from "never tested".
    """
    usable = [r for r in results or [] if r.get("combos")]
    if not usable:
        return {"browsers": [], "containers": [], "codec_gaps": {}}

    usable.sort(key=lambda r: (
        0 if "firefox" in str(r.get("target", "")).lower() else 1,
        str(r.get("label", "")),
    ))
    browsers = [{
        "target": r.get("target", ""), "label": r.get("label", ""),
        "name": short_name(r.get("label", ""), r.get("target", "")),
        "version": r.get("browser_version", ""),
        "is_proxy_for_safari": bool(r.get("is_proxy_for_safari")),
        "is_nonshipping_build": bool(r.get("is_nonshipping_build")),
    } for r in usable]
    targets = [b["target"] for b in browsers]
    us = targets[0]

    # Which containers exist at all, in the order CONTAINER_MIMES declares.
    seen = {c.get("container") for r in usable for c in r["combos"]}
    names = [n for n in CONTAINER_MIMES if n in seen or n == "HLS"]
    names += sorted(n for n in seen if n not in CONTAINER_MIMES)

    containers = []
    for name in names:
        # Measured container-level answer per surface, from the bare MIME probe.
        bare = {}
        for surf in SURFACES:
            per_browser = {}
            for r in usable:
                answers = [
                    answer((r.get("bare") or {}).get(mt, {}), surf, bare=True)
                    for mt in CONTAINER_MIMES.get(name, [])
                    if mt in (r.get("bare") or {})
                ]
                if answers:
                    per_browser[r["target"]] = (
                        "yes" if "yes" in answers
                        else ("partial" if "partial" in answers else "no"))
            bare[surf] = per_browser

        surfaces = {}
        for surf in SURFACES:
            rows = []
            keys = []
            for r in usable:
                for c in r["combos"]:
                    if c.get("container") != name:
                        continue
                    k = (c.get("kind"), c.get("codec"))
                    if k not in keys:
                        keys.append(k)
            for kind, codec in keys:
                support, codec_string = {}, ""
                for r in usable:
                    for c in r["combos"]:
                        if (c.get("container") == name and c.get("kind") == kind
                                and c.get("codec") == codec):
                            support[r["target"]] = answer(c, surf)
                            codec_string = c.get("codecString", "")
                rows.append({
                    "kind": kind, "codec": codec, "codec_string": codec_string,
                    "support": support,
                    "verdict": classify(
                        support.get(us, "unknown"),
                        [v for t, v in support.items() if t != us]),
                })
            # Container-level rows first (they explain the codec rows beneath),
            # then gaps, our conformance bugs, wins, and the rest.
            rows.sort(key=lambda x: (0 if x["kind"] == "container" else 1,
                                     _VERDICT_RANK[x["verdict"]], x["kind"],
                                     x["codec"]))
            counts = {v: sum(1 for x in rows if x["verdict"] == v)
                      for v in (GAP, OVERCLAIM, AHEAD, PARITY, NONE)}
            # Denominator is combinations at least one engine supports: it makes
            # "0 gaps" mean something. 0/5 is verified parity; 0/0 is nobody
            # supports this, which is a different fact.
            counts["supported"] = len(rows) - counts[NONE]
            # What *we* support, which is what the chip reports. The old figure
            # was the gap count, which rises as things get worse -- the wrong
            # direction for a number read at a glance beside a status badge.
            counts["ours"] = sum(
                1 for x in rows
                if x["support"].get(us) in ("yes", "partial"))
            groups = group_by_kind(rows)
            surfaces[surf] = {
                "rows": rows, "counts": counts, "groups": groups,
                # Stated, not silent: how many combinations were left out because
                # no engine supports them.
                "hidden_none": len(rows) - sum(len(g["rows"]) for g in groups),
                "bare": bare[surf],
            }

        # Aggregated across the three surfaces: the card badge answers "how well
        # do we do this container", not "which surface is worst".
        ours_total = sum(surfaces[s]["counts"]["ours"] for s in SURFACES)
        universe_total = sum(surfaces[s]["counts"]["supported"] for s in SURFACES)
        level = support_level(ours_total, universe_total)
        worst = (GAP if any(surfaces[s]["counts"][GAP] for s in SURFACES)
                 else OVERCLAIM if any(surfaces[s]["counts"][OVERCLAIM]
                                       for s in SURFACES)
                 else NONE if universe_total == 0
                 else PARITY)
        # A container is "probed" if it has real codec combinations; HLS has only
        # the container-level answer, and saying so beats implying it is untested.
        has_codecs = any(
            r["kind"] != "container"
            for r in surfaces[SURFACES[0]]["rows"]
        )
        containers.append({
            "name": name,
            "sections": build_sections(surfaces, browsers),
            "level": level,
            "ours": ours_total,
            "achievable": universe_total,
            "mimes": CONTAINER_MIMES.get(name, []),
            "surfaces": surfaces,
            "worst": worst,
            "gaps": sum(surfaces[s]["counts"][GAP] for s in SURFACES),
            "combos": len(surfaces[SURFACES[0]]["rows"]),
            "probed": has_codecs,
        })

    # Worst first; clean containers stay visible at the end.
    order = {GAP: 0, OVERCLAIM: 1, PARITY: 2, NONE: 3}
    # By level first, so the order agrees with the badges a reader scans down the
    # column; then by how much is missing, so two "partial" cards are not
    # alphabetical when one is 1/14 and the other 13/14.
    containers.sort(key=lambda c: (LEVEL_RANK.get(c["level"], 9),
                                   -(c["achievable"] - c["ours"]),
                                   c["name"]))

    # Codec index: answers the codec-shaped question ("should we ship xHE-AAC?")
    # without paying for a second full grouping.
    codec_gaps = {}
    for surf in SURFACES:
        found = {}
        for c in containers:
            for row in c["surfaces"][surf]["rows"]:
                if row["kind"] == "container":
                    continue
                if row["verdict"] == GAP:
                    found.setdefault(row["codec"], []).append(c["name"])
        codec_gaps[surf] = [
            {"codec": k, "containers": v, "count": len(v)}
            for k, v in sorted(found.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        ]

    return {"browsers": browsers, "containers": containers,
            "codec_gaps": codec_gaps, "surface_labels": SURFACE_LABELS}


# A probe run is only a matrix if every engine was asked at once, on one machine.
# Beyond this many days between the oldest and newest answer, they are separate
# runs wearing one date.
_SAME_RUN_DAYS = 2


def check_run(results: list) -> tuple[str, str, list]:
    """(oldest probe timestamp, platform label, warnings).

    Three ways a run silently is not a run, all of them observed:

      * A target whose browser is missing is *skipped*, and its JSON from the
        previous run stays on disk. `probed_at` used to take `max()` of the
        timestamps, so a month-old engine hid behind two fresh ones while the page
        showed a current date. The oldest is the honest headline.
      * Codec support is platform-specific -- HEVC comes from VideoToolbox on
        macOS, and a Linux Chrome build may ship without H.264 at all -- so
        answers from two operating systems do not form one matrix.
      * Nothing recorded the platform, so neither of the above was detectable.

    Returns warnings rather than raising: a stale matrix is still worth showing
    with a caveat, and the caller (or CI) decides how loud to be.
    """
    warnings = []
    stamps = sorted(str(r.get("probedAt") or "") for r in results if r.get("probedAt"))
    oldest = stamps[0] if stamps else ""
    if len(stamps) >= 2 and oldest[:10] and stamps[-1][:10]:
        from datetime import date
        try:
            first = date.fromisoformat(oldest[:10])
            last = date.fromisoformat(stamps[-1][:10])
            if (last - first).days > _SAME_RUN_DAYS:
                warnings.append(
                    f"engines were not probed together: {first} to {last}. "
                    "A target whose browser was missing keeps its previous "
                    "result, so re-run the probe for all of them.")
        except ValueError:
            warnings.append("a probe timestamp could not be parsed")

    plats = set()
    for r in results:
        pl = r.get("platform") or {}
        if not pl.get("system"):
            warnings.append(
                f"{r.get('target')} recorded no platform, so it cannot be "
                "checked against the others; re-run the probe")
            continue
        plats.add(f"{pl.get('system')} {pl.get('machine')}".strip())
    if len(plats) > 1:
        warnings.append(
            "results come from different platforms (" + ", ".join(sorted(plats))
            + "), which is not one matrix: codec support is platform-specific")
    label = plats.pop() if len(plats) == 1 else ", ".join(sorted(plats))
    return oldest, label, warnings


def build_payload(results: list) -> dict | None:
    """Assemble everything the dashboard reads, from raw probe results.

    Lives here rather than in `tools/media-caps/build_matrix.py` so the site
    generator can rebuild it at render time. It used to be a committed derived
    file that only that script refreshed, which meant a change to this module
    plus a site regeneration rendered the *previous* transform -- the container
    rows kept the old "container only" label with every test green, because no
    test reads on-disk JSON. The raw results are tracked, so the derived shape
    does not need to be.

    Returns None when there is nothing probed, so the caller can drop the section
    rather than render an empty one.
    """
    if not results:
        return None
    probed_at, plat, warnings = check_run(results)
    return {
        # Oldest, not newest -- see check_run.
        "probed_at": probed_at,
        "platform": plat,
        "warnings": warnings,
        "browsers": [{
            "target": r.get("target"), "label": r.get("label"),
            "name": short_name(r.get("label"), r.get("target")),
            "version": r.get("browser_version"),
            "is_proxy_for_safari": bool(r.get("is_proxy_for_safari")),
            "is_nonshipping_build": bool(r.get("is_nonshipping_build")),
        } for r in results],
        "surfaces": {s: build_support_matrix(results, surface=s)
                     for s in SURFACES},
        # Container-first grouping is what the page renders; the flat
        # disagreement lists above are kept for the counts.
        "by_container": build_container_view(results),
        # No "conformance" key: the section was removed from the dashboard, and
        # embedding data nothing renders is how it gets rendered again by
        # accident. `build_conformance` still runs -- build_matrix.py reports it
        # -- because it found a real Firefox bug: FlacDecoder::IsSupportedType
        # never reads the codecs parameter, so we alone accept three type strings
        # that cannot exist.
        "apis": build_api_table(results),
    }
