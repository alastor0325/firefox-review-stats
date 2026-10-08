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
# ref -> (milestone, branch-head). Shipped builds are read at their tag.
REFS = {"main": (155, 8059), "FIREFOX_158_0b5_RELEASE": (154, 7990),
            "FIREFOX_157_0_1_RELEASE": (154, 7990), "FIREFOX_140_17_0esr_RELEASE": (135, 7049)}
VERSIONS = {"FIREFOX_NIGHTLY": "159.0a1", "LATEST_FIREFOX_DEVEL_VERSION": "158.0b5",
            "LATEST_FIREFOX_VERSION": "157.0.1", "FIREFOX_ESR": "140.17.0esr"}
CALENDAR = {"157.0": "2026-09-29", "157.0.1": "2026-10-06", "158.0": "2026-10-13"}
BRANCH_DATES = {"135": "2025-03-03", "154": "2026-08-31", "155": "2026-09-14", "156": "2026-09-28",
                "157": "2026-10-12", "158": "2026-10-26"}


def _content(text):
    return {"content": base64.b64encode(text.encode()).decode()}


def _http_error(url, code):
    return urllib.error.HTTPError(url, code, "x", {}, io.BytesIO(b"{}"))


class Upstream:
    """Fake GitHub + web hosts. `down` names hosts that raise; `calls`
    records every request."""

    def __init__(self, down=(), train_horizon=162, versions=VERSIONS):
        self.down, self.train_horizon, self.calls = set(down), train_horizon, []
        self.versions = versions

    def github(self, path):
        self.calls.append(path)
        if "github" in self.down:
            raise OSError("github down")
        if "moz-patch-stack" in path and "/commits?" in path and "since=" in path:
            bug = "2072400" if "since=2026-09-25" in path else "2069067"
            after = "pushafter155" if bug == "2072400" else "pushafter154"
            return [{"sha": after, "commit": {"message": f"Bug {bug} - Vendor libwebrtc from x"}},
                    {"sha": "z", "commit": {"message": f"Bug {bug} - updated libwebrtc patch stack"}}]
        if "moz-patch-stack" in path:
            if "/commits?" in path:
                # One snapshot per month: the sha names the month.
                until = path.split("until=")[1][:7]
                return [{"sha": f"snap{until}".ljust(40, "0")}]
            if "ref=" in path and ("ref=snap" in path or "ref=push" in path):
                ref = path.split("ref=")[1]
                names = [f"s{i:04d}.patch" for i in range(147)]
                if ref.startswith("snap2026-10"):
                    names.append("s0147.patch")       # October adds one patch
                if ref.startswith(("snap2026-09", "snap2026-10", "pushafter155")):
                    names.remove("s0005.patch")       # removed in the M155 push...
                if ref.startswith(("snap2026-10",)):
                    names.remove("s0009.patch")       # ...and one dropped by hand in October
                # The blob sha is the file name: unchanged files share blobs.
                return [{"name": n, "sha": n} for n in names]
            n = 98 if "ref=FIREFOX_140" in path else 147
            return [{"name": f"s{i:04d}.patch"} for i in range(n)] + [{"name": "README.md"}]
        if "/commits?sha=main&path=dom/media/webrtc/third_party_build/default_config_env" in path:
            return [{"sha": "cfg155", "parents": [{"sha": "pushbefore155"}],
                     "commit": {"message": "Bug 2072400 - updated default_config_env for v155",
                                "committer": {"date": "2026-09-25T10:00:00Z"}}},
                    {"sha": "cfg154", "parents": [{"sha": "pushbefore154"}],
                     "commit": {"message": "Bug 2069067 - updated default_config_env for v154",
                                "committer": {"date": "2026-09-14T10:00:00Z"}}},
                    {"sha": "x", "parents": [{"sha": "y"}],
                     "commit": {"message": "Bug 1 - unrelated config tweak",
                                "committer": {"date": "2026-09-01T10:00:00Z"}}}]
        for ref, (ms, bh) in REFS.items():
            if path.endswith(f"default_config_env?ref={ref}"):
                return _content(
                    f"export MOZ_NEXT_LIBWEBRTC_MILESTONE={ms}\n"
                    "export MOZ_NEXT_FIREFOX_REL_TARGET=159\n"
                    'export MOZ_FASTFORWARD_BUG="2072400"\n'
                    f'export MOZ_TARGET_UPSTREAM_BRANCH_HEAD="branch-heads/{bh}"\n')
            if f"sha={ref}&path=third_party/libwebrtc" in path:
                taken = f"{bh}0".ljust(40, "0")  # one branch-head fix vendored
                return [{"commit": {"message": "Bug 1 - Vendor libwebrtc from cccc\n\n"
                                    + UP + MAIN_LAST + "\n" + UP + taken,
                                    "committer": {"date": "2026-09-25T00:00:00Z"}}}]
        raise AssertionError(f"unexpected GitHub path {path}")

    def web(self, url):
        self.calls.append(url)
        host = url.split("/")[2]
        if any(d in host or d in url for d in self.down):
            raise OSError(f"{host} down")
        if "raw.githubusercontent.com" in url:
            name = url.rsplit("/", 1)[1]
            return f"Subject: [PATCH] Bug 7 - Patch {name}\n\nbody\n"
        if "product-details" in url:
            return json.dumps(self.versions)
        if "fetch_releases" in url:
            return '[{"milestone": 154}]'
        if "fetch_milestone_schedule" in url:
            first, n = (int(x.split("=")[1]) for x in url.split("?")[1].split("&"))
            return json.dumps({"mstones": [
                {"mstone": m, "branch_point": BRANCH_DATES[str(m)] + "T00:00:00",
                 "stable_date": BRANCH_DATES[str(m)] + "T00:00:00"}
                for m in range(first, first + n)]})
        if url.endswith("/api/firefox/releases/"):
            return json.dumps(CALENDAR)
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
        if "refs/heads/main..refs/branch-heads/" in url:
            bh = url.split("branch-heads/")[1].split("?")[0]
            return ")]}'\n" + json.dumps({"log": [
                {"commit": f"{bh}{i}".ljust(40, "0"), "message": f"[M100] Fix {bh}-{i}\n",
                 "committer": {"time": f"Thu Oct 0{i + 1} 11:04:14 2026"}}
                for i in range(4)]})
        if "googlesource.com" in url:
            return ")]}'\n" + json.dumps({"log": [{}] * 3})
        raise AssertionError(f"unexpected URL {url}")


