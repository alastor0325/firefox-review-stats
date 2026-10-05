"""The fetch orchestration, driven by a fake upstream (no network).

The fake answers every endpoint the fetcher uses and can be told to fail a
host, so the core/optional split is tested the way the weekly job meets it.
"""

import base64
import io
import json
import urllib.error
from datetime import date

import pytest

from reviewstats.libwebrtc import collect_status

UP = "Upstream commit: https://webrtc.googlesource.com/src/+/"
MAIN_LAST = "c" * 40
TODAY = date(2026, 10, 5)
BRANCHES = {"main": (155, 8059, "159.0a1"), "esr140": (135, 7049, "140.17.1")}
BRANCH_DATES = {"135": "2025-03-03", "155": "2026-09-14", "156": "2026-09-28",
                "157": "2026-10-12", "158": "2026-10-26"}


def _content(text):
    return {"content": base64.b64encode(text.encode()).decode()}


def _http_error(url, code):
    return urllib.error.HTTPError(url, code, "x", {}, io.BytesIO(b"{}"))


class Upstream:
    """Fake GitHub + web hosts. `down` names hosts that raise; `calls`
    records every request."""

    def __init__(self, down=(), train_horizon=162):
        self.down, self.train_horizon, self.calls = set(down), train_horizon, []

    def github(self, path):
        self.calls.append(path)
        if "github" in self.down:
            raise OSError("github down")
        if "moz-patch-stack" in path:
            if "/commits?" in path:
                return [{"sha": "d" * 40}]
            n = 98 if "ref=esr140" in path else 147
            return [{"name": f"s{i:04d}.patch"} for i in range(n)] + [{"name": "README.md"}]
        for branch, (ms, bh, ver) in BRANCHES.items():
            if path.endswith(f"default_config_env?ref={branch}"):
                return _content(
                    f"export MOZ_NEXT_LIBWEBRTC_MILESTONE={ms}\n"
                    "export MOZ_NEXT_FIREFOX_REL_TARGET=159\n"
                    'export MOZ_FASTFORWARD_BUG="2072400"\n'
                    f'export MOZ_TARGET_UPSTREAM_BRANCH_HEAD="branch-heads/{bh}"\n')
            if path.endswith(f"version.txt?ref={branch}"):
                return _content(ver + "\n")
            if f"sha={branch}&path=third_party/libwebrtc" in path:
                return [{"commit": {"message": "Bug 1 - Vendor libwebrtc from cccc\n\n"
                                    + UP + MAIN_LAST,
                                    "committer": {"date": "2026-09-25T00:00:00Z"}}}]
        raise AssertionError(f"unexpected GitHub path {path}")

    def web(self, url):
        self.calls.append(url)
        host = url.split("/")[2]
        if any(d in host for d in self.down):
            raise OSError(f"{host} down")
        if "product-details" in url:
            return '{"FIREFOX_NIGHTLY": "159.0a1", "FIREFOX_ESR": "140.17.0esr"}'
        if "fetch_releases" in url:
            return '[{"milestone": 154}]'
        if "fetch_milestone_schedule" in url:
            first, n = (int(x.split("=")[1]) for x in url.split("?")[1].split("&"))
            return json.dumps({"mstones": [
                {"mstone": m, "branch_point": BRANCH_DATES[str(m)] + "T00:00:00",
                 "stable_date": BRANCH_DATES[str(m)] + "T00:00:00"}
                for m in range(first, first + n)]})
        if "whattrainisitnow" in url:
            v = int(url.rsplit("=", 1)[1])
            if v > self.train_horizon:
                raise _http_error(url, 400)
            start = date(2026, 9, 24).toordinal() + 14 * (v - 159)
            iso = lambda o: date.fromordinal(o).isoformat()
            return json.dumps({"nightly_start": iso(start) + " 00:00:00+00:00",
                               "merge_day": iso(start + 14) + " 00:00:00+00:00"})
        if "+log/refs/heads/main?" in url:
            return ")]}'\n" + json.dumps({"log": [{
                "committer": {"time": "Mon Oct 05 15:02:17 2026"},
                "message": "x\n\nCr-Commit-Position: refs/heads/main@{#48794}"}]})
        if "/+/" in url:
            return ")]}'\n" + json.dumps({
                "committer": {"time": "Fri Sep 18 09:00:00 2026 +0000"},
                "message": "x\n\nCr-Commit-Position: refs/branch-heads/8059@{#1}\n"
                           "Cr-Branched-From: 8d2-refs/heads/main@{#48593}"})
        if "googlesource.com" in url:
            n = 3 if MAIN_LAST in url else 4
            return ")]}'\n" + json.dumps({"log": [{}] * n})
        raise AssertionError(f"unexpected URL {url}")


