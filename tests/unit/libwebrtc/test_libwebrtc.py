"""Pure helpers behind the WebRTC page's libwebrtc version table.

No network: every input is a literal shaped like the real payloads
(product-details, default_config_env, GitHub commit objects, Gitiles JSON,
chromiumdash schedule).
"""

from datetime import date

import pytest

from reviewstats.libwebrtc import (
    Release,
    age_label,
    build_view,
    classify_libwebrtc_change,
    last_libwebrtc_change,
    last_vendored_upstream,
    parse_config_env,
    parse_gitiles_json,
    project_view,
    supported_releases,
    update_in_progress,
)


class TestSupportedReleases:
    VERSIONS = {
        "FIREFOX_NIGHTLY": "159.0a1",
        "LATEST_FIREFOX_DEVEL_VERSION": "158.0b4",
        "LATEST_FIREFOX_VERSION": "157.0",
        "FIREFOX_ESR": "140.17.0esr",
        "FIREFOX_ESR115": "115.42.0esr",
        "FIREFOX_ESR_NEXT": "153.4.0esr",
        "FIREFOX_DEVEDITION": "158.0b4",
    }

    def test_channels_then_esrs_newest_first(self):
        assert supported_releases(self.VERSIONS) == [
            Release("Nightly", "main"),
            Release("Beta", "beta"),
            Release("Release", "release"),
            Release("ESR 153", "esr153"),
            Release("ESR 140", "esr140"),
            Release("ESR 115", "esr115"),
        ]

    def test_empty_or_duplicate_esr_entries_are_ignored(self):
        versions = {"FIREFOX_ESR": "140.17.0esr", "FIREFOX_ESR140": "140.17.0esr",
                    "FIREFOX_ESR_NEXT": ""}
        assert supported_releases(versions) == [Release("ESR 140", "esr140")]


class TestParseConfigEnv:
    def test_reads_milestone_and_branch_head(self):
        text = (
            "# MOZ_NEXT_LIBWEBRTC_MILESTONE and MOZ_NEXT_FIREFOX_REL_TARGET are\n"
            "export MOZ_NEXT_LIBWEBRTC_MILESTONE=153\n"
            'export MOZ_PRIOR_UPSTREAM_BRANCH_HEAD_NUM="7990"\n'
            'export MOZ_TARGET_UPSTREAM_BRANCH_HEAD="branch-heads/8010"\n'
        )
        assert parse_config_env(text) == (153, "branch-heads/8010")

    def test_commented_assignments_are_ignored(self):
        text = "# export MOZ_NEXT_LIBWEBRTC_MILESTONE=99\n"
        assert parse_config_env(text) == (None, None)


class TestParseGitilesJson:
    def test_strips_the_xssi_prefix(self):
        assert parse_gitiles_json(')]}\'\n{"log": []}') == {"log": []}

    def test_plain_json_still_parses(self):
        assert parse_gitiles_json('{"log": [1]}') == {"log": [1]}


def _commit(subject, body="", day="2026-09-01"):
    return {"commit": {"message": subject + ("\n\n" + body if body else ""),
                       "committer": {"date": f"{day}T10:00:00Z"}}}


UP = "Upstream commit: https://webrtc.googlesource.com/src/+/"


class TestClassifyLibwebrtcChange:
    @pytest.mark.parametrize("subject,body,kind", [
        ("Bug 1 - Vendor libwebrtc from c4f21b1f91", UP + "c" * 40, "vendor"),
        ("Bug 1 - Cherry-pick upstream libwebrtc commit bb91915655 r=x",
         UP + "b" * 40, "cherry-pick"),
        ("Bug 1 - WebRTC backport: PipeWire mmap improvements a=x", "", "backport"),
        ("Bug 1 - Declare every about:license notice in moz.build r=x", "", None),
    ])
    def test_kinds(self, subject, body, kind):
        assert classify_libwebrtc_change(_commit(subject, body)) == kind


class TestLastLibwebrtcChange:
    def test_skips_commits_that_only_touch_metadata(self):
        commits = [
            _commit("Bug 2 - Declare every about:license notice r=x", day="2026-09-23"),
            _commit("Bug 1 - Vendor libwebrtc from c2b761bb73", UP + "c" * 40,
                    day="2026-09-14"),
        ]
        assert last_libwebrtc_change(commits) == {"date": "2026-09-14", "kind": "vendor"}

    def test_none_when_nothing_qualifies(self):
        assert last_libwebrtc_change([_commit("Bug 1 - lint fix")]) is None