def _collect(up, **kw):
    return collect_status(up.github, up.web, today=TODAY, **kw)


def test_builds_one_row_per_supported_release():
    view = _collect(Upstream())
    assert [(r["label"], r["firefox"], r["milestone"], r["branch_head"], r["vs_chrome"],
             r["patches"]) for r in view["rows"]] == [
        ("Nightly", "159.0a1", 155, "branch-heads/8059", "1 ahead", 147),
        ("Beta", "158.0b5", 154, "branch-heads/7990", "current", 147),
        ("Release", "157.0.1", 154, "branch-heads/7990", "current", 147),
        ("ESR 140", "140.17.0", 135, "branch-heads/7049", "19 behind", 98)]
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


def test_plan_wiring():
    plan = _collect(Upstream())["plan"]
    assert plan["as_of"] == "2026-10-05"
    first = plan["rows"][0]
    assert (first["vendoring"], first["firefox"], first["fastforward_bug"],
            first["in_progress"]) == (True, 159, 2072400, False)
    assert [r["milestone"] for r in plan["rows"]] == [155, 156, 157, 158]
    assert plan["lag"] == {"last_vendored": "2026-09-18", "upstream_head": "2026-10-05",
                           "behind": 201}


def test_the_plan_is_one_schedule_call():
    up = Upstream()
    _collect(up)
    assert [c for c in up.calls if "&n=4" in c] == [
        "https://chromiumdash.appspot.com/fetch_milestone_schedule?mstone=155&n=4"]


def test_a_train_past_the_calendar_horizon_is_blank_not_a_failure():
    """whattrainisitnow answers 400 for versions it hasn't planned yet."""
    rows = _collect(Upstream(train_horizon=160))["plan"]["rows"]
    assert rows[1]["merge_day"] == "2026-10-22"
    assert rows[2]["merge_day"] is None


