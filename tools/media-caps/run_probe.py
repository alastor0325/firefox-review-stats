#!/usr/bin/env python3
"""Drive the published probe page in every browser present, one JSON per target.

    .venv/bin/python tools/media-caps/run_probe.py

Why this exists: the container/codec matrix on the dashboard was written by
reading Firefox and Chromium source. That tells you what the code says, not what
a shipping browser answers, and it cannot cover WebKit without reading a third
codebase. Asking the browsers directly is more accurate and re-runnable.

Python rather than Node so it uses the repo's existing venv instead of adding a
node_modules tree to a Python project. The browser binaries are shared with any
Node install via ~/Library/Caches/ms-playwright.

**Caveat that must travel with the results:** Playwright's `webkit` is a WebKit
build, not Safari. It lacks platform codec integration that Safari gets from the
OS, so a "no" there is weaker evidence than a "no" from Chrome or Firefox.
Recorded per target as `is_proxy_for_safari` and surfaced on the page.
"""

import argparse
import json
import os
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = (HERE.parents[1] / "media-capabilities" / "index.html").as_uri()
OUT = HERE / "results"

FF_ARGS = ["--no-remote", "--new-instance"]

# Real Chrome, not Playwright's Chromium. Chromium ships without the proprietary
# codecs -- no H.264, AAC or HEVC -- so probing it would report a Chrome that does
# not exist. That makes the binary a hard requirement rather than a nicety, and it
# has to be found on whatever OS this runs on: the path was macOS-only, so on a
# Linux CI runner the target was silently skipped and the matrix quietly became
# two browsers wide.
CHROME_CANDIDATES = {
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
    ],
    "Linux": [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/opt/google/chrome/chrome",
    ],
    "Windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
}


def find_chrome() -> str | None:
    """Real Chrome's path, or None. `CHROME_PATH` overrides the search."""
    override = os.environ.get("CHROME_PATH")
    if override:
        return override if Path(override).exists() else None
    for cand in CHROME_CANDIDATES.get(platform.system(), []):
        if Path(cand).exists():
            return cand
    return None


def platform_summary() -> dict:
    """Recorded with every result: the answers are platform-specific.

    HEVC decoding on macOS comes from VideoToolbox, and a Linux Chrome build may
    ship without H.264 at all, so a matrix assembled from two operating systems is
    not a matrix. Nothing recorded this before, which made that undetectable.
    """
    return {"system": platform.system(), "release": platform.release(),
            "machine": platform.machine()}

# Stock Firefox cannot be driven: Playwright launches with `-juggler-pipe`, which
# only its own patched Gecko understands -- a stock binary sees the flag, prints
# nothing useful and exits 0. So Firefox is probed with Playwright's bundled
# build (path ends in Nightly.app), which IS a real Gecko but not a shipping
# configuration. Codec support is exactly where build flags differ, so the
# Firefox column is marked `is_nonshipping_build` and should be cross-checked
# against the tree rather than trusted alone.
TARGETS = [
    {"name": "firefox-playwright", "label": "Firefox (Playwright Gecko build)",
     "engine": "firefox", "path": None, "args": [],
     "nonshipping": True},
    {"name": "chrome", "label": "Chrome", "engine": "chromium",
     "path": None, "resolve": find_chrome, "required": True,
     "args": ["--no-first-run", "--no-default-browser-check"]},
    {"name": "webkit", "label": "WebKit (Playwright build, not Safari)",
     "engine": "webkit", "path": None, "args": [], "proxy_for_safari": True},
]


