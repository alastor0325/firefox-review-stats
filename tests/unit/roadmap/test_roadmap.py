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

    def test_unknown_reach_no_longer_blocks_ranking(self):
        """Reach is gone, so it cannot disqualify anything. Confidence is the only
        gate left."""
        from reviewstats.roadmap import rankable
        assert rankable({"confidence": "high", "reach": "UNKNOWN"}) is True

    def test_continuous_is_rankable_now(self):
        """It used to be excluded so it could be budgeted as a share of time in its
        own bucket. With one list there is no bucket to hold it out of."""
        from reviewstats.roadmap import rankable
        assert rankable({"confidence": "high", "type": "perennial"}) is True



# --------------------------------------------------------------------------
# priority
# --------------------------------------------------------------------------

class TestImpactAsANumberIsGone:
    """`impact` was a single S1-S4 judgement and it is removed.

    It was unfalsifiable - most items had nothing behind it - and a quarter of them
    were rating a premise that verification showed to be stale or wrong, so the
    number was precise about something untrue. Four separately arguable dimensions
    replace it: see TestOurOwnRating.
    """

    def test_priority_no_longer_reads_an_impact_field(self):
        from reviewstats.roadmap import priority
        # An item with no impact at all must still order.
        assert isinstance(priority({"churn": "LEAVES"}), int)

    def test_priority_follows_churn_not_impact(self):
        from reviewstats.roadmap import priority
        assert priority({"churn": "LEAVES"}) > priority({"churn": "INVISIBLE"})

    def test_an_impact_field_left_in_the_data_changes_nothing(self):
        """Old rows may still carry it; it must not influence the order."""
        from reviewstats.roadmap import rating_key
        a = rating_key({"churn": "ANNOYS", "user_value": 2, "cost": "M",
                        "impact": "S1", "title": "a"})
        b = rating_key({"churn": "ANNOYS", "user_value": 2, "cost": "M",
                        "title": "a"})
        assert a == b


class TestSortItems:
    """One ordered list, not three buckets."""

    def _items(self):
        return [
            {"id": "s3", "title": "cheap s3", "impact": "S3",
             "confidence": "high", "cost": "S"},
            {"id": "s1", "title": "big s1", "impact": "S1",
             "confidence": "high", "cost": "L"},
            {"id": "low", "title": "unsure", "impact": "S1",
             "confidence": "low", "cost": "S"},
            {"id": "cont", "title": "upkeep", "impact": "S2",
             "confidence": "high", "cost": "S", "type": "perennial"},
        ]

    def test_returns_a_single_list_containing_everything(self):
        from reviewstats.roadmap import sort_items
        out = sort_items(self._items())
        assert isinstance(out, list)
        assert len(out) == 4

    def test_higher_churn_comes_first(self):
        from reviewstats.roadmap import sort_items
        items = [
            {"id": "annoy", "title": "a", "churn": "ANNOYS", "user_value": 2,
             "cost": "M", "confidence": "high"},
            {"id": "leave", "title": "b", "churn": "LEAVES", "user_value": 2,
             "cost": "M", "confidence": "high"},
        ]
        assert [i["id"] for i in sort_items(items)] == ["leave", "annoy"]

    def test_items_we_cannot_rank_sit_at_the_end(self):
        """Marked, not hidden: an S1 we are unsure about still has to be read."""
        from reviewstats.roadmap import sort_items
        ids = [i["id"] for i in sort_items(self._items())]
        assert ids[-1] == "low"

    def test_continuous_work_is_ordered_like_everything_else(self):
        """It used to be a third bucket budgeted rather than ranked."""
        from reviewstats.roadmap import sort_items
        ids = [i["id"] for i in sort_items(self._items())]
        assert ids.index("cont") < ids.index("low")

    def test_cost_breaks_a_tie_cheapest_first(self):
        from reviewstats.roadmap import sort_items
        items = [
            {"id": "big", "title": "a", "impact": "S2", "confidence": "high",
             "cost": "L"},
            {"id": "small", "title": "b", "impact": "S2", "confidence": "high",
             "cost": "S"},
        ]
        assert [i["id"] for i in sort_items(items)] == ["small", "big"]

    def test_is_stable_across_calls(self):
        from reviewstats.roadmap import sort_items
        a = [i["id"] for i in sort_items(self._items())]
        b = [i["id"] for i in sort_items(self._items())]
        assert a == b


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
    def test_counts_describe_one_list(self):
        """`measure` and `continuous` counts are gone with their buckets."""
        v = build_roadmap_view(doc(), audience="internal")
        assert set(v["counts"]) == {"total", "ranked", "needs_measuring"}
        assert v["counts"]["total"] == len(v["items"])
        assert (v["counts"]["ranked"] + v["counts"]["needs_measuring"]
                == v["counts"]["total"])

    def test_items_carry_a_measuring_flag_not_a_bucket(self):
        """The reader still needs to know where the order stops being
        evidence-backed; it marks the row instead of moving it."""
        v = build_roadmap_view(doc(), audience="internal")
        for i in v["items"]:
            assert "bucket" not in i
            assert isinstance(i["needs_measuring"], bool)

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