def test_patch_stack_records_each_months_changes_and_updates():
    stack = _collect(Upstream())["patch_stack"]
    assert len(stack["history"]) == 12
    sep, octo = stack["history"][-2:]
    assert sep["sha"] == "snap2026-09".ljust(40, "0")
    assert sep["updates"] == [{"milestone": 154, "bug": 2069067, "date": "2026-09-14"},
                              {"milestone": 155, "bug": 2072400, "date": "2026-09-25"}]
    # September's drop happened inside the M155 push: credited to it.
    assert sep["dropped"] == [{"subject": "Bug 7 - Patch s0005.patch", "absorbed": False,
                               "update": 155}]
    # October: one added, one dropped with no update at all.
    assert octo["added"] == [{"subject": "Bug 7 - Patch s0147.patch", "absorbed": False}]
    assert octo["dropped"] == [{"subject": "Bug 7 - Patch s0009.patch", "absorbed": False,
                                "update": None}]


def test_each_patch_version_is_read_once():
    """Snapshots share most files; a blob already read isn't fetched again."""
    up = Upstream()
    _collect(up)
    raw = [c for c in up.calls if "raw.githubusercontent.com" in c]
    assert len(raw) == len({c.rsplit("/", 1)[1] for c in raw})


def test_an_unchanged_snapshot_is_not_read_again():
    previous = _collect(Upstream())
    up = Upstream()
    _collect(up, previous=previous)
    assert not any("raw.githubusercontent.com" in c for c in up.calls)


def test_a_slow_raw_host_falls_back_instead_of_blowing_the_ci_limit(monkeypatch):
    """Past its time budget the section keeps last week's copy, so the core
    file is still written inside the CI step's limit."""
    import reviewstats.libwebrtc as lw
    ticks = iter(range(0, 10_000, 100))
    monkeypatch.setattr(lw, "_now", lambda: next(ticks))
    errors = []
    view = _collect(Upstream(), previous=PREVIOUS, on_error=lambda k, e: errors.append(k))
    assert "patch_stack" in errors
    assert view["patch_stack"]["as_of"] == "2026-09-28" and view["rows"]


def test_a_warm_week_fetches_no_history():
    previous = _collect(Upstream())
    up = Upstream()
    _collect(up, previous=previous)
    assert not any("moz-patch-stack&until=2026-08" in c for c in up.calls)


PREVIOUS = {
    "rows": [], "chrome_stable": 153, "as_of": "2026-09-28",
    "plan": {"as_of": "2026-09-28", "rows": [], "lag": None},
    "patch_stack": {"as_of": "2026-09-28", "history": []},
}


def test_a_failing_optional_host_keeps_last_weeks_section_only():
    """Gitiles down must not freeze the Releases table or the patch stack."""
    errors = []
    view = _collect(Upstream(down={"googlesource"}), previous=PREVIOUS,
                    on_error=lambda key, exc: errors.append(key))
    assert {"in_progress", "plan"} <= set(errors)
    assert view["as_of"] == "2026-10-05" and len(view["rows"]) == 4
    assert view["plan"]["as_of"] == "2026-09-28"
    assert view["patch_stack"]["as_of"] == "2026-10-05"


def test_an_optional_section_with_no_previous_copy_is_none():
    view = _collect(Upstream(down={"release/schedule"}))
    assert view["plan"] is None and view["rows"]


def test_no_release_calendar_fails_the_fetch():
    """The calendar is what checks the channels, so it is part of the core."""
    with pytest.raises(OSError):
        _collect(Upstream(down={"whattrainisitnow"}))


def test_the_core_still_fails_hard():
    """No Releases table means nothing worth writing; the script keeps last
    week's whole file."""
    with pytest.raises(OSError):
        _collect(Upstream(down={"product-details"}), previous=PREVIOUS)


def test_each_release_lists_its_unvendored_branch_head_commits():
    rows = _collect(Upstream())["rows"]
    assert [(r["label"], len(r["unvendored"]["commits"])) for r in rows] == [
        ("Nightly", 3), ("Beta", 3), ("Release", 3), ("ESR 140", 3)]
    first = rows[0]["unvendored"]["commits"][0]
    assert (first["sha"], first["fix"], first["role"]) == (
        "80591".ljust(40, "0"), "Fix 8059-1", "landed")


