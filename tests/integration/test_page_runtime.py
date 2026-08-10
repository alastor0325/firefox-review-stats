"""Load the rendered page in a real browser and assert it actually works.

Every other test in this suite is a regex over the static HTML. That family of
test cannot see a runtime error, and `node --check` only validates syntax — so a
page whose JavaScript throws on the first line passes all of them while
rendering nothing.

That is not hypothetical. Removing `#roadmap-matrices` from the markup while
leaving the JS that wrote to it threw `Cannot set properties of null`, which
aborted the whole script: the Roadmap item tables were empty and `renderMetrics`
never ran at all. 841 static tests were green. The bug was found by looking at a
screenshot.

So these tests execute the page and assert two things a regex cannot:

  * no console errors and no uncaught exceptions
  * every container the JS is supposed to fill actually has content

Skipped when Playwright or a browser is unavailable, so it never blocks a run on
a machine without them — the static tests still cover markup and CSS.
"""

import json
import pathlib

import pytest

# Reuse the fixtures the render tests already maintain.
from tests.unit.render.test_media_health_view import _MINIMAL_DATA, _ROADMAP

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Containers the page's JS is responsible for filling. If the script dies early,
# these stay empty and the page looks like a set of blank headings.
FILLED_BY_JS = [
    "roadmap-aspects",
    "roadmap-ranked",
    "roadmap-measure",
    "roadmap-continuous",
    "pm-lede",
    "pm-cards",
    "pm-coverage",
]


def _metrics_payload():
    """A metrics payload with the same shape the fetcher produces."""
    return {
        "generated_at": "2026-08-10T00:00:00Z",
        "window_days": 30,
        "counts": {"total": 2, "compared": 1, "firefox_only": 1},
        "metrics": [],
        "groups": [],
        "summary": [],
        "coverage": {"browsers": ["firefox", "chrome"],
                     "rows": [{"suite": "vpl", "label": "First frame",
                               "measured": ["firefox", "chrome"]}]},
    }


def _metric(mid, group, title, series, **kw):
    base = {
        "id": mid, "group": group, "title": title, "unit": "ms",
        "lower_is_better": True, "platform": "macosx1470-64-shippable",
        "note": "", "series": series, "window_days": 30, "stale": False,
        "days_behind": 0, "window_end": "2026-08-10", "noisy": False,
        "axis_max": 300.0, "graph_url": "https://example.invalid/graph",
        "compared": len(series) > 1,
        "comparison": ({"ahead": True, "factor": 1.8, "versus": "chrome",
                        "rival_count": 1} if len(series) > 1
                       else {"ahead": None, "factor": None, "versus": None,
                             "rival_count": 0}),
    }
    base.update(kw)
    return base


def _s(median, n=50, cv=2.0):
    return {"n": n, "median": median, "p25": median * 0.98,
            "p75": median * 1.02, "cv": cv, "signature_id": 1}


