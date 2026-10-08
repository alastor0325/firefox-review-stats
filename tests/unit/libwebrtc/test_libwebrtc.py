"""Pure helpers behind the WebRTC page's libwebrtc version table.

No network: every input is a literal shaped like the real payloads
(product-details, default_config_env, GitHub commit objects, Gitiles JSON,
chromiumdash schedule).
"""

from datetime import date

import pytest

from reviewstats.libwebrtc import (
    Release,
    check_channels,
    full_stable,
    is_libwebrtc_change,
    last_libwebrtc_change,
    last_vendored_upstream,
    parse_config_env,
    parse_gitiles_json,
    project_view,
    release_tag,
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
            Release("Nightly", "main", "159.0a1"),
            Release("Beta", "FIREFOX_158_0b4_RELEASE", "158.0b4"),
            Release("Release", "FIREFOX_157_0_RELEASE", "157.0"),
            Release("ESR 153", "FIREFOX_153_4_0esr_RELEASE", "153.4.0"),
            Release("ESR 140", "FIREFOX_140_17_0esr_RELEASE", "140.17.0"),
            Release("ESR 115", "FIREFOX_115_42_0esr_RELEASE", "115.42.0"),
        ]

    def test_empty_or_duplicate_esr_entries_are_ignored(self):
        versions = {"FIREFOX_ESR": "140.17.0esr", "FIREFOX_ESR140": "140.17.0esr",
                    "FIREFOX_ESR_NEXT": ""}
        assert supported_releases(versions) == [
            Release("ESR 140", "FIREFOX_140_17_0esr_RELEASE", "140.17.0")]


class TestReleaseTag:
    """A shipped build's tag, not its branch: between merge day and release
    day the release branch already carries the next version."""

    @pytest.mark.parametrize("version, tag", [
        ("157.0.1", "FIREFOX_157_0_1_RELEASE"),
        ("158.0b5", "FIREFOX_158_0b5_RELEASE"),
        ("140.17.0esr", "FIREFOX_140_17_0esr_RELEASE"),
    ])
    def test_tag_names(self, version, tag):
        assert release_tag(version) == tag


class TestCheckChannels:
    VERSIONS = {"FIREFOX_NIGHTLY": "159.0a1", "LATEST_FIREFOX_DEVEL_VERSION": "158.0b5",
                "LATEST_FIREFOX_VERSION": "157.0.1"}
    CALENDAR = {"156.0": "2026-09-15", "157.0": "2026-09-29", "157.0.1": "2026-10-06",
                "158.0": "2026-10-13"}
    TODAY = date(2026, 10, 7)

    def test_consistent_channels_pass(self):
        check_channels(self.VERSIONS, self.CALENDAR, self.TODAY)

    def test_channels_must_be_one_version_apart(self):
        versions = {**self.VERSIONS, "LATEST_FIREFOX_VERSION": "158.0"}
        with pytest.raises(ValueError, match="Nightly 159, Beta 158, Release 158"):
            check_channels(versions, self.CALENDAR, self.TODAY)

    def test_release_must_be_the_newest_one_the_calendar_has_shipped(self):
        """158 is scheduled for 10-13, so on 10-07 it has not shipped."""
        versions = {"FIREFOX_NIGHTLY": "160.0a1", "LATEST_FIREFOX_DEVEL_VERSION": "159.0b1",
                    "LATEST_FIREFOX_VERSION": "158.0"}
        with pytest.raises(ValueError, match="calendar says 157"):
            check_channels(versions, self.CALENDAR, self.TODAY)

    def test_release_day_counts_as_shipped(self):
        versions = {"FIREFOX_NIGHTLY": "160.0a1", "LATEST_FIREFOX_DEVEL_VERSION": "159.0b1",
                    "LATEST_FIREFOX_VERSION": "158.0"}
        check_channels(versions, self.CALENDAR, date(2026, 10, 13))

    def test_a_missing_channel_fails(self):
        versions = {k: v for k, v in self.VERSIONS.items() if k != "LATEST_FIREFOX_VERSION"}
        with pytest.raises(ValueError, match="LATEST_FIREFOX_VERSION"):
            check_channels(versions, self.CALENDAR, self.TODAY)


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


