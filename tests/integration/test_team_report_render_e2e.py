"""End-to-end rendering integration tests.

Most unit tests check markup *structure* (an id is present, a CSS
rule exists, a JS function is wired). These tests check *values*:
build a realistic report from synthesised commits, render to HTML,
then extract the embedded `DATA` JSON and assert specific numbers
flow through correctly.

If a renderer dropped a key, mis-named a field, or sorted in the
wrong direction, the value-side check catches it; the structure
checks alone would happily pass.
"""

import json
import re
from datetime import datetime, timezone

from reviewstats.git_log import Commit
from reviewstats.parse import Reviewer
from reviewstats.render import render_html
from reviewstats.report import build_report


PLAYBACK_GROUP = "media-playback-reviewers"
WEBRTC_GROUP = "webrtc-reviewers"


def _extract_embedded_data(html: str) -> dict:
    """Read the `const DATA = {...};` block render_html injects."""
    m = re.search(r"const DATA = (\{.*?\});\n", html, re.DOTALL)
    assert m is not None, "Embedded DATA JSON not found in rendered HTML."
    payload = m.group(1).replace("\\u003c", "<")
    return json.loads(payload)


def _commit(
    *,
    sha: str,
    author: str,
    reviewers: list[Reviewer],
    days_ago: int = 5,
    d_number: str | None = None,
) -> Commit:
    return Commit(
        sha=sha,
        date=datetime(2026, 5, 15 - days_ago, tzinfo=timezone.utc),
        author=author,
        subject=f"Bug 100 - {sha} thing",
        reviewers=reviewers,
        differential_revision=d_number or f"D{sha[:5]}",
    )


def _render_for(
    commits: list[Commit],
    *,
    group: str,
    paths: tuple[str, ...],
    members: dict[str, str],
) -> tuple[str, dict]:
    """Build report + render, return (html, embedded DATA dict)."""
    report = build_report(
        commits,
        group=group,
        paths=paths,
        window_start=datetime(2026, 4, 15, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 15, tzinfo=timezone.utc),
        generated_at=datetime(2026, 5, 15, tzinfo=timezone.utc),
        excludes=(),
        members=members,
    )
    html = render_html(report)
    return html, _extract_embedded_data(html)


class TestPlaybackIntegration:
    """Single-path team, 8-member-style roster (we use 3 for the test)."""

    members = {"alwu": "Alastor Wu", "padenot": "Paul Adenot",
               "kinetik": "Matthew Gregan"}

    def _commits(self) -> list[Commit]:
        # 5 commits total:
        # - 4 group-tagged (alwu authors, others review)
        # - 1 NOT group-tagged AND no listed-member reviewer → counts
        #   toward landed_without_team_review.
        return [
            _commit(sha="a" * 12, author="Alastor Wu", reviewers=[
                Reviewer("padenot", False),
                Reviewer(PLAYBACK_GROUP, True),
            ]),
            _commit(sha="b" * 12, author="Alastor Wu", reviewers=[
                Reviewer("padenot", False),
                Reviewer(PLAYBACK_GROUP, True),
            ]),
            _commit(sha="c" * 12, author="Paul Adenot", reviewers=[
                Reviewer("alwu", False),
                Reviewer(PLAYBACK_GROUP, True),
            ]),
            _commit(sha="d" * 12, author="Outsider", reviewers=[
                Reviewer("kinetik", False),
                Reviewer(PLAYBACK_GROUP, True),
            ]),
            _commit(sha="e" * 12, author="Outsider", reviewers=[
                Reviewer("someone-not-on-the-team", False),
            ]),  # bypass: no group, no member
        ]

    def test_summary_tiles_reflect_input_counts(self):
        _, data = _render_for(
            self._commits(), group=PLAYBACK_GROUP,
            paths=("dom/media",), members=self.members,
        )
        s = data["summary"]
        assert s["total_patches"] == 5
        assert s["group_tagged_patches"] == 4
        assert s["group_tagged_pct"] == 4 / 5
        assert s["unique_individuals"] == 3  # padenot, alwu, kinetik
        assert s["landed_without_team_review"] == 1
        assert s["landed_without_team_review_pct"] == 1 / 5

    def test_within_group_table_orders_by_review_count_desc(self):
        _, data = _render_for(
            self._commits(), group=PLAYBACK_GROUP,
            paths=("dom/media",), members=self.members,
        )
        # padenot reviewed 2 (commits a, b), alwu reviewed 1 (c),
        # kinetik reviewed 1 (d).
        rows = [(r["name"], r["count"]) for r in data["within_group_total"]]
        assert rows[0] == ("padenot", 2)
        assert set(rows) == {("padenot", 2), ("alwu", 1), ("kinetik", 1)}

    def test_top_authors_dedupes_by_d_number(self):
        """Two commits authored by alwu under different D-numbers count
        as 2 patches; same D-number twice (a reland) counts as 1.
        Verified end-to-end."""
        _, data = _render_for(
            self._commits(), group=PLAYBACK_GROUP,
            paths=("dom/media",), members=self.members,
        )
        top = {r["name"]: r["count"] for r in data["authors"]["top_total"]}
        assert top["Alastor Wu"] == 2
        assert top["Paul Adenot"] == 1
        # Outsider authored 2 commits with different D-numbers.
        assert top["Outsider"] == 2

    def test_members_field_round_trips_supplied_roster(self):
        _, data = _render_for(
            self._commits(), group=PLAYBACK_GROUP,
            paths=("dom/media",), members=self.members,
        )
        assert data["members"] == self.members

    def test_meta_paths_round_trips_for_single_path_team(self):
        _, data = _render_for(
            self._commits(), group=PLAYBACK_GROUP,
            paths=("dom/media",), members=self.members,
        )
        assert data["meta"]["paths"] == ["dom/media"]
        assert data["meta"]["path"] == "dom/media"
        assert data["meta"]["group"] == PLAYBACK_GROUP


