"""Pure helpers for the "Recent Changes" tab.

The tab answers "what shipped in this component lately?" by grouping the
recent in-scope landings into human-friendly *feature areas*. A feature
area is just the primary subdirectory a patch touched (computed upstream
by `metrics.primary_subdir`), mapped to a readable label.

Everything here is pure — it takes pre-built row dicts (subdir + display
fields) and returns grouped/sorted structures ready to inline into the
report JSON. No I/O, no network.
"""

import re
from collections import Counter
from typing import Optional

# Friendly names for the buckets `primary_subdir` produces. Single-root
# teams (e.g. playback over dom/media) bucket by immediate subdirectory,
# so the keys are leaf names ("eme"); multi-root teams (webrtc, gfx)
# bucket by the root path they touch most, so those keys are full paths.
# Anything not listed falls back to a humanized leaf — see
# `humanize_feature`.
FEATURE_LABELS: dict[str, str] = {
    # dom/media (media-playback-reviewers) — leaf buckets.
    "mediasource": "Media Source Extensions (MSE)",
    "eme": "Encrypted Media (EME / DRM)",
    "platforms": "Decoder / platform backends",
    "webaudio": "Web Audio",
    "gmp": "Gecko Media Plugins (GMP)",
    "mediacontrol": "Media Control / Session",
    "mediasession": "Media Control / Session",
    "mediacapabilities": "Media Capabilities",
    "webvtt": "WebVTT / captions",
    "autoplay": "Autoplay",
    "ipc": "Media IPC",
    "encoder": "Media encoders",
    "imagecapture": "Image Capture",
    "doctor": "Media diagnostics (doctor)",
    "hls": "HLS",
    "webcodecs": "WebCodecs",
    "webm": "WebM",
    "webspeech": "Web Speech",
    "mediaelement": "HTMLMediaElement",
    "mediasink": "Media sink",
    "fuzz": "Fuzzing",
    "gtest": "Tests (gtest)",
    "test": "Tests",
    "tests": "Tests",
    # webrtc-reviewers — root and one-level-deeper buckets (see
    # deep_feature_bucket; multi-root teams group finer than the root).
    "dom/media/webrtc": "WebRTC",
    "dom/media/webrtc/jsapi": "WebRTC web API (RTCPeerConnection)",
    "dom/media/webrtc/libwebrtcglue": "libwebrtc integration",
    "dom/media/webrtc/transport": "Connection transport (ICE / DTLS)",
    "dom/media/webrtc/sdp": "Session negotiation (SDP)",
    "dom/media/webrtc/jsep": "Negotiation engine (JSEP)",
    "dom/media/webrtc/tests": "WebRTC tests",
    "dom/media/webrtc/third_party_build": "libwebrtc build",
    "dom/media/systemservices": "Camera & audio capture",
    "dom/media/systemservices/android_video_capture": "Android camera capture",
    "dom/media/systemservices/fake_video_capture": "Test camera capture",
    # gfx-reviewers — root and one-level-deeper buckets.
    "gfx": "Graphics core",
    "gfx/wr": "WebRender (GPU compositor)",
    "gfx/webrender_bindings": "WebRender bindings",
    "gfx/wgpu_bindings": "WebGPU backend (wgpu)",
    "gfx/layers": "Compositing & layers",
    "gfx/thebes": "2D graphics (Thebes)",
    "gfx/2d": "2D graphics library (Moz2D)",
    "gfx/gl": "OpenGL / GL contexts",
    "gfx/vr": "Virtual & augmented reality",
    "gfx/config": "Graphics configuration",
    "gfx/ycbcr": "Video colour conversion (YCbCr)",
    "gfx/qcms": "Colour management (QCMS)",
    "gfx/src": "Graphics core internals",
    "gfx/tests": "Graphics tests",
    "image": "Image decoding",
    "image/decoders": "Image decoders",
    "image/encoders": "Image encoders",
    "image/test": "Image tests",
    "dom/canvas": "Canvas",
    "dom/canvas/test": "Canvas tests",
    "dom/webgpu": "WebGPU",
    "dom/webgpu/tests": "WebGPU tests",
    # Shared sentinel buckets emitted by primary_subdir / the classifier.
    "(top-level)": "General / top-level",
    "(unknown)": "Other",
}


def humanize_feature(subdir: str) -> str:
    """Map a `primary_subdir` bucket to a human-friendly feature label.

    Exact `FEATURE_LABELS` match wins; otherwise the leaf segment is
    looked up; otherwise the leaf is title-cased (splitting on `/ - _`).
    """
    if subdir in FEATURE_LABELS:
        return FEATURE_LABELS[subdir]
    leaf = subdir.rstrip("/").split("/")[-1]
    if leaf in FEATURE_LABELS:
        return FEATURE_LABELS[leaf]
    words = [w for w in re.split(r"[-_/]+", leaf) if w]
    return " ".join(w.capitalize() for w in words)


def deep_feature_bucket(files: list[str], paths: tuple[str, ...]) -> Optional[str]:
    """Bucket a commit one level *under* whichever owned root it touched
    most — the finer grouping the Recent Changes feed uses for multi-root
    teams (gfx, webrtc), where the plain root ("gfx") is too coarse to be a
    useful feature area.

    Returns e.g. "gfx/layers" or "dom/media/webrtc/transport"; the bare
    root (e.g. "gfx") for files sitting directly under it; None if no file
    lies under any owned path. Ties broken alphabetically for determinism.
    """
    prefixes = sorted(paths, key=len, reverse=True)
    counts: Counter[str] = Counter()
    for fn in files:
        for root in prefixes:
            prefix = root.rstrip("/") + "/"
            if fn.startswith(prefix):
                rest = fn[len(prefix):]
                counts[f"{root}/{rest.split('/')[0]}" if "/" in rest else root] += 1
                break
            if fn == root:
                counts[root] += 1
                break
    if not counts:
        return None
    best = max(counts.values())
    return sorted(b for b, c in counts.items() if c == best)[0]


def _patch_key(row: dict) -> str:
    """De-dup key: a Differential Revision groups a backed-out/re-landed
    patch into one item; commits without one fall back to their sha."""
    return row.get("differential_revision") or f"sha:{row['sha']}"


def group_by_feature(rows: list[dict]) -> list[dict]:
    """Group recent-change rows into feature buckets.

    `rows` each carry a `primary_subdir` plus the display fields (date,
    author, subject, sha, ...). Re-lands sharing one Differential
    Revision collapse to a single patch (keeping the most recent
    landing). Returns
    `[{feature, label, count, patches: [...]}]` sorted by patch count
    (desc) then label (asc); patches within a group are newest-first.
    """
    # De-dup first so a re-land doesn't inflate a feature's count or
    # appear twice. Keep the row with the latest date per key.
    latest: dict[str, dict] = {}
    for row in rows:
        key = _patch_key(row)
        prev = latest.get(key)
        if prev is None or row["date"] > prev["date"]:
            latest[key] = row

    buckets: dict[str, list[dict]] = {}
    for row in latest.values():
        buckets.setdefault(row["primary_subdir"], []).append(row)

    groups = []
    for feature, patches in buckets.items():
        patches.sort(key=lambda r: r["date"], reverse=True)
        groups.append(
            {
                "feature": feature,
                "label": humanize_feature(feature),
                "count": len(patches),
                "patches": patches,
            }
        )
    groups.sort(key=lambda g: (-g["count"], g["label"]))
    return groups