class TestIsLibwebrtcChange:
    @pytest.mark.parametrize("subject,body,real", [
        ("Bug 1 - Vendor libwebrtc from c4f21b1f91", UP + "c" * 40, True),
        ("Bug 1 - Cherry-pick upstream libwebrtc commit bb91915655 r=x", "", True),
        ("Bug 1 - WebRTC backport: PipeWire mmap improvements a=x", "", True),
        ("Bug 1 - Declare every about:license notice in moz.build r=x", "", False),
    ])
    def test_cases(self, subject, body, real):
        assert is_libwebrtc_change(_commit(subject, body)) is real


class TestLastLibwebrtcChange:
    def test_skips_commits_that_only_touch_metadata(self):
        commits = [
            _commit("Bug 2 - Declare every about:license notice r=x", day="2026-09-23"),
            _commit("Bug 1 - Vendor libwebrtc from c2b761bb73", UP + "c" * 40,
                    day="2026-09-14"),
        ]
        assert last_libwebrtc_change(commits) == {"date": "2026-09-14"}

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


class TestProjectView:
    """`project_view` is the one whitelist, applied when the data file is
    written AND when it is read, so no extra field reaches the page by
    either path."""

    VIEW = {
        "chrome_stable": 154, "as_of": "2026-10-05",
        "rows": [{"label": "Release", "firefox": "157.0.1", "milestone": 153,
                  "branch_head": "branch-heads/8010", "branched": "2026-08-17",
                  "vs_chrome": "1 behind", "patches": 150,
                  "last_change": {"date": "2026-09-01"},
                  "unvendored": None}],
    }

    def test_keeps_the_known_fields(self):
        assert project_view(self.VIEW) == {**self.VIEW, "plan": None,
                                           "patch_stack": None}

    def test_drops_unknown_row_fields(self):
        leaky = {**self.VIEW, "rows": [{**self.VIEW["rows"][0],
                                        "missing": ["chromium:123"]}]}
        assert "missing" not in project_view(leaky)["rows"][0]

    def test_drops_unknown_last_change_fields(self):
        row = {**self.VIEW["rows"][0],
               "last_change": {"date": "2026-09-01",
                               "sha": "f" * 40, "subject": "Fix UAF"}}
        got = project_view({**self.VIEW, "rows": [row]})["rows"][0]["last_change"]
        assert got == {"date": "2026-09-01"}

    def test_drops_unknown_top_level_fields(self):
        assert "commits" not in project_view({**self.VIEW, "commits": [1]})

    def test_unvendored_is_whitelisted_to_its_fields(self):
        row = {**self.VIEW["rows"][0], "unvendored": {
            "count": 1, "as_of": "2026-10-05", "x": 1,
            "commits": [{"sha": "a" * 40, "subject": "Fix A", "fix": "Fix A",
                         "role": "landed", "extra": 1}]}}
        assert project_view({**self.VIEW, "rows": [row]})["rows"][0]["unvendored"] == {
            "as_of": "2026-10-05", "branch_commits": None, "last_merge": None,
            "commits": [{"sha": "a" * 40, "subject": "Fix A", "fix": "Fix A",
                         "role": "landed"}]}


class TestFullStable:
    """chromiumdash's newest "Stable" release can be a milestone still in its
    early-stable rollout (M156 started 2026-10-07; full stable 2026-10-20).
    The page compares against full stable."""

    @pytest.mark.parametrize("stable_date,today,expected", [
        ("2026-10-20", date(2026, 10, 7), 155),   # still early stable
        ("2026-10-20", date(2026, 10, 20), 156),  # reached full stable
        (None, date(2026, 10, 7), 156),           # unknown: trust the feed
    ])
    def test_cases(self, stable_date, today, expected):
        assert full_stable(156, stable_date, today) == expected