def probe_one(pw, target: dict) -> dict:
    engine = getattr(pw, target["engine"])
    kwargs = {"headless": True, "args": target["args"]}
    if target["path"]:
        kwargs["executable_path"] = target["path"]

    browser = engine.launch(**kwargs)
    try:
        page = browser.new_context().new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text)
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(PAGE, wait_until="domcontentloaded", timeout=60_000)
        # The page assigns __MEDIA_CAPS__ once every async probe has resolved.
        page.wait_for_function("() => typeof window.__MEDIA_CAPS__ !== 'undefined'",
                               timeout=180_000)
        data = page.evaluate("() => window.__MEDIA_CAPS__")
        version = browser.version
        return {
            "target": target["name"],
            "label": target["label"],
            "browser_version": version,
            "is_proxy_for_safari": bool(target.get("proxy_for_safari")),
            "is_nonshipping_build": bool(target.get("nonshipping")),
            "executable_path": target["path"],
            "platform": platform_summary(),
            "console_errors": errors,
            **(data or {}),
        }
    finally:
        browser.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--own-build", action="store_true",
                    help="Also probe ~/firefox/obj-*/dist/bin/firefox (debug).")
    ap.add_argument("--only", help="Probe a single target by name.")
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright

    targets = list(TARGETS)
    if args.own_build:
        found = sorted(Path.home().glob("firefox/obj-*/dist/bin/firefox"))
        if found:
            targets.insert(0, {"name": "firefox-own", "label": "Firefox own build",
                               "engine": "firefox", "path": str(found[0]),
                               "args": FF_ARGS})
    if args.only:
        targets = [t for t in targets if t["name"] == args.only]

    # Resolve binaries that are looked up rather than fixed.
    for t in targets:
        if t.get("resolve") and not t["path"]:
            t["path"] = t["resolve"]()

    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    with sync_playwright() as pw:
        for t in targets:
            if t.get("required") and not t["path"]:
                # Not a skip. A missing required browser leaves the PREVIOUS
                # run's JSON on disk, and the payload would then mix a fresh
                # date with stale answers.
                print(f"ERROR {t['label']} — not found on "
                      f"{platform.system()}; set CHROME_PATH")
                summary.append({"target": t["name"], "label": t["label"],
                                "error": "browser not found"})
                continue
            if t["path"] and not Path(t["path"]).exists():
                print(f"SKIP  {t['label']} — not installed")
                continue
            print(f"RUN   {t['label']} ...", flush=True)
            try:
                r = probe_one(pw, t)
                (OUT / f"{t['name']}.json").write_text(
                    json.dumps(r, indent=2), encoding="utf-8")
                combos = r.get("combos") or []
                playable = [c for c in combos
                            if c.get("canPlayType") in ("probably", "maybe")]
                apis = r.get("apis") or {}
                print(f"      ok — {len(combos)} combos, {len(playable)} playable, "
                      f"WebCodecs {'present' if apis.get('VideoDecoder') else 'absent'}")
                summary.append({"target": t["name"], "label": t["label"],
                                "version": r.get("browser_version"),
                                "combos": len(combos), "playable": len(playable),
                                "webcodecs": bool(apis.get("VideoDecoder"))})
            except Exception as e:  # a missing browser download is the usual case
                msg = str(e).split("\n")[0]
                print(f"      FAILED — {msg}")
                if "Executable doesn't exist" in msg:
                    print(f"      fix: .venv/bin/playwright install {t['engine']}")
                summary.append({"target": t["name"], "label": t["label"],
                                "error": msg})

    (OUT / "summary.json").write_text(
        json.dumps({"summary": summary, "platform": platform_summary()},
                   indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}/")

    # Every requested target must have answered. The old rule -- succeed if ANY
    # did -- meant a run that lost Chrome exited 0, so CI would have committed a
    # two-browser matrix with a fresh date on it.
    failed = [s for s in summary if "error" in s]
    missing = [t["name"] for t in targets
               if not any(s["target"] == t["name"] and "error" not in s
                          for s in summary)]
    if failed or missing:
        print(f"\nFAILED — {len(failed)} error(s); "
              f"no fresh result for: {', '.join(missing) or 'none'}",
              file=sys.stderr)
        print("Results on disk may now mix this run with an older one; "
              "build_matrix.py will say so.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
