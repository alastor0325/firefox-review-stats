"""What changed in the Mozilla patch stack between month-end snapshots, and
when upstream updates landed — the data behind the patch-stack chart."""

from reviewstats.libwebrtc import attribute_drops, diff_stack, parse_update_commit, patch_subject


class TestPatchSubject:
    def test_reads_a_wrapped_subject_header(self):
        text = ("From 1a2b Mon Sep 17 00:00:00 2001\n"
                "From: Someone <x@y>\n"
                "Subject: Bug 1654112 - Don't check the calling thread in\n"
                " webrtc::AudioReceiveStream::GetSources. r=ng\n"
                "\n"
                "body\n")
        assert patch_subject(text) == ("Bug 1654112 - Don't check the calling thread in "
                                       "webrtc::AudioReceiveStream::GetSources. r=ng")

    def test_drops_the_patch_tag(self):
        assert patch_subject("Subject: [PATCH] Bug 1 - Fix\n\n") == "Bug 1 - Fix"

    def test_no_subject_is_none(self):
        assert patch_subject("no headers here") is None


class TestDiffStack:
    def test_added_and_dropped_as_multisets(self):
        """Several patches can share one subject."""
        before = ["Bug 1 - A", "WebRTC backport: B", "Bug 2 - C"]
        after = ["Bug 1 - A", "Bug 3 - D", "Bug 3 - D", "Bug 3 - D"]
        added, dropped = diff_stack(before, after)
        assert added == [{"subject": "Bug 3 - D", "absorbed": False}] * 3
        assert dropped == [{"subject": "WebRTC backport: B", "absorbed": True},
                           {"subject": "Bug 2 - C", "absorbed": False}]

    def test_backport_is_recognised_inside_a_bug_title(self):
        _, dropped = diff_stack(["Bug 2054622 - WebRTC backport: PipeWire mmap improvements"], [])
        assert dropped[0]["absorbed"] is True

    def test_no_change(self):
        assert diff_stack(["a", "b"], ["b", "a"]) == ([], [])


class TestParseUpdateCommit:
    def test_reads_bug_and_milestone(self):
        assert parse_update_commit(
            "Bug 2072400 - updated default_config_env for v155") == (2072400, 155)

    def test_other_commits_are_not_updates(self):
        assert parse_update_commit("Bug 2072400 - Vendor libwebrtc from c4f21b1f91") is None


class TestAbsorbed:
    def test_cherry_picks_of_upstream_are_absorbed_too(self):
        """"Cherry-pick upstream libwebrtc commit X" is upstream code by
        definition, like a "WebRTC backport"."""
        _, dropped = diff_stack(["Bug 1985396 - Cherry-pick upstream libwebrtc commit 1a2b",
                                 "Bug 2 - cherry-pick upstream libwebrtc fix",
                                 "Bug 3 - Firefox-only tweak"], [])
        assert [d["absorbed"] for d in dropped] == [True, True, False]


class TestAttributeDrops:
    """A drop is credited to an upstream update only if that update's own
    push removed the patch; anything else is unexplained, in any month."""

    def test_drops_removed_by_a_push_name_its_update(self):
        dropped = [{"subject": "A", "absorbed": True}, {"subject": "B", "absorbed": False}]
        got = attribute_drops(dropped, [(155, ["A"])])
        assert got == [{"subject": "A", "absorbed": True, "update": 155},
                       {"subject": "B", "absorbed": False, "update": None}]

    def test_duplicate_subjects_are_credited_one_for_one(self):
        dropped = [{"subject": "A", "absorbed": False}] * 2
        got = attribute_drops(dropped, [(154, ["A"])])
        assert [d["update"] for d in got] == [154, None]

    def test_unknown_push_contents_fall_back_to_the_months_update(self):
        """If an update's push couldn't be read, don't cry backout: credit
        the month's update as before."""
        got = attribute_drops([{"subject": "A", "absorbed": False}], [(155, None)])
        assert got[0]["update"] == 155

    def test_no_update_means_every_drop_is_unexplained(self):
        got = attribute_drops([{"subject": "A", "absorbed": False}], [])
        assert got[0]["update"] is None
