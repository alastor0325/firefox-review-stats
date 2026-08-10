#!/usr/bin/env python3
"""Run probe.html across every browser present and dump one JSON per target.

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
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = (HERE.parents[1] / "media-capabilities" / "index.html").as_uri()
OUT = HERE / "results"

FF_ARGS = ["--no-remote", "--new-instance"]

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
     "path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
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

    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    with sync_playwright() as pw:
        for t in targets:
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
        json.dumps({"summary": summary}, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}/")
    return 0 if any("error" not in s for s in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