class TestOneListNotThreeBuckets:
    """One ordered list. `Continuous` is gone; `Need measuring first` is merged in.

    Three buckets asked a reader to hold three different orderings at once, and the
    split leaked a methodology decision into the product view: whether an item is
    rankable is a property of our evidence, not of the work. An item we cannot yet
    rank still has to be looked at, so it belongs in the same list, marked.

    `reach` goes with them. It was shown so it could be argued about, but it was
    also the thing forcing the buckets -- an unknown reach made an item unrankable
    -- and every metric it fed is TBD.
    """

    def _doc(self):
        return {
            "condition": [],
            "items": [
                {"id": "a", "title": "Ranked one", "impact": "S1",
                 "confidence": "high", "cost": "M", "consequence": "x"},
                {"id": "b", "title": "Unrankable one", "impact": "S2",
                 "confidence": "low", "cost": "S", "consequence": "y"},
                {"id": "c", "title": "Upkeep", "impact": "S3",
                 "confidence": "high", "cost": "S", "consequence": "z",
                 "continuous": True},
            ],
        }

    def test_every_item_lands_in_one_list(self):
        from reviewstats.roadmap import build_roadmap_view
        v = build_roadmap_view(self._doc(), audience="internal")
        assert len(v["items"]) == 3
        assert {i["id"] for i in v["items"]} == {"a", "b", "c"}

    def test_there_are_no_bucket_names_left(self):
        from reviewstats.roadmap import build_roadmap_view
        v = build_roadmap_view(self._doc(), audience="internal")
        assert {i.get("bucket") for i in v["items"]} == {None} or all(
            i.get("bucket") in (None, "ranked") for i in v["items"])
        assert "continuous" not in v["counts"]
        assert "measure" not in v["counts"]

    def test_an_unrankable_item_is_marked_rather_than_separated(self):
        """The reader still needs to know the order is not evidence-backed here."""
        from reviewstats.roadmap import build_roadmap_view
        v = build_roadmap_view(self._doc(), audience="internal")
        b = [i for i in v["items"] if i["id"] == "b"][0]
        assert b["needs_measuring"] is True
        a = [i for i in v["items"] if i["id"] == "a"][0]
        assert a["needs_measuring"] is False

    def test_ranked_items_come_before_unrankable_ones(self):
        from reviewstats.roadmap import build_roadmap_view
        v = build_roadmap_view(self._doc(), audience="internal")
        ids = [i["id"] for i in v["items"]]
        assert ids.index("a") < ids.index("b")

    def test_reach_is_not_rendered(self):
        from reviewstats.roadmap import build_roadmap_view
        doc = self._doc()
        doc["items"][0]["reach"] = 4
        v = build_roadmap_view(doc, audience="internal")
        a = [i for i in v["items"] if i["id"] == "a"][0]
        assert "reach" not in a
        assert all("reach" not in (f.get("label", "").lower())
                   for f in a.get("fields") or [])

    def test_an_unknown_reach_no_longer_makes_an_item_unrankable(self):
        """Reach is gone, so it cannot gate anything. Only low confidence does."""
        from reviewstats.roadmap import rankable
        assert rankable({"confidence": "high", "reach": "UNKNOWN"}) is True
        assert rankable({"confidence": "low"}) is False


