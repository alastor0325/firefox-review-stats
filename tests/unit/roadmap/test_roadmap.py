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
                {"name": "A", "rating": "weak", "text": "t", "rests_on": ["x"]}
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
        assert v["aspects"][0]["name"] == "A"
        assert v["aspects"][0]["rests_on"] == ["x"]

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
