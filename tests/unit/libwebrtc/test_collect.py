"""The fetch orchestration, driven by fake getters (no network)."""

import base64
from datetime import date

from reviewstats.libwebrtc import collect_status

UP = "Upstream commit: https://webrtc.googlesource.com/src/+/"
MAIN_LAST = "c" * 40


def _content(text):
    return {"content": base64.b64encode(text.encode()).decode()}


def _env(ms, bh):
    return (f"export MOZ_NEXT_LIBWEBRTC_MILESTONE={ms}\n"
            f'export MOZ_TARGET_UPSTREAM_BRANCH_HEAD="branch-heads/{bh}"\n')


BRANCHES = {"main": (155, 8059, "159.0a1"), "esr140": (135, 7049, "140.17.1")}


def _github(path):
    for branch, (ms, bh, ver) in BRANCHES.items():
        if path.endswith(f"default_config_env?ref={branch}"):
            return _content(_env(ms, bh))
        if path.endswith(f"version.txt?ref={branch}"):
            return _content(ver + "\n")
        if f"sha={branch}&path=third_party/libwebrtc" in path:
            return [{"commit": {"message": "Bug 1 - Vendor libwebrtc from cccc\n\n"
                                + UP + MAIN_LAST,
                                "committer": {"date": "2026-09-25T00:00:00Z"}}}]
    raise AssertionError(f"unexpected GitHub path {path}")


def _web(url, remaining=3):
    if "product-details" in url:
        return ('{"FIREFOX_NIGHTLY": "159.0a1", "FIREFOX_ESR": "140.17.0esr"}')
    if "fetch_releases" in url:
        return '[{"milestone": 154}]'
    if "fetch_milestone_schedule" in url:
        ms = url.rsplit("=", 1)[1]
        return ('{"mstones": [{"branch_point": "%s"}]}'
                % {"155": "2026-09-14T00:00:00", "135": "2025-03-03T00:00:00"}[ms])
    if "googlesource.com" in url:
        n = remaining if MAIN_LAST in url else 4
        return ")]}'\n" + '{"log": [%s]}' % ",".join(["{}"] * n)
    raise AssertionError(f"unexpected URL {url}")


def test_builds_one_row_per_supported_release():
    view = collect_status(_github, _web, today=date(2026, 10, 5))
    assert [(r["label"], r["firefox"], r["milestone"], r["branch_head"])
            for r in view["rows"]] == [
        ("Nightly", "159.0a1", 155, "branch-heads/8059"),
        ("ESR 140", "140.17.1", 135, "branch-heads/7049"),
    ]
    assert view["chrome_stable"] == 154


def test_only_nightly_is_checked_for_an_unfinished_update():
    view = collect_status(_github, _web, today=date(2026, 10, 5))
    assert [r["in_progress"] for r in view["rows"]] == [False, False]

    busy = collect_status(_github, lambda u: _web(u, remaining=200),
                          today=date(2026, 10, 5))
    assert [r["in_progress"] for r in busy["rows"]] == [True, False]


def test_known_branch_dates_skip_the_schedule_lookup():
    """A milestone's branch date never changes, so dates from last week's
    file are reused instead of re-asking chromiumdash."""
    asked = []

    def web(url):
        if "fetch_milestone_schedule" in url:
            asked.append(url.rsplit("=", 1)[1])
        return _web(url)
    view = collect_status(_github, web, today=date(2026, 10, 5),
                          known_branch_dates={135: "2025-03-03"})
    assert asked == ["155"]
    assert [r["branched"] for r in view["rows"]] == ["2026-09-14", "2025-03-03"]