def test_firefox_history_is_read_from_the_branch_date_on():
    up = Upstream()
    _collect(up)
    assert any("sha=FIREFOX_140_17_0esr_RELEASE&path=third_party/libwebrtc&since=2025-03-03" in c
               for c in up.calls)


def test_unvendored_falls_back_to_last_weeks_list_per_release():
    """Gitiles down: the table still refreshes, and each release keeps last
    week's list (with its own as_of) instead of losing the column."""
    previous = {"rows": [{"label": "Nightly", "milestone": 155, "branched": "2026-09-14",
                          "branch_head": "branch-heads/8059",
                          "unvendored": {"count": 2, "commits": [], "as_of": "2026-09-28"}}]}
    errors = []
    rows = _collect(Upstream(down={"googlesource"}), previous=previous,
                    on_error=lambda key, exc: errors.append(key))["rows"]
    assert "missing fixes" in errors
    assert rows[0]["unvendored"] == {"commits": [], "as_of": "2026-09-28",
                                     "branch_commits": None, "last_merge": None}
    assert rows[1]["unvendored"] is None


def test_shipped_channels_are_read_at_their_release_tag():
    """Not the branch tip: on 10-05 the release branch already holds 158,
    which ships on 10-13."""
    up = Upstream()
    _collect(up)
    assert any("default_config_env?ref=FIREFOX_157_0_1_RELEASE" in c for c in up.calls)
    assert not any(c.endswith(("ref=release", "ref=beta")) for c in up.calls)


def test_channels_that_disagree_with_the_calendar_fail_the_fetch():
    """Last week's whole file is kept rather than publishing a wrong Release."""
    versions = {**VERSIONS, "FIREFOX_NIGHTLY": "160.0a1",
                "LATEST_FIREFOX_DEVEL_VERSION": "159.0b1", "LATEST_FIREFOX_VERSION": "158.0"}
    with pytest.raises(ValueError, match="calendar says 157"):
        _collect(Upstream(versions=versions))


def test_last_weeks_list_is_not_reused_for_a_different_milestone():
    """On a merge week Release moves milestone; last week's [M153] list must
    not be shown next to M154."""
    previous = {"rows": [{"label": "Nightly", "milestone": 154, "branched": "2026-08-31",
                          "branch_head": "branch-heads/8037",
                          "unvendored": {"count": 2, "commits": [], "as_of": "2026-09-28"}}]}
    rows = _collect(Upstream(down={"googlesource"}), previous=previous)["rows"]
    assert rows[0]["unvendored"] is None


def test_fresh_lists_carry_this_weeks_date():
    assert _collect(Upstream())["rows"][0]["unvendored"]["as_of"] == "2026-10-05"


def test_a_host_that_failed_is_not_retried_for_the_rest_of_the_run():
    """A hanging Gitiles would otherwise time out once per release and push
    the CI step past its 5-minute limit, losing the whole refresh."""
    up = Upstream(down={"googlesource"})
    _collect(up)
    assert sum("googlesource" in c for c in up.calls) == 1


def test_identical_requests_are_made_once_per_run():
    """Nightly's main..branch-head log feeds both its in-progress check and
    its unvendored list."""
    up = Upstream()
    _collect(up)
    log = [c for c in up.calls if "refs/heads/main..refs/branch-heads/8059" in c]
    assert len(log) == 1


def _early_stable(up_cls):
    class Early(up_cls):
        def web(self, url):
            if "fetch_releases" in url:
                self.calls.append(url)
                return '[{"milestone": 156}]'
            return super().web(url)
    return Early


def test_chrome_stable_is_full_stable_not_early_stable(monkeypatch):
    """M156 is in the release feed but its stable date is still ahead."""
    monkeypatch.setitem(BRANCH_DATES, "156", "2026-10-20")
    assert _collect(_early_stable(Upstream)())["chrome_stable"] == 155


def test_a_failing_schedule_does_not_fail_the_table():
    """The stable-date lookup is optional: without it the release feed's
    milestone is used and the rest still refreshes."""
    errors = []
    view = _collect(_early_stable(Upstream)(down={"chromiumdash.appspot.com/fetch_milestone"}),
                    on_error=lambda key, exc: errors.append(key))
    assert view["chrome_stable"] == 156 and view["rows"]
    assert "chrome stable" in errors