class TestOurOwnRating:
    """Impact is replaced by four dimensions we can argue about separately.

    A single S1-S4 impact number was unfalsifiable: 33 of 39 items had no external
    anchor at all, and where one existed we disagreed with it as often as not. Worse,
    a quarter of the items turned out to be rating a premise that was stale or wrong,
    so the number was precise about something untrue.

    Bugzilla's severity is deliberately NOT the anchor - that is their triage of a
    single bug report, and it does not exist for most of these. Instead each item
    carries:

      fills       what kind of hole this closes
      user_value  what a user gets if we do it
      churn       whether not doing it costs us the user
      cost        how much work

    Ordering is churn, then user_value, then cheapest first - so "users leave over
    this and it is cheap" floats to the top, which is the question a roadmap is for.
    """

    def _item(self, **kw):
        base = {"id": "x", "title": "t", "consequence": "c",
                "fills": "BLOCKED", "user_value": 4, "churn": "LEAVES",
                "cost": "M", "confidence": "high"}
        base.update(kw)
        return base

    def test_churn_dominates_the_order(self):
        """A cheap polish item must not outrank something users leave over."""
        from reviewstats.roadmap import sort_items
        items = [self._item(id="polish", churn="ANNOYS", user_value=1, cost="S"),
                 self._item(id="leaves", churn="LEAVES", user_value=4, cost="XL")]
        assert [i["id"] for i in sort_items(items)] == ["leaves", "polish"]

    def test_value_does_not_order_the_list(self):
        """It is no longer a column, so it must not move rows. A field that
        reorders invisibly is the hidden-score problem again: a reader cannot tell
        why one row sits above another. It still shows in the expansion."""
        from reviewstats.roadmap import sort_items
        items = [self._item(id="a", churn="ANNOYS", user_value=1, cost="M"),
                 self._item(id="b", churn="ANNOYS", user_value=4, cost="M")]
        # Tie broken by title, not by value.
        assert [i["id"] for i in sort_items(items)] == ["a", "b"]

    def test_cost_breaks_a_churn_tie(self):
        from reviewstats.roadmap import sort_items
        items = [self._item(id="big", churn="ANNOYS", cost="XL"),
                 self._item(id="cheap", churn="ANNOYS", cost="S")]
        assert [i["id"] for i in sort_items(items)] == ["cheap", "big"]

    def test_cheapest_first_when_value_and_churn_tie(self):
        from reviewstats.roadmap import sort_items
        items = [self._item(id="big", cost="XL"), self._item(id="small", cost="S")]
        assert [i["id"] for i in sort_items(items)] == ["small", "big"]

    def test_a_quick_win_is_real_churn_at_low_cost(self):
        from reviewstats.roadmap import is_quick_win
        assert is_quick_win(self._item(churn="LEAVES", cost="M")) is True
        assert is_quick_win(self._item(churn="LEAVES", cost="XL")) is False
        assert is_quick_win(self._item(churn="INVISIBLE", cost="S")) is False

    def test_value_no_longer_makes_a_quick_win(self):
        """It is invisible in the table, so it must not drive a visible marker."""
        from reviewstats.roadmap import is_quick_win
        assert is_quick_win(
            self._item(user_value=4, churn="INVISIBLE", cost="S")) is False

    def test_churn_alone_can_make_a_quick_win(self):
        """Users leaving is worth doing even at middling user value."""
        from reviewstats.roadmap import is_quick_win
        assert is_quick_win(
            self._item(user_value=2, churn="LEAVES", cost="M")) is True
        assert is_quick_win(
            self._item(user_value=2, churn="INVISIBLE", cost="M")) is False

    def test_an_unrated_item_sorts_last_rather_than_defaulting_high(self):
        """A missing rating must not be silently treated as severe."""
        from reviewstats.roadmap import sort_items
        items = [self._item(id="rated"),
                 {"id": "unrated", "title": "t", "cost": "M",
                  "confidence": "high"}]
        assert [i["id"] for i in sort_items(items)][-1] == "unrated"

    def test_the_rendered_item_carries_all_four_dimensions(self):
        from reviewstats.roadmap import build_roadmap_view
        v = build_roadmap_view({"items": [self._item()], "condition": []},
                               audience="internal")
        it = v["items"][0]
        for f in ("fills", "user_value", "churn", "cost", "quick_win"):
            assert f in it, f

    def test_impact_is_no_longer_required(self):
        """Items carry no `impact` field; nothing may depend on one."""
        from reviewstats.roadmap import build_roadmap_view
        v = build_roadmap_view({"items": [self._item()], "condition": []},
                               audience="internal")
        assert "impact" not in v["items"][0]
