"""Which upstream branch-head commits a Firefox branch hasn't vendored —
the logic of dom/media/webrtc/third_party_build/check_missing_branch_head_commits.py."""

import pytest

from reviewstats.libwebrtc import fix_identity, project_view, unvendored_commits

UP = "Upstream commit: https://webrtc.googlesource.com/src/+/"


def _up(sha, subject):
    return {"commit": sha, "message": f"{subject}\n\nBug: chromium:1\n"}


def _ff(message):
    return {"commit": {"message": message}}


BRANCH = [
    _up("a" * 40, "[M153] Fix A"),
    _up("b" * 40, "[M153] Fix B"),
    _up("c" * 40, "[M153] Fix C"),
    _up("d" * 40, "[M153] Fix D"),
]


class TestUnvendoredCommits:
    def test_vendored_by_upstream_footer(self):
        ff = [_ff("Bug 1 - Cherry-pick upstream libwebrtc commit aaaa\n\n" + UP + "a" * 40)]
        missing = unvendored_commits(BRANCH, ff)
        assert [m["sha"] for m in missing] == ["b" * 40, "c" * 40, "d" * 40]

    def test_vendored_by_cherry_picked_from_line(self):
        ff = [_ff("Bug 1 - backport\n\n(cherry picked from commit " + "b" * 40 + ")")]
        assert "b" * 40 not in [m["sha"] for m in unvendored_commits(BRANCH, ff)]

    def test_vendored_by_subject_without_the_milestone_prefix(self):
        """Manual backports that drop the SHA still count, matched on the
        subject with its [M153] prefix stripped."""
        branch = [_up("c" * 40, "[M153] Harden payload capacity checks")]
        ff = [_ff("Bug 1 - WebRTC backport: Harden payload capacity checks r=mjf")]
        assert unvendored_commits(branch, ff) == []

    def test_vendored_via_the_main_commit_it_was_cherry_picked_from(self):
        """A branch-head commit is usually a cherry-pick of a main commit. If
        Firefox took that original instead, the branch copy is not missing —
        a case check_missing_branch_head_commits.py itself does not handle."""
        branch = [{"commit": "f" * 40, "message":
                   "[M153] Fix F\n\n(cherry picked from commit " + "9" * 40 + ")\n"}]
        ff = [_ff("Bug 1 - Cherry-pick upstream libwebrtc commit 9999\n\n" + UP + "9" * 40)]
        assert unvendored_commits(branch, ff) == []

    def test_nothing_vendored_returns_every_commit_in_order(self):
        missing = unvendored_commits(BRANCH, [])
        assert [m["sha"] for m in missing] == ["a" * 40, "b" * 40, "c" * 40, "d" * 40]
        assert missing[0] == {"sha": "a" * 40, "subject": "[M153] Fix A",
                              "fix": "Fix A", "role": "landed"}

    def test_a_short_generic_subject_cannot_hide_a_fix(self):
        """Firefox vendoring commits embed whole upstream messages, so "Fix
        crash" would match some unrelated line and hide a missing fix."""
        branch = [_up("e" * 40, "[M153] Fix crash")]
        ff = [_ff("Bug 1 - Vendor libwebrtc from x\n\n    Fix crash in unrelated code")]
        assert len(unvendored_commits(branch, ff)) == 1

    def test_an_empty_subject_never_matches_everything(self):
        branch = [_up("e" * 40, "[M153]")]
        assert len(unvendored_commits(branch, [_ff("anything")])) == 1


ROW = {"label": "Release", "firefox": "157.0.1", "milestone": 153,
       "branch_head": "branch-heads/8010", "branched": "2026-08-17",
       "vs_chrome": "1 behind", "patches": 150, "last_change": None,
       "unvendored": {"count": 1, "commits": [{"sha": "a" * 40, "subject": "Fix A",
                                               "extra": 1}]}}


class TestIncompleteInputFails:
    """A fetch that can't show it saw everything must fall back rather than
    publish a count built from partial history."""

    def _fetch(self, **kw):
        from reviewstats.libwebrtc import _fetch_unvendored
        args = dict(ref="FIREFOX_157_0_1_RELEASE", branch_head="branch-heads/8010",
                    branched="2026-08-17", today=__import__("datetime").date(2026, 10, 5))
        args.update(kw)
        return _fetch_unvendored(**args)

    def test_a_truncated_gitiles_log_raises(self):
        import pytest
        get_text = lambda url: ")]}'\n" + '{"log": [], "next": "x"}'
        with pytest.raises(RuntimeError):
            self._fetch(github_get=lambda p: [], get_text=get_text)

    def test_hitting_the_page_cap_raises(self):
        import json
        import pytest
        log = {"log": [{"commit": "a" * 40, "message": "[M153] Fix A long enough\n"}]}
        get_text = lambda url: ")]}'\n" + json.dumps(log)
        full_page = [{"commit": {"message": "x"}}] * 100
        with pytest.raises(RuntimeError):
            self._fetch(github_get=lambda p: full_page, get_text=get_text)

    def test_no_branch_date_raises(self):
        import pytest
        with pytest.raises(RuntimeError):
            self._fetch(github_get=lambda p: [], get_text=lambda u: "{}", branched=None)

    def test_an_empty_branch_log_needs_no_firefox_history(self):
        calls = []
        got = self._fetch(github_get=lambda p: calls.append(p) or [],
                          get_text=lambda u: ")]}'\n" + '{"log": []}')
        assert got["commits"] == [] and calls == []



class TestFixIdentity:
    """One definition of "the same fix", used both for matching and for the
    page's grouping: Chrome merges one upstream fix to each branch under its
    own SHA and [Mxxx] tag, and may revert and reland it."""

    @pytest.mark.parametrize("subject,fix,role", [
        ("[M155] Keep MID in sync", "Keep MID in sync", "landed"),
        ("[M120-LTS] [Wayland] Fix crash", "[Wayland] Fix crash", "landed"),
        ('Revert "[M120] Remove raw pointers"', "Remove raw pointers", "reverted"),
        ('Revert^2 "[M120] Remove raw pointers"', "Remove raw pointers", "relanded"),
        ('Revert^3 "[M120] Remove raw pointers"', "Remove raw pointers", "reverted"),
        # The tag can sit outside the quotes too, the way Gerrit merges it.
        ('[M155] Revert "Remove raw pointers"', "Remove raw pointers", "reverted"),
        ('Reland "[M155] Remove raw pointers"', "Remove raw pointers", "relanded"),
        ("Plain subject", "Plain subject", "landed"),
    ])
    def test_cases(self, subject, fix, role):
        assert fix_identity(subject) == (fix, role)


def test_files_written_before_fix_identity_are_upgraded_on_read():
    """The page groups by `fix`; an older data file (kept when a weekly
    fetch fails) has only subjects, so the projection fills them in."""
    row = {"label": "ESR 115", "unvendored": {"as_of": "2026-10-01", "commits": [
        {"sha": "g" * 40, "subject": 'Revert^2 "[M120] Remove raw pointers"'}]}}
    commit = project_view({"rows": [row]})["rows"][0]["unvendored"]["commits"][0]
    assert (commit["fix"], commit["role"]) == ("Remove raw pointers", "relanded")