def _collect(up, **kw):
    return collect_status(up.github, up.web, today=TODAY, **kw)


def test_builds_one_row_per_supported_release():
    view = _collect(Upstream())
    assert [(r["label"], r["firefox"], r["milestone"], r["branch_head"], r["vs_chrome"])
            for r in view["rows"]] == [
        ("Nightly", "159.0a1", 155, "branch-heads/8059", "1 ahead"),
        ("ESR 140", "140.17.1", 135, "branch-heads/7049", "19 behind")]
    assert view["chrome_stable"] == 154


def test_github_paths_only_go_to_the_authenticated_getter():
    up = Upstream()
    _collect(up)
    assert all(c.startswith(("/repos/", "https://")) for c in up.calls)
    assert not any(c.startswith("https://api.github.com") for c in up.calls)


def test_known_branch_dates_skip_the_schedule_lookup():
    """A past milestone's branch date never changes."""
    up = Upstream()
    previous = {"rows": [{"milestone": 135, "branched": "2025-03-03"}]}
    _collect(up, previous=previous)
    assert not any("mstone=135" in c for c in up.calls)


def test_next_update_wiring():
    nxt = _collect(Upstream())["next_update"]
    assert nxt["as_of"] == "2026-10-05"
    assert (nxt["current"]["firefox"], nxt["current"]["fastforward_bug"]) == (159, 2072400)
    assert [u["milestone"] for u in nxt["upcoming"]] == [156, 157, 158]
    assert nxt["lag"] == {"last_vendored": "2026-09-18", "upstream_head": "2026-10-05",
                          "behind": 201}


def test_upcoming_milestones_are_one_schedule_call():
    up = Upstream()
    _collect(up)
    assert [c for c in up.calls if "mstone=156" in c] == [
        "https://chromiumdash.appspot.com/fetch_milestone_schedule?mstone=156&n=3"]


def test_a_train_past_the_calendar_horizon_is_blank_not_a_failure():
    """whattrainisitnow answers 400 for versions it hasn't planned yet."""
    nxt = _collect(Upstream(train_horizon=160))["next_update"]
    assert nxt["upcoming"][0]["merge_day"] == "2026-10-22"
    assert nxt["upcoming"][1]["merge_day"] is None


def test_patch_stack_uses_nightlys_live_count_for_this_month():
    up = Upstream()
    stack = _collect(up)["patch_stack"]
    assert stack["releases"] == [{"label": "Nightly", "count": 147},
                                 {"label": "ESR 140", "count": 98}]
    assert len(stack["history"]) == 12
    assert stack["history"][-1] == {"month": "2026-10", "count": 147,
                                    "sampled": "2026-10-05"}
    assert not any("until=2026-10-05" in c for c in up.calls)


def test_a_warm_week_fetches_no_history():
    previous = _collect(Upstream())
    up = Upstream()
    _collect(up, previous=previous)
    assert not any("moz-patch-stack&until=" in c for c in up.calls)


PREVIOUS = {
    "rows": [], "chrome_stable": 153, "as_of": "2026-09-28",
    "next_update": {"as_of": "2026-09-28", "current": {"milestone": 154},
                    "upcoming": [], "lag": None},
    "patch_stack": {"as_of": "2026-09-28", "releases": [], "history": []},
}


def test_a_failing_optional_host_keeps_last_weeks_section_only():
    """Gitiles down must not freeze the Releases table or the patch stack."""
    errors = []
    view = _collect(Upstream(down={"googlesource"}), previous=PREVIOUS,
                    on_error=lambda key, exc: errors.append(key))
    assert errors == ["in_progress", "next_update"]
    assert view["as_of"] == "2026-10-05" and len(view["rows"]) == 2
    assert view["rows"][0]["in_progress"] is None
    assert view["next_update"]["as_of"] == "2026-09-28"
    assert view["patch_stack"]["as_of"] == "2026-10-05"


def test_an_optional_section_with_no_previous_copy_is_none():
    view = _collect(Upstream(down={"whattrainisitnow"}))
    assert view["next_update"] is None and view["rows"]


def test_the_core_still_fails_hard():
    """No Releases table means nothing worth writing; the script keeps last
    week's whole file."""
    with pytest.raises(OSError):
        _collect(Upstream(down={"product-details"}), previous=PREVIOUS)