def _full_metrics():
    """Exercises every branch the renderer has: a compared metric, a
    Firefox-only one, a stale one, and a higher-is-better one."""
    ms = [
        _metric("vpl.h264", "First frame latency", "H.264",
                {"firefox": _s(160.0), "chrome": _s(288.0)}),
        _metric("seek.cold", "Seek latency", "Decoder cold",
                {"firefox": _s(15.0, cv=22.5)}, noisy=True, axis_max=20.0),
        _metric("ve.h264", "WebCodecs encode", "H.264 realtime",
                {"firefox": _s(1.0), "chrome": _s(4.3)}, stale=True,
                days_behind=100, window_end="2026-05-01", axis_max=5.0),
        _metric("webaudio.score", "Web Audio score", "Score",
                {"firefox": _s(96.0), "chrome": _s(316.0)},
                unit="score", lower_is_better=False, axis_max=400.0,
                comparison={"ahead": False, "factor": 3.29, "versus": "chrome",
                            "rival_count": 2}),
    ]
    groups = {}
    for m in ms:
        g = groups.setdefault(m["group"], {
            "title": m["group"], "unit": m["unit"],
            "lower_is_better": m["lower_is_better"],
            "platform": m["platform"], "metrics": [], "axis_max": 0})
        g["metrics"].append(m)
        g["axis_max"] = max(g["axis_max"], m["axis_max"])
    payload = _metrics_payload()
    payload["metrics"] = ms
    payload["groups"] = list(groups.values())
    payload["summary"] = ms
    payload["counts"] = {"total": len(ms), "compared": 3, "firefox_only": 1}
    return payload


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    from reviewstats.render import render_html

    html = render_html(_MINIMAL_DATA, roadmap_data=_ROADMAP,
                       metrics_data=_full_metrics())
    path = tmp_path_factory.mktemp("page") / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def page_state(rendered):
    """Load the page once and report errors plus what got filled."""
    pytest.importorskip("playwright", reason="playwright not installed")
    from playwright.sync_api import sync_playwright

    if not pathlib.Path(CHROME).exists():
        pytest.skip("no browser available to execute the page")

    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=CHROME)
        try:
            page = browser.new_page()
            page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                    if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"uncaught: {e}"))
            page.goto(rendered.resolve().as_uri(), wait_until="load",
                      timeout=60_000)
            page.wait_for_timeout(800)
            lengths = {
                cid: page.evaluate(
                    "(id) => { const el = document.getElementById(id);"
                    " return el ? el.innerHTML.length : -1; }", cid)
                for cid in FILLED_BY_JS
            }
            views = page.evaluate(
                "() => [...document.querySelectorAll("
                "'.toggle-bar button[data-view]')].map(b => b.dataset.view)")
        finally:
            browser.close()
    return {"errors": errors, "lengths": lengths, "views": views}


class TestPageExecutes:
    def test_no_uncaught_exceptions_or_console_errors(self, page_state):
        """The regression this file exists for. One throw aborts the script and
        every container below it stays empty, while static tests stay green."""
        assert page_state["errors"] == [], (
            "page reported errors: " + "; ".join(page_state["errors"])
        )

    @pytest.mark.parametrize("container", FILLED_BY_JS)
    def test_container_is_populated(self, page_state, container):
        n = page_state["lengths"][container]
        assert n != -1, f"#{container} is missing from the markup entirely"
        assert n > 50, (
            f"#{container} has {n} chars — the JS that fills it did not run"
        )

    def test_every_view_button_is_present(self, page_state):
        assert page_state["views"] == [
            "team", "member", "queue", "recent", "health"
        ]


class TestNoOrphanedElementWrites:
    """Guards the exact shape of the bug: JS writing to an id the markup no
    longer contains. Caught statically so it fails fast, in addition to the
    browser check above."""

    def _html(self, rendered):
        return rendered.read_text(encoding="utf-8")

    def test_every_getelementbyid_target_exists_in_the_markup(self, rendered):
        import re

        html = self._html(rendered)
        # Ids the JS reaches for...
        wanted = set(re.findall(r"getElementById\(\s*'([\w-]+)'\s*\)", html))
        # ...and ids the markup actually defines.
        defined = set(re.findall(r'\bid="([\w-]+)"', html))
        missing = sorted(wanted - defined)
        assert not missing, (
            "JS writes to ids with no matching element: " + ", ".join(missing)
            + " — this throws and aborts the rest of the script"
        )

    def test_no_dynamic_container_is_left_unwritten(self, rendered):
        """The mirror case: markup declaring a container nothing ever fills.

        Matches the id as a quoted string anywhere in the script, not only inside
        a literal `getElementById('...')` — several tables are filled indirectly,
        e.g. `fill('roadmap-ranked', 'ranked')`. Pinning the narrower pattern made
        this fail on working code.
        """
        html = self._html(rendered)
        for cid in FILLED_BY_JS:
            assert f"'{cid}'" in html, (
                f"#{cid} is never referenced by any script, directly or by name"
            )
