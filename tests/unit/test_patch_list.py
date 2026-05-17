"""`build_patch_list` powers the Wait Queue view.

Sort contract: longest `time_to_accept_days` first; revisions with no
accept timing fall to the bottom (sorted by `time_to_react_days` desc
within that group).
"""

from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.patch_list import build_patch_list


def _commit(d_number: str, subject: str = "Bug 1 - x. r=padenot") -> Commit:
    return Commit(
        sha="x" * 12,
        date=datetime(2026, 5, 15, tzinfo=timezone.utc),
        author="git-name",
        subject=subject,
        reviewers=[Reviewer("padenot", False)],
        differential_revision=d_number,
    )


def _raw(
    d: str,
    *,
    author: str | None = "alwu",
    accept_actor: str | None = None,
    react_actor: str | None = None,
    react_action: str | None = None,
    time_to_react_seconds: int | None = None,
    time_to_accept_seconds: int | None = None,
) -> dict:
    events: list[dict] = []
    if react_actor:
        events.append({
            "ts": "2026-05-14T00:00:00+00:00",
            "actor": react_actor,
            "action": react_action or "comment",
        })
    if accept_actor:
        events.append({
            "ts": "2026-05-15T00:00:00+00:00",
            "actor": accept_actor,
            "action": "accept",
        })
    return {
        "d_number": d,
        "author": author,
        "events": events,
        "time_to_react_seconds": time_to_react_seconds,
        "time_to_accept_seconds": time_to_accept_seconds,
    }


class TestSortOrder:
    def test_longest_accept_first(self):
        raw = {
            "D1": _raw("D1", time_to_accept_seconds=10 * 86400),
            "D2": _raw("D2", time_to_accept_seconds=2  * 86400),
            "D3": _raw("D3", time_to_accept_seconds=30 * 86400),
        }
        commits = {d: _commit(d) for d in raw}
        result = build_patch_list(raw, commits)
        assert [r["d_number"] for r in result] == ["D3", "D1", "D2"]

    def test_missing_accept_goes_last(self):
        raw = {
            "D1": _raw("D1", time_to_accept_seconds=5 * 86400),
            "D2": _raw("D2", time_to_accept_seconds=None,
                       time_to_react_seconds=20 * 86400),
            "D3": _raw("D3", time_to_accept_seconds=15 * 86400),
        }
        commits = {d: _commit(d) for d in raw}
        result = build_patch_list(raw, commits)
        # Accepted ones first, by length; non-accepted at the bottom.
        assert [r["d_number"] for r in result] == ["D3", "D1", "D2"]

    def test_missing_commit_is_skipped(self):
        """Defence-in-depth: if we somehow have a raw_data entry for
        a D-number not in the current git window, drop it."""
        raw = {
            "D1": _raw("D1", time_to_accept_seconds=10 * 86400),
            "D-stray": _raw("D-stray", time_to_accept_seconds=20 * 86400),
        }
        commits = {"D1": _commit("D1")}
        result = build_patch_list(raw, commits)
        assert [r["d_number"] for r in result] == ["D1"]


class TestRowFields:
    def test_row_carries_link_inputs(self):
        raw = {
            "D55555": _raw(
                "D55555",
                author="alwu",
                accept_actor="padenot",
                react_actor="padenot",
                react_action="accept",
                time_to_react_seconds=3600,        # 1 h
                time_to_accept_seconds=2 * 86400,  # 2 days
            )
        }
        commits = {"D55555": _commit("D55555", "Bug 99 - hello. r=padenot")}
        row = build_patch_list(raw, commits)[0]
        assert row["d_number"] == "D55555"
        assert row["url"].endswith("/D55555")
        assert row["title"] == "Bug 99 - hello. r=padenot"
        assert row["author"] == "alwu"
        assert row["accept_actor"] == "padenot"
        assert row["react_actor"] == "padenot"
        assert row["react_action"] == "accept"
        assert abs(row["time_to_react_days"] - (3600 / 86400.0)) < 1e-9
        assert row["time_to_accept_days"] == 2.0

    def test_missing_fields_become_none(self):
        raw = {"D1": _raw("D1")}
        commits = {"D1": _commit("D1")}
        row = build_patch_list(raw, commits)[0]
        assert row["accept_actor"] is None
        assert row["react_actor"] is None
        assert row["time_to_react_days"] is None
        assert row["time_to_accept_days"] is None

    def test_accept_actor_can_be_non_member(self):
        """Author should be whoever actually accepted — including
        non-members. Earlier the field was sourced from
        `first_member_accept`, so non-member accepts came back as
        None and broke alignment with `time_to_accept_days`."""
        raw = {
            "D1": {
                "d_number": "D1",
                "author": "alwu",
                "events": [
                    {"ts": "2026-05-15T00:00:00+00:00",
                     "actor": "emilio",  # non-member
                     "action": "accept"},
                ],
                "time_to_accept_seconds": 86400,
                "time_to_react_seconds": 86400,
            }
        }
        commits = {"D1": _commit("D1")}
        row = build_patch_list(raw, commits)[0]
        assert row["accept_actor"] == "emilio"
        assert row["time_to_accept_days"] == 1.0

    def test_skips_bot_actors(self):
        raw = {
            "D1": {
                "d_number": "D1",
                "author": "alwu",
                "events": [
                    {"ts": "...", "actor": "Herald",       "action": "accept"},
                    {"ts": "...", "actor": "Lando",        "action": "accept"},
                    {"ts": "...", "actor": "padenot",      "action": "accept"},
                ],
                "time_to_accept_seconds": 86400,
                "time_to_react_seconds": 86400,
            }
        }
        commits = {"D1": _commit("D1")}
        row = build_patch_list(raw, commits)[0]
        assert row["accept_actor"] == "padenot"

    def test_skips_self_accept_by_author(self):
        raw = {
            "D1": {
                "d_number": "D1",
                "author": "alwu",
                "events": [
                    {"ts": "...", "actor": "alwu",    "action": "accept"},
                    {"ts": "...", "actor": "padenot", "action": "accept"},
                ],
                "time_to_accept_seconds": 86400,
                "time_to_react_seconds": 86400,
            }
        }
        commits = {"D1": _commit("D1")}
        row = build_patch_list(raw, commits)[0]
        assert row["accept_actor"] == "padenot"
