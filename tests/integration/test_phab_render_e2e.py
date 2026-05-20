"""End-to-end integration test for the wait-time half of the page.

`render_html` takes both `data` (git side) and `phab_data` (Phab
side). The page surfaces phab data in three places:
* Team / 6-Month: histogram + weekly median + summary tiles
* Team / Per-Week: most-recent-week slice
* Wait Queue view: per-revision table

Build a small but realistic phab_data dict, render, and verify the
specific numbers + the per-revision rows survive intact end-to-end.
"""

import json
import re

from reviewstats.render import render_html


def _extract(html: str, var: str) -> dict:
    m = re.search(rf"const {var} = (\{{.*?\}});\n", html, re.DOTALL)
    assert m is not None, f"{var} not embedded in HTML"
    return json.loads(m.group(1).replace("\\u003c", "<"))


_MIN_DATA = {
    "meta": {"path": "dom/media", "paths": ["dom/media"], "group": "g",
             "excludes": [], "window_start": "2026-04-15",
             "window_end": "2026-05-15",
             "generated_at": "2026-05-15T00:00:00Z"},
    "summary": {"total_patches": 1, "group_tagged_patches": 1,
                "group_tagged_pct": 1.0,
                "landed_without_team_review": 0,
                "landed_without_team_review_pct": 0,
                "landed_without_team_review_by_subdir": {},
                "landed_without_team_review_list": [],
                "unique_individuals": 1, "avg_per_week": 1.0},
    "concentration": {"top1_share": 1.0, "top3_share": 1.0,
                       "top5_share": 1.0, "gini": 0.0, "bus_factor": 1},
    "within_group_total": [{"name": "padenot", "count": 1, "pct": 1.0}],
    "sole_reviewer": [],
    "total_reviews_per_member": [
        {"name": "padenot", "in_group": 1, "out_of_group": 0, "total": 1},
    ],
    "weekly_trend": {"weeks": ["2026-W19", "2026-W20"],
                      "top_reviewers": ["padenot"],
                      "all_members": {"padenot": [0, 1]},
                      "authored_per_member": {"alwu": [1, 0]}},
    "members": {"padenot": "Paul Adenot", "alwu": "Alastor Wu"},
    "authors": {"top_total": [{"name": "Alastor Wu", "count": 1, "pct": 1.0}],
                "reviewer_matrix": {"Alastor Wu": {"padenot": 1}}},
    "per_member_authors": {"padenot": [{"name": "Alastor Wu", "count": 1}]},
    "member_authored_counts": {"alwu": 1, "padenot": 0},
}


_PHAB = {
    "n": 3,
    "histogram": [
        {"bucket": "< 1 day", "count": 1, "pct": 1 / 3},
        {"bucket": "1-3 days", "count": 1, "pct": 1 / 3},
        {"bucket": "3-7 days", "count": 1, "pct": 1 / 3},
        {"bucket": "1-2 weeks", "count": 0, "pct": 0.0},
        {"bucket": "2-4 weeks", "count": 0, "pct": 0.0},
        {"bucket": "> 1 month", "count": 0, "pct": 0.0},
    ],
    "percentiles": {"p50": 2.0, "p75": 4.0, "p90": 5.0},
    "weekly_median": [
        {"week": "2026-W19", "median_days": 1.0, "count": 1},
        {"week": "2026-W20", "median_days": 3.0, "count": 2},
    ],
    "last_week": {
        "week": "2026-W20",
        "n": 2,
        "histogram": [
            {"bucket": "< 1 day", "count": 0, "pct": 0.0},
            {"bucket": "1-3 days", "count": 1, "pct": 0.5},
            {"bucket": "3-7 days", "count": 1, "pct": 0.5},
            {"bucket": "1-2 weeks", "count": 0, "pct": 0.0},
            {"bucket": "2-4 weeks", "count": 0, "pct": 0.0},
            {"bucket": "> 1 month", "count": 0, "pct": 0.0},
        ],
        "percentiles": {"p50": 3.0, "p75": 4.0, "p90": 4.5},
    },
    "per_author": {
        "alwu": {"n_total": 2, "n_react": 2, "n_accept": 1,
                  "react_p50": 1.0, "react_p75": 2.0, "react_p90": 2.5,
                  "accept_p50": 3.0, "accept_p75": 3.0, "accept_p90": 3.0},
    },
    "patch_list": [
        {"d_number": "D101", "url": "https://example/D101",
         "title": "Bug 1 - patch a", "author": "alwu",
         "accept_actor": "padenot", "react_actor": "padenot",
         "react_action": "accept", "time_to_react_days": 1.5,
         "time_to_accept_days": 2.0, "wait_anchor": "creation"},
        {"d_number": "D102", "url": "https://example/D102",
         "title": "Bug 2 - patch b", "author": "alwu",
         "accept_actor": None, "react_actor": "padenot",
         "react_action": "comment", "time_to_react_days": 4.0,
         "time_to_accept_days": None, "wait_anchor": "queue-added"},
    ],
    "meta": {"generated_at": "2026-05-15T00:00:00+00:00",
             "n_commits": 1, "n_with_revision": 1,
             "n_with_wait_time": 3, "n_failures": 0, "partial": False},
}


def test_phab_data_embedded_into_rendered_html():
    """render_html must embed PHAB_DATA so the JS can read it; with
    no phab data the placeholder gets null."""
    html_with = render_html(_MIN_DATA, phab_data=_PHAB)
    html_without = render_html(_MIN_DATA, phab_data=None)
    assert "const PHAB_DATA = {" in html_with
    assert "const PHAB_DATA = null;" in html_without


def test_phab_summary_values_survive_render():
    html = render_html(_MIN_DATA, phab_data=_PHAB)
    phab = _extract(html, "PHAB_DATA")
    assert phab["n"] == 3
    assert phab["percentiles"] == {"p50": 2.0, "p75": 4.0, "p90": 5.0}


def test_phab_last_week_slice_survives_render():
    """Per-Week view consumes phab.last_week — verify the values
    arrive intact end-to-end."""
    html = render_html(_MIN_DATA, phab_data=_PHAB)
    phab = _extract(html, "PHAB_DATA")
    lw = phab["last_week"]
    assert lw["week"] == "2026-W20"
    assert lw["n"] == 2
    assert lw["percentiles"]["p50"] == 3.0


def test_wait_queue_rows_survive_render():
    """The Wait Queue table is JS-rendered from phab.patch_list.
    Verify the underlying records all made it into the embedded
    JSON."""
    html = render_html(_MIN_DATA, phab_data=_PHAB)
    phab = _extract(html, "PHAB_DATA")
    rows = phab["patch_list"]
    assert len(rows) == 2
    d_numbers = {r["d_number"] for r in rows}
    assert d_numbers == {"D101", "D102"}


def test_per_author_wait_tile_data_survives_render():
    """Member Profile per-author wait tiles read phab.per_author —
    verify percentiles + counts arrive intact."""
    html = render_html(_MIN_DATA, phab_data=_PHAB)
    phab = _extract(html, "PHAB_DATA")
    alwu = phab["per_author"]["alwu"]
    assert alwu["n_react"] == 2
    assert alwu["react_p50"] == 1.0
    assert alwu["accept_p75"] == 3.0
