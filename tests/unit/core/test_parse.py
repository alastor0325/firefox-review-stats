from reviewstats.parse import (
    Reviewer,
    extract_differential_revision,
    is_group_reviewer,
    parse_reviewers,
    should_skip_commit,
)


class TestIsGroupReviewer:
    def test_plain_group(self):
        assert is_group_reviewer("media-playback-reviewers") is True

    def test_rotation_group(self):
        assert is_group_reviewer("toolkit-telemetry-reviewers-rotation") is True

    def test_individual(self):
        assert is_group_reviewer("padenot") is False

    def test_individual_with_hyphen(self):
        assert is_group_reviewer("jan-erik") is False


class TestParseReviewers:
    def test_single_individual(self):
        assert parse_reviewers("Bug 123 - fix. r=padenot") == [
            Reviewer("padenot", is_group=False)
        ]

    def test_two_individuals(self):
        assert parse_reviewers("Bug 123 - fix. r=padenot,alwu") == [
            Reviewer("padenot", False),
            Reviewer("alwu", False),
        ]

    def test_group_and_individual(self):
        assert parse_reviewers("Bug 123 - fix. r=media-playback-reviewers,padenot") == [
            Reviewer("media-playback-reviewers", True),
            Reviewer("padenot", False),
        ]

    def test_group_only(self):
        assert parse_reviewers("Bug 123 - fix. r=media-playback-reviewers") == [
            Reviewer("media-playback-reviewers", True),
        ]

    def test_strips_hash_prefix(self):
        assert parse_reviewers("Bug 123 - fix. r=#linter-reviewers") == [
            Reviewer("linter-reviewers", True),
        ]

    def test_strips_trailing_period(self):
        assert parse_reviewers("Bug 123 - fix. r=padenot.") == [
            Reviewer("padenot", False),
        ]

    def test_request_review_syntax(self):
        assert parse_reviewers("Bug 123 - fix. r?padenot") == [
            Reviewer("padenot", False),
        ]

    def test_no_reviewer_line(self):
        assert parse_reviewers("Bug 123 - fix.") == []

    def test_dedups_repeats(self):
        assert parse_reviewers("Bug 123 - fix. r=padenot,padenot") == [
            Reviewer("padenot", False),
        ]


class TestShouldSkipCommit:
    def test_skip_lando_format(self):
        assert should_skip_commit("Bug 123: apply code formatting via Lando") is True

    def test_skip_merge(self):
        assert should_skip_commit("Merge autoland to mozilla-central") is True

    def test_keep_backout(self):
        # "Backed out N changesets" isn't currently filtered; pinning behavior.
        assert should_skip_commit("Backed out 2 changesets for causing X") is False

    def test_keep_normal_commit(self):
        assert (
            should_skip_commit("Bug 123 - Fix something. r=padenot") is False
        )

    def test_skip_revert(self):
        # Per spec: Revert means backing out, not a landing.
        assert (
            should_skip_commit('Revert "Bug 123 - Fix" for causing X') is True
        )

    def test_skip_revert_no_quotes(self):
        assert should_skip_commit("Revert Bug 123 - Fix") is True


class TestExtractDifferentialRevision:
    def test_found(self):
        body = (
            "Some description here.\n\n"
            "Differential Revision: https://phabricator.services.mozilla.com/D12345\n"
        )
        assert extract_differential_revision(body) == "D12345"

    def test_missing(self):
        assert extract_differential_revision("No phab link here.") is None

    def test_ignores_random_d_numbers(self):
        # Only the labeled line — bare `D12345` in prose is not a revision link.
        assert extract_differential_revision("see D12345 for details") is None