class TestLastVendoredUpstream:
    def test_first_upstream_footer_wins(self):
        commits = [
            _commit("Bug 3 - backport", "no footer"),
            _commit("Bug 2 - Vendor libwebrtc from aaaa", UP + "a" * 40),
            _commit("Bug 1 - Vendor libwebrtc from bbbb", UP + "b" * 40),
        ]
        assert last_vendored_upstream(commits) == "a" * 40

    def test_none_without_footers(self):
        assert last_vendored_upstream([_commit("Bug 1 - x")]) is None


class TestUpdateInProgress:
    def test_complete_when_only_branch_only_commits_remain(self):
        assert update_in_progress(remaining=3, branch_only=4) is False
        assert update_in_progress(remaining=4, branch_only=4) is False

    def test_in_progress_when_main_commits_remain(self):
        assert update_in_progress(remaining=120, branch_only=4) is True

    def test_unknown_remaining_counts_as_in_progress(self):
        """Gitiles paginates long ranges; more than a page left is in progress."""
        assert update_in_progress(remaining=None, branch_only=4) is True


class TestAgeLabel:
    @pytest.mark.parametrize("branched,label", [
        (date(2026, 9, 14), "3 wk"),
        (date(2026, 8, 17), "7 wk"),
        (date(2026, 5, 4), "5 mo"),
        (date(2023, 10, 30), "35 mo"),
    ])
    def test_weeks_then_months(self, branched, label):
        assert age_label(branched, date(2026, 10, 5)) == label


class TestBuildView:
    def _row(self, **kw):
        base = dict(label="Release", firefox="157.0.1",
                    milestone=153, branch_head="branch-heads/8010",
                    branched="2026-08-17", last_change={"date": "2026-09-01",
                                                        "kind": "cherry-pick"},
                    in_progress=False)
        base.update(kw)
        return base

    def test_relation_to_chrome_stable(self):
        rows = [self._row(label="Nightly", milestone=155),
                self._row(label="Beta", milestone=154),
                self._row(label="ESR 140", milestone=135)]
        view = build_view(rows, chrome_stable=154, today=date(2026, 10, 5))
        assert [r["vs_chrome"] for r in view["rows"]] == [
            "1 ahead", "current", "19 behind"]

    def test_age_is_computed_from_the_branch_date(self):
        view = build_view([self._row()], chrome_stable=154, today=date(2026, 10, 5))
        assert view["rows"][0]["age"] == "7 wk"
        assert view["as_of"] == "2026-10-05"

    def test_missing_branch_date_leaves_age_blank(self):
        view = build_view([self._row(branched=None)], chrome_stable=154,
                          today=date(2026, 10, 5))
        assert view["rows"][0]["age"] is None



class TestProjectView:
    """The page is versions only: missing branch-head fixes are mostly
    security fixes, and this site is public. `project_view` is the one
    whitelist, applied when the data file is written AND when it is read,
    so no extra field reaches the page by either path."""

    VIEW = {
        "chrome_stable": 154, "as_of": "2026-10-05",
        "rows": [{"label": "Release", "firefox": "157.0.1", "milestone": 153,
                  "branch_head": "branch-heads/8010", "branched": "2026-08-17",
                  "age": "7 wk", "vs_chrome": "1 behind", "in_progress": False,
                  "last_change": {"date": "2026-09-01", "kind": "cherry-pick"}}],
    }

    def test_keeps_the_known_fields(self):
        assert project_view(self.VIEW) == self.VIEW

    def test_drops_unknown_row_fields(self):
        leaky = {**self.VIEW, "rows": [{**self.VIEW["rows"][0],
                                        "missing": ["chromium:123"]}]}
        assert "missing" not in project_view(leaky)["rows"][0]

    def test_drops_unknown_last_change_fields(self):
        row = {**self.VIEW["rows"][0],
               "last_change": {"date": "2026-09-01", "kind": "cherry-pick",
                               "sha": "f" * 40, "subject": "Fix UAF"}}
        got = project_view({**self.VIEW, "rows": [row]})["rows"][0]["last_change"]
        assert got == {"date": "2026-09-01", "kind": "cherry-pick"}

    def test_drops_unknown_top_level_fields(self):
        assert "commits" not in project_view({**self.VIEW, "commits": [1]})

    def test_build_view_output_is_already_projected(self):
        row = dict(self.VIEW["rows"][0])
        for k in ("age", "vs_chrome"):
            row.pop(k)
        view = build_view([row], chrome_stable=154, today=date(2026, 10, 5))
        assert project_view(view) == view
