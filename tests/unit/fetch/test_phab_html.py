"""Tests for the Phabricator HTML timeline parser.

Uses tests/fixtures/D299302.html — a real revision page snapshotted into
the repo so tests run offline.
"""

from datetime import datetime, timezone
from pathlib import Path

from reviewstats.phab_html import (
    Event,
    extract_author_handle,
    first_member_review_action,
    parse_timeline,
)


# tests/fixtures/ lives under the `tests/` root, two up from this
# file (tests/unit/fetch/ → tests/).
_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "D299302.html"
)


def _events():
    return parse_timeline(_FIXTURE.read_text(encoding="utf-8"))


class TestParseTimelineD299302:
    """D299302 is alwu's accepted patch. Expected timeline (from inspection):
    - alwu created           Fri May 8, 2026 7:43 AM   (local)
    - alwu added child       Fri May 8, 2026 7:44 AM
    - phab-bot published     Fri May 8, 2026 7:44 AM
    - alwu removed reviewer  Fri May 8, 2026 7:44 AM
    - alwu added reviewer    Fri May 8, 2026 6:24 PM
    - padenot accepted       Mon May 11, 2026 3:06 PM
    - padenot commented      Mon May 11, 2026 3:09 PM
    - alwu commented         Mon May 11, 2026 6:38 PM
    - alwu updated diff      Mon May 11, 2026 9:24 PM

    The print-only spans give precise UTC: 2026-05-11 15:06:17 (UTC+0)
    for the accept.
    """

    def test_first_event_is_creation_by_author(self):
        events = _events()
        assert events[0].action == "create"
        assert events[0].actor == "alwu"

    def test_accept_event_present(self):
        events = _events()
        accepts = [e for e in events if e.action == "accept"]
        assert len(accepts) == 1
        assert accepts[0].actor == "padenot"
        # UTC timestamp from the print-only span:
        assert accepts[0].timestamp == datetime(
            2026, 5, 11, 15, 6, 17, tzinfo=timezone.utc
        )

    def test_actor_handles_extracted(self):
        actors = {e.actor for e in _events()}
        assert "alwu" in actors
        assert "padenot" in actors
        assert "phab-bot" in actors

    def test_action_types_include_create_accept_comment_update(self):
        actions = {e.action for e in _events()}
        assert "create" in actions
        assert "accept" in actions
        assert "comment" in actions
        assert "update-diff" in actions
        assert "add-reviewer" in actions
        assert "remove-reviewer" in actions

    def test_phab_bot_publish_recognized(self):
        events = _events()
        publishes = [e for e in events if e.action == "publish"]
        assert len(publishes) >= 1
        assert publishes[0].actor == "phab-bot"

    def test_add_reviewer_target_extracted(self):
        events = _events()
        adds = [e for e in events if e.action == "add-reviewer"]
        # D299302 has at least two `add-reviewer` events, both targeting
        # `media-playback-reviewers` (Herald auto-add + alwu re-add).
        assert len(adds) >= 2
        for e in adds:
            assert e.target == "media-playback-reviewers", (
                f"unexpected target {e.target!r} for add-reviewer at {e.timestamp}"
            )

    def test_remove_reviewer_target_extracted(self):
        events = _events()
        removes = [e for e in events if e.action == "remove-reviewer"]
        assert len(removes) >= 1
        assert removes[0].target == "media-playback-reviewers"

    def test_extract_author_handle(self):
        html = _FIXTURE.read_text(encoding="utf-8")
        assert extract_author_handle(html) == "alwu"

    def test_non_reviewer_events_have_no_target(self):
        events = _events()
        for e in events:
            if e.action not in ("add-reviewer", "remove-reviewer"):
                assert e.target is None, (
                    f"unexpected target {e.target!r} on action {e.action}"
                )


class TestFirstMemberReviewAction:
    MEMBERS = frozenset({"padenot", "alwu", "kinetik"})

    def test_picks_first_member_comment_or_accept(self):
        events = _events()
        first = first_member_review_action(
            events,
            members=self.MEMBERS,
            author="alwu",  # alwu is the author here
        )
        # First member action excluding the author: padenot accepted.
        assert first is not None
        assert first.actor == "padenot"
        assert first.action == "accept"

    def test_skips_author_actions(self):
        # If padenot were the author, the next member's action wins.
        events = _events()
        first = first_member_review_action(
            events,
            members=self.MEMBERS,
            author="padenot",
        )
        # No other member commented before alwu (the original author).
        # Both padenot's and alwu's were filtered (author=padenot skips
        # padenot; alwu is also a member, so alwu's later comment wins).
        assert first is not None
        assert first.actor == "alwu"

    def test_skips_non_review_actions(self):
        # 'create', 'add-reviewer', 'remove-reviewer', 'update-diff',
        # 'publish' should never count as a review action.
        events = _events()
        first = first_member_review_action(
            events,
            members=self.MEMBERS,
            author="someone-else",
        )
        assert first is not None
        assert first.action in {"accept", "comment", "request-changes", "reject"}

    def test_returns_none_when_no_member_reviewed(self):
        events = _events()
        first = first_member_review_action(
            events,
            members=frozenset({"kinetik"}),  # kinetik never touched this rev
            author="someone-else",
        )
        assert first is None

    def test_bot_actor_skipped(self):
        events = _events()
        # phab-bot's "published" event should never be the result.
        first = first_member_review_action(
            events,
            members=self.MEMBERS | frozenset({"phab-bot"}),
            author="someone-else",
        )
        # Result should still be padenot's accept, not phab-bot's publish.
        assert first is not None
        assert first.actor != "phab-bot"
