"""Unit tests for the roadmap view model behind the Media Health view.

The roadmap is hand-curated YAML living outside this repo. These tests cover
the pure transforms that turn it into the JSON the page consumes:

  * the ranking gate — impact x reach, with low confidence or unknown reach
    making an item deliberately unrankable
  * the three buckets (ranked / measure / continuous)
  * the internal-vs-public split, which is the part that must not regress:
    the dashboard is a public GitHub Pages site and the roadmap carries
    candid internal assessment
"""

import pytest

from reviewstats.roadmap import (
    build_roadmap_view,
    is_continuous,
    priority,
    rankable,
    sort_items,
    strip_internal,
)


def item(**kw):
    """A minimal valid item; override only what a test cares about."""
    base = {
        "id": "x",
        "scope": "reliability",
        "type": "MISSING",
        "title": "t",
        "consequence": "c",
        "impact": "S2",
        "reach": 2,
        "confidence": "high",
        "cost": "M",
        "outcome_tags": ["PLATFORM"],
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# is_continuous
# --------------------------------------------------------------------------

class TestIsContinuous:
    @pytest.mark.parametrize("t", ["SPEC", "UPKEEP"])
    def test_spec_and_upkeep_are_continuous(self, t):
        assert is_continuous(item(type=t)) is True

    @pytest.mark.parametrize("t", ["MISSING", "DEFECT", "UNKNOWN"])
    def test_everything_else_is_not(self, t):
        assert is_continuous(item(type=t)) is False


# --------------------------------------------------------------------------
# rankable — the gate
# --------------------------------------------------------------------------

class TestRankable:
    def test_high_confidence_known_reach_is_rankable(self):
        assert rankable(item(confidence="high", reach=3)) is True

    def test_med_confidence_is_still_rankable(self):
        """Only `low` blocks ranking; med is explicitly allowed."""
        assert rankable(item(confidence="med", reach=3)) is True

    def test_low_confidence_is_not_rankable(self):
        assert rankable(item(confidence="low", reach=3)) is False

    def test_unknown_reach_is_not_rankable(self):
        assert rankable(item(reach="UNKNOWN")) is False

    def test_continuous_is_never_rankable(self):
        """SPEC/UPKEEP have no meaningful reach, so they bypass the gate
        entirely rather than being ranked against features."""
        assert rankable(item(type="SPEC", confidence="high", reach=4)) is False


# --------------------------------------------------------------------------
# priority
# --------------------------------------------------------------------------

class TestPriority:
    @pytest.mark.parametrize(
        "impact,reach,expected",
        [("S1", 4, 16), ("S1", 1, 4), ("S2", 3, 9), ("S3", 2, 4), ("S4", 4, 4)],
    )
    def test_impact_times_reach(self, impact, reach, expected):
        assert priority(item(impact=impact, reach=reach)) == expected

    def test_s4_wide_reach_collides_with_s1_narrow(self):
        """Documents a known weakness rather than endorsing it: with impact
        weighted 4/3/2/1 against reach 1-4, 'polish for everyone' scores the
        same as 'total failure for a niche'. Pinned so a future weighting
        change is a deliberate act with a failing test, not a silent drift."""
        assert priority(item(impact="S4", reach=4)) == priority(
            item(impact="S1", reach=1)
        )


# --------------------------------------------------------------------------
# sort_items — bucketing and order
# --------------------------------------------------------------------------

class TestSortItems:
    def test_splits_into_three_buckets(self):
        items = [
            item(id="ranked", confidence="high", reach=2),
            item(id="lowconf", confidence="low", reach=2),
            item(id="noreach", reach="UNKNOWN"),
            item(id="spec", type="SPEC"),
            item(id="upkeep", type="UPKEEP"),
        ]
        ranked, measure, cont = sort_items(items)
        assert [i["id"] for i in ranked] == ["ranked"]
        assert sorted(i["id"] for i in measure) == ["lowconf", "noreach"]
        assert sorted(i["id"] for i in cont) == ["spec", "upkeep"]

    def test_ranked_is_ordered_by_descending_priority(self):
        items = [
            item(id="low", impact="S4", reach=1),
            item(id="high", impact="S1", reach=4),
            item(id="mid", impact="S2", reach=2),
        ]
        ranked, _, _ = sort_items(items)
        assert [i["id"] for i in ranked] == ["high", "mid", "low"]

    def test_cost_breaks_priority_ties_cheapest_first(self):
        items = [
            item(id="expensive", impact="S2", reach=2, cost="XL"),
            item(id="cheap", impact="S2", reach=2, cost="S"),
        ]
        ranked, _, _ = sort_items(items)
        assert [i["id"] for i in ranked] == ["cheap", "expensive"]

    def test_impact_breaks_ties_before_cost(self):
        """Review finding: with cost-then-title tie-breaking, an S3 could
        outrank an S1 on the letter of its title inside a 7-way score tie.
        Severity must win before cost so row order stays meaningful."""
        items = [
            # Both score 4. S1 must come first despite the later title
            # and the more expensive cost.
            item(id="a-minor", impact="S3", reach=2, cost="S", title="aaa"),
            item(id="z-severe", impact="S1", reach=1, cost="L", title="zzz"),
        ]
        ranked, _, _ = sort_items(items)
        assert [i["id"] for i in ranked] == ["z-severe", "a-minor"]

    def test_is_stable_across_calls(self):
        items = [item(id=f"i{n}", impact="S2", reach=2) for n in range(5)]
        first = [i["id"] for i in sort_items(items)[0]]
        assert first == [i["id"] for i in sort_items(items)[0]]


# --------------------------------------------------------------------------
# strip_internal — the public/internal split
# --------------------------------------------------------------------------

class TestStripInternal:
    def test_internal_block_removed_for_public(self):
        it = item(internal={"notes": "Netflix is the holdout"})
        out = strip_internal(it, audience="public")
        assert "internal" not in out

    def test_internal_block_kept_for_internal_audience(self):
        it = item(internal={"notes": "secret"})
        out = strip_internal(it, audience="internal")
        assert out["internal"] == {"notes": "secret"}

    def test_named_fields_are_withheld_for_public(self):
        it = item(owner="gfx - contested", internal={"withhold": ["owner"]})
        out = strip_internal(it, audience="public")
        assert "owner" not in out
        assert out["withheld"] == ["owner"]

    def test_withheld_fields_are_kept_for_internal(self):
        it = item(owner="gfx - contested", internal={"withhold": ["owner"]})
        out = strip_internal(it, audience="internal")
        assert out["owner"] == "gfx - contested"
        assert out["withheld"] == []

    def test_multiple_fields_withheld(self):
        it = item(
            owner="John",
            details="candid",
            internal={"withhold": ["owner", "details"]},
        )
        out = strip_internal(it, audience="public")
        assert "owner" not in out and "details" not in out
        assert sorted(out["withheld"]) == ["details", "owner"]

    def test_item_without_internal_block_is_unchanged(self):
        it = item(owner="alwu")
        out = strip_internal(it, audience="public")
        assert out["owner"] == "alwu"
        assert out["withheld"] == []

    def test_does_not_mutate_the_input(self):
        it = item(owner="John", internal={"withhold": ["owner"]})
        strip_internal(it, audience="public")
        assert it["owner"] == "John", "input item must not be mutated"
        assert "internal" in it

    def test_rejects_unknown_audience(self):
        with pytest.raises(ValueError):
            strip_internal(item(), audience="somethingelse")


# --------------------------------------------------------------------------
# build_roadmap_view
# --------------------------------------------------------------------------

def doc(**kw):
    base = {
        "updated": "2026-08-07",
        "condition": {
            "summary": "s",
            "aspects": [
                {"name": "A", "rating": "weak", "text": "t",
                 "sub": [{"name": "A1", "rating": "weak", "text": "t1",
                          "rests_on": ["x"]}]}
            ],
        },
        "scopes": [{"id": "reliability", "title": "Reliability", "ends": True,
                    "blurb": "b"}],
        "metrics": [{"id": "m", "title": "M", "source": "src", "exists": True,
                     "target": "TBD", "cross_browser": ["firefox", "chrome"]}],
        "items": [item(id="x")],
        "questions": [{"q": "q", "why": "w"}],
        "closed": [{"what": "c", "why": "y"}],
    }
    base.update(kw)
    return base


class TestBuildRoadmapView:
    def test_counts_match_buckets(self):
        v = build_roadmap_view(
            doc(items=[
                item(id="a", confidence="high", reach=2),
                item(id="b", confidence="low", reach=2),
                item(id="c", type="SPEC"),
            ]),
            audience="internal",
        )
        assert v["counts"] == {
            "total": 3, "ranked": 1, "measure": 1, "continuous": 1
        }

    def test_items_carry_their_bucket(self):
        v = build_roadmap_view(
            doc(items=[
                item(id="a", confidence="high", reach=2),
                item(id="b", type="UPKEEP"),
            ]),
            audience="internal",
        )
        by_id = {i["id"]: i for i in v["items"]}
        assert by_id["a"]["bucket"] == "ranked"
        assert by_id["b"]["bucket"] == "continuous"

    def test_audience_is_recorded_in_the_payload(self):
        v = build_roadmap_view(doc(), audience="public")
        assert v["audience"] == "public"

    def test_no_internal_content_reaches_the_public_payload(self):
        """The load-bearing guarantee. The dashboard is public; a leak here
        publishes candid internal assessment. Serialise the whole payload and
        assert the secret string is nowhere in it."""
        import json

        secret = "NETFLIX-IS-THE-HOLDOUT-SENTINEL"
        v = build_roadmap_view(
            doc(items=[item(id="a", details=secret,
                            internal={"withhold": ["details"],
                                      "notes": secret})]),
            audience="public",
        )
        assert secret not in json.dumps(v)

    def test_internal_payload_does_include_it(self):
        import json

        secret = "NETFLIX-IS-THE-HOLDOUT-SENTINEL"
        v = build_roadmap_view(
            doc(items=[item(id="a", details=secret,
                            internal={"withhold": ["details"]})]),
            audience="internal",
        )
        assert secret in json.dumps(v)

    def test_condition_aspects_are_carried_through(self):
        v = build_roadmap_view(doc(), audience="internal")
        aspect = v["aspects"][0]
        assert aspect["name"] == "A"
        # rests_on is authored on the sub-category and rolled up here.
        assert aspect["sub"][0]["rests_on"] == ["x"]
        assert aspect["rests_on"] == ["x"]

    def test_metrics_flag_missing_targets(self):
        v = build_roadmap_view(doc(), audience="internal")
        assert v["metrics"][0]["target"] == "TBD"
        assert v["metrics_without_target"] == 1

    def test_prose_is_flattened_for_display(self):
        """YAML block scalars arrive with embedded newlines; the page renders
        them in table cells, so they are collapsed at build time."""
        v = build_roadmap_view(
            doc(items=[item(id="a", consequence="one\ntwo\n  three\n")]),
            audience="internal",
        )
        assert v["items"][0]["consequence"] == "one two three"

    def test_rejects_unknown_audience(self):
        with pytest.raises(ValueError):
            build_roadmap_view(doc(), audience="world")

    def test_raw_internal_block_never_reaches_the_payload(self):
        """Not even on internal builds. Nothing renders `internal.notes`, and
        `<slug>/index.html` is git-tracked and published, so carrying the block
        through would be a leak path with no upside."""
        import json

        secret = "RAW-INTERNAL-BLOCK-SENTINEL"
        for audience in ("internal", "public"):
            v = build_roadmap_view(
                doc(items=[item(id="a", internal={"notes": secret})]),
                audience=audience,
            )
            assert secret not in json.dumps(v), audience

    def test_unrendered_sections_are_not_shipped(self):
        """`scopes`, `questions` and `closed` carry prose with no withhold
        path and nothing renders them, so they stay out of the payload until
        something does."""
        v = build_roadmap_view(doc(), audience="public")
        for key in ("scopes", "questions", "closed"):
            assert key not in v, f"{key} should not be in the payload yet"

    def test_derivable_fields_are_not_duplicated(self):
        """`bucket` already encodes both predicates."""
        v = build_roadmap_view(doc(), audience="internal")
        assert "rankable" not in v["items"][0]
        assert "continuous" not in v["items"][0]


class TestAspectWithholding:
    """Aspect prose is the most quotable text on the page and some of it names
    partners and other teams, so an aspect can be withheld wholesale."""

    def _doc(self):
        return doc(condition={
            "summary": "s",
            "aspects": [
                {"name": "Public one", "rating": "good", "text": "fine"},
                {"name": "Candid one", "rating": "weak",
                 "text": "NAMES-A-PARTNER-SENTINEL", "internal": True},
            ],
        })

    def test_internal_aspect_dropped_for_public(self):
        v = build_roadmap_view(self._doc(), audience="public")
        assert [a["name"] for a in v["aspects"]] == ["Public one"]
        assert v["aspects_withheld"] == 1

    def test_internal_aspect_text_absent_from_public_payload(self):
        import json

        v = build_roadmap_view(self._doc(), audience="public")
        assert "NAMES-A-PARTNER-SENTINEL" not in json.dumps(v)

    def test_internal_aspect_kept_for_internal(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        assert len(v["aspects"]) == 2
        assert v["aspects_withheld"] == 0


class TestAspectSubCategories:
    """An aspect is a big category that expands into the sub-categories it is
    made of. `rests_on` lives on the sub-category so there is a single place to
    edit; the aspect's list is the computed union of its children."""

    def _doc(self):
        return doc(
            items=[item(id="a"), item(id="b"), item(id="c")],
            condition={
                "summary": "s",
                "aspects": [{
                    "name": "Big one",
                    "rating": "mixed",
                    "text": "top level prose",
                    "sub": [
                        {"name": "First", "rating": "weak", "text": "t1",
                         "rests_on": ["a", "b"]},
                        {"name": "Second", "rating": "good", "text": "t2",
                         "rests_on": ["b", "c"]},
                    ],
                }],
            },
        )

    def test_sub_categories_are_projected(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        subs = v["aspects"][0]["sub"]
        assert [s["name"] for s in subs] == ["First", "Second"]
        assert subs[0]["rating"] == "weak"
        assert subs[0]["rests_on"] == ["a", "b"]

    def test_aspect_rests_on_is_the_union_of_its_children(self):
        """Deduplicated and order-preserving, so 'b' appears once."""
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["aspects"][0]["rests_on"] == ["a", "b", "c"]

    def test_aspect_item_count_is_exposed(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["aspects"][0]["item_count"] == 3

    def test_sub_prose_is_flattened(self):
        d = self._doc()
        d["condition"]["aspects"][0]["sub"][0]["text"] = "one\ntwo\n  three\n"
        v = build_roadmap_view(d, audience="internal")
        assert v["aspects"][0]["sub"][0]["text"] == "one two three"

    def test_aspect_without_sub_still_works(self):
        """Not every aspect has to be decomposed."""
        d = doc(condition={"summary": "s", "aspects": [
            {"name": "Plain", "rating": "good", "text": "t"}]})
        v = build_roadmap_view(d, audience="internal")
        assert v["aspects"][0]["sub"] == []
        assert v["aspects"][0]["rests_on"] == []

    def test_internal_sub_category_withheld_from_public(self):
        """A single sub-category can be held back without losing the whole
        card — the aspect still renders, one child fewer."""
        import json

        d = self._doc()
        d["condition"]["aspects"][0]["sub"][1]["internal"] = True
        d["condition"]["aspects"][0]["sub"][1]["text"] = "SUB-SECRET-SENTINEL"

        pub = build_roadmap_view(d, audience="public")
        assert [s["name"] for s in pub["aspects"][0]["sub"]] == ["First"]
        assert "SUB-SECRET-SENTINEL" not in json.dumps(pub)
        assert pub["aspects"][0]["subs_withheld"] == 1

        intl = build_roadmap_view(d, audience="internal")
        assert len(intl["aspects"][0]["sub"]) == 2
        assert intl["aspects"][0]["subs_withheld"] == 0

    def test_withheld_sub_items_drop_out_of_the_union(self):
        """The union must reflect what is actually shown, or the card would
        claim items the reader cannot see."""
        d = self._doc()
        d["condition"]["aspects"][0]["sub"][1]["internal"] = True
        pub = build_roadmap_view(d, audience="public")
        assert pub["aspects"][0]["rests_on"] == ["a", "b"]


class TestItemlessGoodSubCategories:
    """The roadmap tracks problems. A sub-category rated `good` with nothing on
    the roadmap is a status claim wearing a roadmap costume — it expands to
    "nothing here", which is noise. An itemless *weak* sub-category is the
    opposite: it says a known problem has no work against it, which is worth
    surfacing loudly. So the rule is about `good`, not about emptiness."""

    def _aspect(self, *subs):
        return doc(items=[item(id="a")], condition={
            "summary": "s",
            "aspects": [{"name": "Big", "rating": "mixed", "text": "t",
                         "sub": list(subs)}],
        })

    def test_itemless_good_sub_is_dropped(self):
        d = self._aspect(
            {"name": "Fine", "rating": "good", "text": "t", "rests_on": []},
            {"name": "Real", "rating": "weak", "text": "t", "rests_on": ["a"]},
        )
        v = build_roadmap_view(d, audience="internal")
        assert [x["name"] for x in v["aspects"][0]["sub"]] == ["Real"]

    def test_good_sub_with_items_is_kept(self):
        """Where work exists, the sub-category earns its place even at good."""
        d = self._aspect(
            {"name": "Mostly fine", "rating": "good", "text": "t",
             "rests_on": ["a"]},
        )
        v = build_roadmap_view(d, audience="internal")
        assert [x["name"] for x in v["aspects"][0]["sub"]] == ["Mostly fine"]

    def test_itemless_weak_sub_is_kept(self):
        d = self._aspect(
            {"name": "Bad and unowned", "rating": "weak", "text": "t",
             "rests_on": []},
        )
        v = build_roadmap_view(d, audience="internal")
        assert [x["name"] for x in v["aspects"][0]["sub"]] == ["Bad and unowned"]

    def test_aspect_level_good_is_untouched(self):
        """Aspects are an assessment, not a work list, so they may be good."""
        d = doc(condition={"summary": "s", "aspects": [
            {"name": "Fine area", "rating": "good", "text": "t"}]})
        v = build_roadmap_view(d, audience="internal")
        assert v["aspects"][0]["rating"] == "good"


class TestMatrixMetrics:
    """`metrics:` holds two kinds of entry: a scalar we track against a target,
    and a coverage matrix. Coverage used to be asserted in prose as "codec
    coverage is good"; it is measurable, so it is measured."""

    def _doc(self):
        return doc(metrics=[
            {"id": "s1", "title": "Scalar one", "source": "Raptor",
             "exists": True, "target": "TBD", "cross_browser": ["firefox"]},
            {"id": "s2", "title": "Scalar two", "source": "Raptor",
             "exists": True, "target": "< 200ms"},
            {"id": "cov", "kind": "matrix", "title": "Container x codec",
             "source": "tree", "exists": True,
             "verified": "rev abc, 2026-08-07",
             "columns": ["H.264", "VP9"],
             "rows": [{"name": "MP4", "cells": ["yes", "yes"]},
                      {"name": "WebM", "cells": ["no", "yes"]}],
             "note": "n"},
        ])

    def test_scalar_is_the_default_kind(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        by_id = {m["id"]: m for m in v["metrics"]}
        assert by_id["s1"]["kind"] == "scalar"

    def test_matrix_kind_is_carried(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        by_id = {m["id"]: m for m in v["metrics"]}
        assert by_id["cov"]["kind"] == "matrix"

    def test_matrix_columns_and_rows_are_projected(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        cov = next(m for m in v["metrics"] if m["kind"] == "matrix")
        assert cov["columns"] == ["H.264", "VP9"]
        assert cov["rows"] == [
            {"name": "MP4", "cells": ["yes", "yes"]},
            {"name": "WebM", "cells": ["no", "yes"]},
        ]

    def test_matrix_carries_its_verification_stamp(self):
        """A measured claim needs a revision behind it or it is just prose."""
        v = build_roadmap_view(self._doc(), audience="internal")
        cov = next(m for m in v["metrics"] if m["kind"] == "matrix")
        assert cov["verified"] == "rev abc, 2026-08-07"

    def test_matrices_are_excluded_from_the_missing_target_count(self):
        """A coverage grid has no target, so counting it as 'no target set'
        would inflate the number that gates the perennial scope."""
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["metrics_without_target"] == 1  # only s1

    def test_matrix_row_cell_count_mismatch_is_reported(self):
        d = self._doc()
        d["metrics"][2]["rows"][0]["cells"] = ["yes"]  # one short
        v = build_roadmap_view(d, audience="internal")
        cov = next(m for m in v["metrics"] if m["kind"] == "matrix")
        assert cov["malformed_rows"] == ["MP4"]

    def test_wellformed_matrix_reports_no_malformed_rows(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        cov = next(m for m in v["metrics"] if m["kind"] == "matrix")
        assert cov["malformed_rows"] == []


class TestNestedSubCategories:
    """Sub-categories nest arbitrarily deep. Codec support turned out to need
    three levels: the aspect, the kind of gap, then the surface it shows up on
    (element / MSE / WebCodecs / recording), because those are different
    problems that were previously mixed into one 'missing formats' bucket."""

    def _doc(self):
        return doc(
            items=[item(id="a"), item(id="b"), item(id="c"), item(id="d")],
            condition={"summary": "s", "aspects": [{
                "name": "Top", "rating": "good", "text": "t",
                "sub": [
                    {"name": "Mid", "rating": "mixed", "text": "m", "sub": [
                        {"name": "Leaf1", "rating": "weak", "text": "l1",
                         "rests_on": ["a", "b"]},
                        {"name": "Leaf2", "rating": "mixed", "text": "l2",
                         "rests_on": ["b", "c"]},
                    ]},
                    {"name": "Flat", "rating": "mixed", "text": "f",
                     "rests_on": ["d"]},
                ],
            }]},
        )

    def test_third_level_is_projected(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        mid = v["aspects"][0]["sub"][0]
        assert [x["name"] for x in mid["sub"]] == ["Leaf1", "Leaf2"]

    def test_union_rolls_up_through_every_level(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        aspect = v["aspects"][0]
        assert aspect["sub"][0]["rests_on"] == ["a", "b", "c"]
        assert aspect["rests_on"] == ["a", "b", "c", "d"]
        assert aspect["item_count"] == 4

    def test_intermediate_level_needs_no_items_of_its_own(self):
        """A grouping level exists to organise its children, so the
        itemless-`good` rule must not delete a mixed/weak grouping node."""
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["aspects"][0]["sub"][0]["name"] == "Mid"

    def test_depth_is_exposed_for_rendering(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        aspect = v["aspects"][0]
        assert aspect["sub"][0]["depth"] == 1
        assert aspect["sub"][0]["sub"][0]["depth"] == 2

    def test_leaf_flag_distinguishes_grouping_from_content(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        mid = v["aspects"][0]["sub"][0]
        assert mid["has_children"] is True
        assert mid["sub"][0]["has_children"] is False

    def test_withholding_a_leaf_removes_it_from_every_ancestor_union(self):
        d = self._doc()
        d["condition"]["aspects"][0]["sub"][0]["sub"][1]["internal"] = True
        v = build_roadmap_view(d, audience="public")
        aspect = v["aspects"][0]
        assert aspect["sub"][0]["rests_on"] == ["a", "b"]
        assert aspect["rests_on"] == ["a", "b", "d"]

    def test_itemless_good_rule_applies_at_every_depth(self):
        d = self._doc()
        d["condition"]["aspects"][0]["sub"][0]["sub"].append(
            {"name": "Fine", "rating": "good", "text": "x", "rests_on": []}
        )
        v = build_roadmap_view(d, audience="internal")
        names = [x["name"] for x in v["aspects"][0]["sub"][0]["sub"]]
        assert "Fine" not in names


class TestAspectOrdering:
    """Cards are ordered by condition, worst first, so the page opens on what
    needs attention instead of on whatever the YAML happened to list first.
    Order matches the existing markdown renderer's convention."""

    def _doc(self, *ratings):
        return doc(condition={"summary": "s", "aspects": [
            {"name": f"A{i}", "rating": r, "text": "t"}
            for i, r in enumerate(ratings)
        ]})

    def test_worst_first(self):
        v = build_roadmap_view(
            self._doc("good", "mixed", "weak", "unknown"), audience="internal"
        )
        assert [a["rating"] for a in v["aspects"]] == [
            "weak", "unknown", "mixed", "good"
        ]

    def test_unknown_sorts_above_mixed(self):
        """"We cannot answer this" outranks "partly fine": an unmeasurable area
        is a worse position to be in than a known-uneven one."""
        v = build_roadmap_view(self._doc("mixed", "unknown"), audience="internal")
        assert [a["rating"] for a in v["aspects"]] == ["unknown", "mixed"]

    def test_authored_order_is_preserved_within_a_rating(self):
        """Stable sort, so equally-rated cards keep the sequence the author
        chose rather than being alphabetised into noise."""
        v = build_roadmap_view(
            self._doc("weak", "weak", "weak"), audience="internal"
        )
        assert [a["name"] for a in v["aspects"]] == ["A0", "A1", "A2"]

    def test_unrecognised_rating_sorts_last_without_raising(self):
        """A typo in the YAML should not reorder the page or crash the build."""
        v = build_roadmap_view(self._doc("typo", "weak"), audience="internal")
        assert [a["rating"] for a in v["aspects"]] == ["weak", "typo"]

    def test_nested_levels_are_sorted_too(self):
        """The same worst-first rule applies all the way down, so a reader
        scanning any expanded node meets its problems first."""
        d = doc(condition={"summary": "s", "aspects": [{
            "name": "A", "rating": "weak", "text": "t",
            "sub": [
                {"name": "fine", "rating": "good", "text": "t",
                 "rests_on": ["x"]},
                {"name": "bad", "rating": "weak", "text": "t",
                 "rests_on": ["x"]},
                {"name": "uneven", "rating": "mixed", "text": "t",
                 "rests_on": ["x"]},
            ],
        }]})
        v = build_roadmap_view(d, audience="internal")
        assert [s["name"] for s in v["aspects"][0]["sub"]] == [
            "bad", "uneven", "fine"
        ]

    def test_third_level_is_sorted(self):
        d = doc(condition={"summary": "s", "aspects": [{
            "name": "A", "rating": "weak", "text": "t",
            "sub": [{"name": "mid", "rating": "mixed", "text": "t", "sub": [
                {"name": "leaf-mixed", "rating": "mixed", "text": "t",
                 "rests_on": ["x"]},
                {"name": "leaf-weak", "rating": "weak", "text": "t",
                 "rests_on": ["x"]},
            ]}],
        }]})
        v = build_roadmap_view(d, audience="internal")
        leaves = v["aspects"][0]["sub"][0]["sub"]
        assert [x["name"] for x in leaves] == ["leaf-weak", "leaf-mixed"]

    def test_sort_is_stable_within_a_rating_at_every_level(self):
        d = doc(condition={"summary": "s", "aspects": [{
            "name": "A", "rating": "weak", "text": "t",
            "sub": [
                {"name": "one", "rating": "weak", "text": "t", "rests_on": ["x"]},
                {"name": "two", "rating": "weak", "text": "t", "rests_on": ["x"]},
                {"name": "three", "rating": "weak", "text": "t",
                 "rests_on": ["x"]},
            ],
        }]})
        v = build_roadmap_view(d, audience="internal")
        assert [s["name"] for s in v["aspects"][0]["sub"]] == [
            "one", "two", "three"
        ]

    def test_union_order_follows_the_sorted_reading_order(self):
        """The item union is built in reading order, so re-sorting children
        re-sorts the union — otherwise the chips under a node would not match
        the order of the children they came from."""
        d = doc(items=[item(id="p"), item(id="q")], condition={
            "summary": "s", "aspects": [{
                "name": "A", "rating": "weak", "text": "t",
                "sub": [
                    {"name": "later", "rating": "good", "text": "t",
                     "rests_on": ["p"]},
                    {"name": "first", "rating": "weak", "text": "t",
                     "rests_on": ["q"]},
                ],
            }]})
        v = build_roadmap_view(d, audience="internal")
        assert v["aspects"][0]["rests_on"] == ["q", "p"]


class TestParityTags:
    """Items may declare which other engines ship the thing we lack. Nodes roll
    up the union of their descendants', so a card can be read as "Chrome and
    Safari both have this". Absent means unverified, never "they lack it"."""

    def _doc(self):
        return doc(
            items=[
                # Anchored: parity is only projected with a proof link.
                item(id="a", parity=["chrome", "safari"],
                     mdn_url="https://developer.mozilla.org/docs/Web/API/HTMLMediaElement/remote"),
                item(id="b", parity=["chrome"], mdn_url="https://developer.mozilla.org/docs/Web/API/AudioListener/positionX"),
                item(id="c"),
            ],
            condition={"summary": "s", "aspects": [{
                "name": "A", "rating": "weak", "text": "t", "sub": [
                    {"name": "one", "rating": "weak", "text": "t",
                     "rests_on": ["a"]},
                    {"name": "two", "rating": "weak", "text": "t",
                     "rests_on": ["b", "c"]},
                ],
            }]},
        )

    def test_item_parity_is_projected(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        by_id = {i["id"]: i for i in v["items"]}
        assert by_id["a"]["parity"] == ["chrome", "safari"]

    def test_item_without_parity_gets_an_empty_list(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        by_id = {i["id"]: i for i in v["items"]}
        assert by_id["c"]["parity"] == []

    def test_node_parity_is_the_union_of_its_items(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        subs = {s["name"]: s for s in v["aspects"][0]["sub"]}
        assert subs["one"]["parity"] == ["chrome", "safari"]
        assert subs["two"]["parity"] == ["chrome"]

    def test_parity_does_not_roll_up_to_the_aspect(self):
        """Superseded behaviour: it used to. A parent gets one proof link while
        covering several children, so the rollup made it look like the link
        backed all of them. See TestParityOnlyWhereAuthored."""
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["aspects"][0]["parity"] == []

    def test_parity_order_is_stable_not_set_order(self):
        """Rendered as tail tags, so the order must be deterministic across
        builds rather than whatever a set iteration produced."""
        v1 = build_roadmap_view(self._doc(), audience="internal")
        v2 = build_roadmap_view(self._doc(), audience="internal")
        assert v1["aspects"][0]["parity"] == v2["aspects"][0]["parity"]
        assert v1["aspects"][0]["parity"] == sorted(v1["aspects"][0]["parity"])

    def test_withheld_sub_takes_its_parity_tag_with_it(self):
        d = self._doc()
        d["condition"]["aspects"][0]["sub"][0]["internal"] = True
        v = build_roadmap_view(d, audience="public")
        names = [x["name"] for x in v["aspects"][0]["sub"]]
        assert names == ["two"], names
        # The surviving sub keeps its own tag; the withheld one's is gone.
        assert v["aspects"][0]["sub"][0]["parity"] == ["chrome"]


class TestParityProof:
    """A parity tag is a claim about another engine, so it must be citable. The
    rule is enforced here rather than by convention: parity with no proof anchor
    is dropped, because an uncitable tag reads as verified when it is not."""

    def test_parity_survives_when_a_web_feature_anchors_it(self):
        v = build_roadmap_view(
            doc(items=[item(id="a", parity=["chrome"],
                            mdn_url="https://developer.mozilla.org/docs/Web/API/HTMLMediaElement/remote")]),
            audience="internal",
        )
        assert v["items"][0]["parity"] == ["chrome"]

    def test_parity_is_dropped_without_a_proof_anchor(self):
        v = build_roadmap_view(
            doc(items=[item(id="a", parity=["chrome", "safari"])]),
            audience="internal",
        )
        assert v["items"][0]["parity"] == []

    def test_proof_url_is_the_mdn_page(self):
        url = "https://developer.mozilla.org/docs/Web/API/ManagedMediaSource"
        v = build_roadmap_view(
            doc(items=[item(id="a", parity=["safari"], mdn_url=url,
                            mdn_bcd="api.ManagedMediaSource")]),
            audience="internal",
        )
        assert v["items"][0]["parity_url"] == url
        assert v["items"][0]["parity_bcd"] == "api.ManagedMediaSource"

    def test_no_url_when_there_is_no_mdn_page(self):
        v = build_roadmap_view(doc(items=[item(id="a")]), audience="internal")
        assert v["items"][0]["parity_url"] == ""

    def test_node_carries_the_proof_url_of_its_items(self):
        url = "https://developer.mozilla.org/docs/Web/API/HTMLMediaElement/remote"
        d = doc(
            items=[item(id="a", parity=["chrome"], mdn_url=url)],
            condition={"summary": "s", "aspects": [{
                "name": "A", "rating": "weak", "text": "t",
                "sub": [{"name": "one", "rating": "weak", "text": "t",
                         "rests_on": ["a"]}],
            }]},
        )
        v = build_roadmap_view(d, audience="internal")
        sub = v["aspects"][0]["sub"][0]
        assert sub["parity"] == ["chrome"]
        assert sub["parity_url"] == url

    def test_unproven_item_contributes_no_parity_to_its_node(self):
        d = doc(
            items=[item(id="a", parity=["chrome", "safari"])],
            condition={"summary": "s", "aspects": [{
                "name": "A", "rating": "weak", "text": "t",
                "sub": [{"name": "one", "rating": "weak", "text": "t",
                         "rests_on": ["a"]}],
            }]},
        )
        v = build_roadmap_view(d, audience="internal")
        assert v["aspects"][0]["sub"][0]["parity"] == []
        assert v["aspects"][0]["parity"] == []


class TestParityOnlyWhereAuthored:
    """A parity tag belongs on the node that actually names the item, not on an
    ancestor. A rolled-up union carries one proof link while covering several
    children, so the parent appears to cite evidence for claims that link does
    not cover. Computing from the node's OWN items makes both the aspect card
    and intermediate grouping nodes fall out with no tag, without special-casing
    either."""

    def _doc(self):
        url = "https://developer.mozilla.org/docs/Web/API/ManagedMediaSource"
        return doc(
            items=[
                item(id="proven", parity=["safari"], mdn_url=url),
                item(id="plain"),
            ],
            condition={"summary": "s", "aspects": [{
                "name": "Top", "rating": "mixed", "text": "t", "sub": [
                    {"name": "Group", "rating": "mixed", "text": "t", "sub": [
                        {"name": "Leaf with proof", "rating": "weak", "text": "t",
                         "rests_on": ["proven"]},
                        {"name": "Leaf without", "rating": "weak", "text": "t",
                         "rests_on": ["plain"]},
                    ]},
                ],
            }]},
        )

    def test_aspect_card_has_no_parity_tag(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["aspects"][0]["parity"] == []
        assert v["aspects"][0]["parity_url"] == ""

    def test_intermediate_grouping_node_has_no_parity_tag(self):
        """Same defect one level down: a grouping node covers several children
        and could only ever link to one of them."""
        v = build_roadmap_view(self._doc(), audience="internal")
        group = v["aspects"][0]["sub"][0]
        assert group["has_children"] is True
        assert group["parity"] == []

    def test_leaf_that_names_a_proven_item_keeps_its_tag(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        leaves = {s["name"]: s for s in v["aspects"][0]["sub"][0]["sub"]}
        assert leaves["Leaf with proof"]["parity"] == ["safari"]
        assert leaves["Leaf with proof"]["parity_url"].endswith("ManagedMediaSource")

    def test_leaf_without_a_proven_item_gets_nothing(self):
        v = build_roadmap_view(self._doc(), audience="internal")
        leaves = {s["name"]: s for s in v["aspects"][0]["sub"][0]["sub"]}
        assert leaves["Leaf without"]["parity"] == []

    def test_item_union_still_rolls_up(self):
        """Only parity stops rolling up — the item count a card advertises must
        still cover everything beneath it."""
        v = build_roadmap_view(self._doc(), audience="internal")
        assert v["aspects"][0]["rests_on"] == ["proven", "plain"]
        assert v["aspects"][0]["item_count"] == 2


class TestSourceAnchoredParity:
    """Codec, container and DRM gaps have no MDN data at any granularity, so
    they anchor on a line in the other engine's source instead. Either anchor
    counts; neither means no tag."""

    def test_source_proof_anchors_parity(self):
        url = ("https://chromium.googlesource.com/chromium/src/+/main/"
               "media/base/mime_util_internal.cc#318")
        v = build_roadmap_view(
            doc(items=[item(id="a", parity=["chrome"], parity_proof=url,
                            parity_evidence="mkv_audio_codecs includes FLAC")]),
            audience="internal",
        )
        got = v["items"][0]
        assert got["parity"] == ["chrome"]
        assert got["parity_url"] == url
        assert got["parity_evidence"] == "mkv_audio_codecs includes FLAC"

    def test_mdn_wins_when_both_are_present(self):
        v = build_roadmap_view(
            doc(items=[item(id="a", parity=["chrome"],
                            mdn_url="https://developer.mozilla.org/x",
                            parity_proof="https://example.invalid/y")]),
            audience="internal",
        )
        assert v["items"][0]["parity_url"] == "https://developer.mozilla.org/x"

    def test_evidence_alone_is_not_an_anchor(self):
        """Prose explaining the claim is not a citation."""
        v = build_roadmap_view(
            doc(items=[item(id="a", parity=["chrome"],
                            parity_evidence="I read the source, trust me")]),
            audience="internal",
        )
        assert v["items"][0]["parity"] == []
