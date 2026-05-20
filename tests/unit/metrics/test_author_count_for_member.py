"""`author_count_for_member` must return the same number that the Top
Authors chart shows for the same member, so the Member Profile view
stays consistent with the 6-month view.
"""

from reviewstats.report import author_count_for_member


_MEMBERS = {
    "alwu": "Alastor Wu",
    "padenot": "Paul Adenot",
    "kinetik": "Matthew Gregan",
}
_TOP_AUTHORS = [
    {"name": "Alastor Wu", "count": 120, "pct": 0.18},
    {"name": "Paul Adenot", "count": 63, "pct": 0.10},
    {"name": "Andreas Pehrson", "count": 55, "pct": 0.085},
]


def test_known_member_returns_chart_count():
    assert author_count_for_member("alwu", _MEMBERS, _TOP_AUTHORS) == 120


def test_member_not_in_top_authors_returns_zero():
    # kinetik has 0 authored patches in this window — top_authors row
    # is absent, so we expect 0 rather than a KeyError.
    assert author_count_for_member("kinetik", _MEMBERS, _TOP_AUTHORS) == 0


def test_unknown_member_returns_zero():
    assert author_count_for_member("not-a-member", _MEMBERS, _TOP_AUTHORS) == 0


def test_matches_real_data_for_every_member():
    """End-to-end consistency: for every listed member, the count we
    return must equal the row in the canonical Top Authors list.

    Build a small Top Authors list that contains every member's
    canonical name with a specific count, then iterate.
    """
    members = {
        "alwu": "Alastor Wu",
        "aosmond": "Andrew Osmond",
        "padenot": "Paul Adenot",
    }
    expected = {
        "Alastor Wu": 120,
        "Andrew Osmond": 71,
        "Paul Adenot": 63,
    }
    top = [{"name": n, "count": c, "pct": 1.0} for n, c in expected.items()]
    for member, canonical in members.items():
        assert author_count_for_member(member, members, top) == expected[canonical]
