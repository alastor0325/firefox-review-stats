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


def _says_nothing(support: dict) -> bool:
    """True for a bare-type row where every engine answered `maybe`.

    `maybe` is the correct answer to a type with no codecs parameter -- the
    browser cannot know without codec information -- so unanimous `maybe` reduces
    to "we all recognise this container name" and takes a full row to say it. Six
    rows on the page were this: MP4 video and audio, WebM video and audio, Ogg
    audio, WAV.

    Deliberately narrower than unanimous-anything. Three identical `no`s mean no
    engine supports the container, which is worth a row, and the surviving bare
    rows carry real findings -- HLS has no codec combinations at all, so its bare
    rows are the only place its support is visible.
    """
    return set(support.values()) == {"partial"}


KIND_LABELS = {"container": "Container itself", "video": "Video codecs",
               "audio": "Audio codecs"}

# Worst first, the rule the roadmap cards and sub-cards also follow.
_VERDICT_RANK = {GAP: 0, OVERCLAIM: 1, AHEAD: 2, PARITY: 3, NONE: 4}


def group_by_kind(rows: list) -> list:
    """Split rows into container / video / audio groups, worst first.

    Two things were wrong with one flat list. Video and audio are different
    questions, and worst-first sorting interleaved them -- a container's table ran
    AC-3, ALAC, E-AC-3, xHE-AAC, MP3, Opus, AV1, AAC-LC, so finding the video
    codecs meant filtering audio out by eye.

    Rows **no engine supports** are left out. They are not a gap, not an
    overclaim, and not a win, so there is nothing to act on, and the probe
    produces many of them because it asks every codec a container could
    plausibly carry. They stay in `counts`, and the caller is given
    `hidden_none` so it can say how many it dropped -- a silently shortened
    table reads as full coverage.

    Groups are ordered by their own worst verdict, so the group holding a gap
    leads, and an emptied group is omitted rather than left as a bare heading.
    """
    groups = []
    for kind in ("container", "video", "audio"):
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
    # Container-level rows stay on top -- they explain the codec rows beneath --
    # and the rest go worst first.
    groups.sort(key=lambda g: (0 if g["kind"] == "container" else 1, g["worst"]))
    return groups


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
                if sup and not _says_nothing(sup):
                    rows.append({
                        # The MIME type IS the row's identity here. It used to
                        # be labelled "container only" with the type in the
                        # second column, which read as "Container itself:
                        # container only, container only" once the rows were
                        # grouped under a heading that already says it.
                        "kind": "container", "codec": mt,
                        "codec_string": "", "support": sup,
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
            rows.sort(key=lambda x: (0 if x["kind"] == "container" else 1,
                                     _VERDICT_RANK[x["verdict"]], x["kind"],
                                     x["codec"]))
            counts = {v: sum(1 for x in rows if x["verdict"] == v)
                      for v in (GAP, OVERCLAIM, AHEAD, PARITY, NONE)}
            # Denominator is combinations at least one engine supports: it makes
            # "0 gaps" mean something. 0/5 is verified parity; 0/0 is nobody
            # supports this, which is a different fact.
            counts["supported"] = len(rows) - counts[NONE]
            groups = group_by_kind(rows)
            surfaces[surf] = {
                "rows": rows, "counts": counts, "groups": groups,
                # Stated, not silent: how many combinations were left out because
                # no engine supports them.
                "hidden_none": len(rows) - sum(len(g["rows"]) for g in groups),
                "bare": bare[surf],
            }

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
    return {
        "probed_at": max((r.get("probedAt") or "") for r in results),
        "browsers": [{
            "target": r.get("target"), "label": r.get("label"),
            "version": r.get("browser_version"),
            "is_proxy_for_safari": bool(r.get("is_proxy_for_safari")),
            "is_nonshipping_build": bool(r.get("is_nonshipping_build")),
        } for r in results],
        "surfaces": {s: build_support_matrix(results, surface=s)
                     for s in SURFACES},
        # Container-first grouping is what the page renders; the flat
        # disagreement lists above are kept for the counts.
        "by_container": build_container_view(results),
        "conformance": build_conformance(results),
        "apis": build_api_table(results),
    }
