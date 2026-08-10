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

**Grouped by container, not codec.** A container has a *measured* header — the
probe asks the bare MIME type too — whereas a codec-level header could only ever
be a derived count. Disagreements also turn out to be container-shaped in
practice: WebKit implements no Matroska at all, so 12 "differences" are one fact.
The codec framing is served by a separate derived index rather than a second
grouping.

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

# The surfaces a probe reports, in reading order. These are the MediaCapabilities
# answers, not the legacy ones: decodingInfo gives a definite boolean plus
# `smooth` and `powerEfficient`, where canPlayType gives a deliberately vague
# tri-state whose "maybe" is unreadable without explanation. The legacy fields are
# still collected and compared -- a disagreement between the two API generations
# is itself worth knowing -- but they do not drive the table.
SURFACES = ("playback", "streaming", "recording")

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
}

SURFACE_LABELS = {
    "playback": "Playback", "streaming": "Streaming", "recording": "Recording",
}

# Which API actually answered, so the page can say so rather than implying all
# three columns are equally precise.
SURFACE_SOURCE = {
    "playback": "mediaCapabilities.decodingInfo({type:'file'})",
    "streaming": "mediaCapabilities.decodingInfo({type:'media-source'})",
    "recording": "MediaRecorder.isTypeSupported "
                 "(encodingInfo throws on Chrome)",
}

def power_efficiency(value: object) -> str:
    """efficient / costly / unknown, from a flattened decodingInfo answer.

    This is `powerEfficient`, and it is NOT a hardware-decode flag, however often
    it gets read as one. Measured here, both Firefox and Chrome report it true for
    MP3, FLAC, Vorbis and AAC -- 16 and 19 audio rows respectively -- and no
    shipping browser has a hardware MP3 or FLAC decoder. The spec only asks
    whether decoding is power efficient, and cheap software decoding qualifies.

    So it is suggestive for video, where the expensive path is the hardware one,
    and close to meaningless for audio. The dashboard says which flag this is
    rather than relabelling it as hardware support, and `hw-decode-matrix` still
    needs a real answer -- this does not close it.
    """
    v = str(value or "")
    if not v.startswith("yes"):
        return "unknown"
    return "efficient" if "+hw" in v else "costly"


def smoothness(value: object) -> bool:
    return "+smooth" in str(value or "")

# Bare MIME types the probe asks about, grouped to the container they belong to,
# so a container card can show a measured header rather than a derived count.
# HLS appears here and in no codec combination -- it is container-level only, and
# saying so beats leaving it invisible.
CONTAINER_MIMES = {
    "MP4": ["video/mp4", "audio/mp4"],
    "WebM": ["video/webm", "audio/webm"],
    "Matroska": ["video/x-matroska", "audio/x-matroska"],
    "Ogg": ["video/ogg", "audio/ogg"],
    "MPEG-2 TS": ["video/mp2t"],
    "ADTS/AAC": ["audio/aac"],
    "MP3": ["audio/mpeg"],
    "FLAC": ["audio/flac"],
    "WAV": ["audio/wav"],
    "HLS": ["application/vnd.apple.mpegurl", "application/x-mpegurl"],
}

# How a row compares. The distinction drives what a reader should do about it.
GAP = "gap"              # we lack it, another engine has it -> implement
OVERCLAIM = "overclaim"  # we claim it, nobody else does -> fix conformance
AHEAD = "ahead"          # we have it, some engine does not
PARITY = "parity"        # everyone agrees, and at least one supports it
NONE = "none"            # no engine supports it


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
            # The bare container type is a first-class row, not just a header.
            # Without it, HLS -- which has no codec combinations and is supported
            # by Chrome and WebKit but not us -- came out as "no engine support",
            # and FLAC and WAV looked unsupported because only nonsense codec
            # combinations were being counted.
            rows = []
            for mt in CONTAINER_MIMES.get(name, []):
                sup = {}
                for r in usable:
                    entry = (r.get("bare") or {}).get(mt)
                    if entry is not None:
                        sup[r["target"]] = answer(entry, surf, bare=True)
                if sup:
                    rows.append({
                        "kind": "container", "codec": "container only",
                        "codec_string": mt, "support": sup,
                        "eff": {}, "smooth": {},
                        "verdict": classify(
                            sup.get(us, "unknown"),
                            [v for t, v in sup.items() if t != us]),
                    })
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
                eff, smooth = {}, {}
                for r in usable:
                    for c in r["combos"]:
                        if (c.get("container") == name and c.get("kind") == kind
                                and c.get("codec") == codec):
                            support[r["target"]] = answer(c, surf)
                            # Acceleration and smoothness come from the
                            # MediaCapabilities field specifically -- they are
                            # only reported there, so they read the raw answer
                            # rather than the possibly-fallen-back verdict.
                            raw = c.get(SURFACE_FIELDS[surf]["codec"])
                            eff[r["target"]] = power_efficiency(raw)
                            smooth[r["target"]] = smoothness(raw)
                            codec_string = c.get("codecString", "")
                rows.append({
                    "kind": kind, "codec": codec, "codec_string": codec_string,
                    "support": support,
                    "eff": eff,
                    "smooth": smooth,
                    "verdict": classify(
                        support.get(us, "unknown"),
                        [v for t, v in support.items() if t != us]),
                })
            # Container-level rows first (they explain the codec rows beneath),
            # then gaps, our conformance bugs, wins, and the rest.
            rank = {GAP: 0, OVERCLAIM: 1, AHEAD: 2, PARITY: 3, NONE: 4}
            rows.sort(key=lambda x: (0 if x["kind"] == "container" else 1,
                                     rank[x["verdict"]], x["kind"], x["codec"]))
            counts = {v: sum(1 for x in rows if x["verdict"] == v)
                      for v in (GAP, OVERCLAIM, AHEAD, PARITY, NONE)}
            # Denominator is combinations at least one engine supports: it makes
            # "0 gaps" mean something. 0/5 is verified parity; 0/0 is nobody
            # supports this, which is a different fact.
            counts["supported"] = len(rows) - counts[NONE]
            surfaces[surf] = {"rows": rows, "counts": counts,
                              "bare": bare[surf]}

        worst = (GAP if any(surfaces[s]["counts"][GAP] for s in SURFACES)
                 else OVERCLAIM if any(surfaces[s]["counts"][OVERCLAIM]
                                       for s in SURFACES)
                 else NONE if all(surfaces[s]["counts"]["supported"] == 0
                                  for s in SURFACES)
                 else PARITY)
        # A container is "probed" if it has real codec combinations; HLS has only
        # the container-level answer, and saying so beats implying it is untested.
        has_codecs = any(
            r["kind"] != "container"
            for r in surfaces[SURFACES[0]]["rows"]
        )
        containers.append({
            "name": name,
            "mimes": CONTAINER_MIMES.get(name, []),
            "surfaces": surfaces,
            "worst": worst,
            "gaps": sum(surfaces[s]["counts"][GAP] for s in SURFACES),
            "combos": len(surfaces[SURFACES[0]]["rows"]),
            "probed": has_codecs,
        })

    # Worst first; clean containers stay visible at the end.
    order = {GAP: 0, OVERCLAIM: 1, PARITY: 2, NONE: 3}
    containers.sort(key=lambda c: (order.get(c["worst"], 9), -c["gaps"],
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