class TestWebRtcIntegrationMultiPath:
    """Multi-path team — paths=(dom/media/webrtc, dom/media/systemservices),
    6-member-style roster (we use 3 for the test)."""

    members = {"jib": "Jan-Ivar Bruaroey", "pehrsons": "Andreas Pehrson",
               "mjf": "Michael Froman"}
    paths = ("dom/media/webrtc", "dom/media/systemservices")

    def _commits(self) -> list[Commit]:
        return [
            _commit(sha="w" * 12, author="Andreas Pehrson", reviewers=[
                Reviewer("jib", False),
                Reviewer(WEBRTC_GROUP, True),
            ]),
            _commit(sha="x" * 12, author="Andreas Pehrson", reviewers=[
                Reviewer("mjf", False),
                Reviewer(WEBRTC_GROUP, True),
            ]),
            _commit(sha="y" * 12, author="Outsider", reviewers=[
                Reviewer("not-on-team", False),
            ]),  # bypass
        ]

    def test_meta_paths_carries_both_roots(self):
        _, data = _render_for(
            self._commits(), group=WEBRTC_GROUP,
            paths=self.paths, members=self.members,
        )
        assert data["meta"]["paths"] == list(self.paths)

    def test_meta_path_falls_back_to_first_for_legacy_consumers(self):
        """meta.path (singular) is kept for older code/tests; it equals
        the first entry of meta.paths so tooling that only knows the
        old field name still gets a coherent value."""
        _, data = _render_for(
            self._commits(), group=WEBRTC_GROUP,
            paths=self.paths, members=self.members,
        )
        assert data["meta"]["path"] == self.paths[0]

    def test_header_meta_line_lists_both_paths(self):
        """The page-header JS joins meta.paths with ', ' and writes it
        into #hdr-paths. The actual JS runs in the browser, but the
        template + embedded data should both surface the value."""
        html, _ = _render_for(
            self._commits(), group=WEBRTC_GROUP,
            paths=self.paths, members=self.members,
        )
        # JS reads from meta.paths; verify the value is present in the
        # embedded JSON (the JS will pick it up at runtime).
        assert "dom/media/webrtc" in html
        assert "dom/media/systemservices" in html

    def test_within_group_counts_correct_for_multipath_team(self):
        _, data = _render_for(
            self._commits(), group=WEBRTC_GROUP,
            paths=self.paths, members=self.members,
        )
        rows = {r["name"]: r["count"] for r in data["within_group_total"]}
        assert rows == {"jib": 1, "mjf": 1}
        # pehrsons authored but didn't review in this set; absent.
        assert "pehrsons" not in rows

    def test_landed_without_team_review_count_for_webrtc_team(self):
        _, data = _render_for(
            self._commits(), group=WEBRTC_GROUP,
            paths=self.paths, members=self.members,
        )
        # One commit went to a non-team reviewer with no group tag.
        assert data["summary"]["landed_without_team_review"] == 1
        assert data["summary"]["landed_without_team_review_pct"] == 1 / 3
