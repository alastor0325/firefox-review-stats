"""Roadmap view model — the Roadmap subview of the Media Health view.

The media roadmap is hand-curated YAML that lives outside this repo (in the
investigation repo). This module holds the pure transforms that turn that
document into the JSON the page consumes; all file reading lives in the caller.

Two things here carry more weight than the rest.

**The ranking gate.** Items are ordered by impact x reach. An item whose
confidence is `low`, or whose reach is unknown, is deliberately *not* ranked —
the next action on it is to find out, not to build. `SPEC` and `UPKEEP` never
rank at all: they have no meaningful reach and are budgeted as a share of time.

**The internal/public split.** This dashboard is published to a public GitHub
Pages site, and the roadmap carries candid internal assessment: cross-team ownership
questions, partner and provider names, individual owners. An item may declare an `internal:`
block naming the fields to withhold:

    - id: example-item
      consequence: >          # public, neutral phrasing
        A capability ships, but few providers have enabled it.
      internal:
        withhold: [details]
        notes: >              # never rendered publicly
          <partner name> is the holdout.

Illustrative placeholders on purpose. An earlier version of this docstring used a
real partner name and a real ownership dispute as its example, which published --
in source, in a public repo -- precisely what the mechanism exists to withhold.

`audience="public"` drops the `internal:` block entirely and removes every
field it names, recording them in `withheld` so the page can show that
something was held back rather than silently omitting it.

A condition aspect may also carry `internal: true` to be omitted wholesale —
the aspect prose is the most quotable thing on the page and some of it names
partners and other teams.

Callers should default to `public`. `internal` output is a strict *superset*,
and `<slug>/index.html` is git-tracked and served from GitHub Pages, so an
internal build that gets committed publishes exactly the fields the annotation
was added to protect. The raw `internal:` block is never copied into the
payload at any audience: nothing renders it, so carrying it would be risk
without benefit.

Known gap: only items and aspects have a withhold path. `condition.summary`
carries no annotation mechanism yet, so it must be written to be publishable.
"""

IMPACT_WEIGHT = {"S1": 4, "S2": 3, "S3": 2, "S4": 1}
COST_ORDER = {"S": 0, "M": 1, "L": 2, "XL": 3}

# Continuous work is not ranked by impact x reach: there is no "reach" for
# maintaining CI health or editing a spec, and forcing one invites fake numbers.
CONTINUOUS_TYPES = frozenset({"SPEC", "UPKEEP"})

AUDIENCES = frozenset({"internal", "public"})

# Condition cards are ordered worst-first, so the page opens on what needs
# attention rather than on whatever the YAML listed first. `unknown` sorts above
# `mixed` deliberately: an area we cannot measure is a worse position to be in
# than one we know is uneven. Matches the markdown renderer's existing order.
# An unrecognised rating sorts last rather than raising -- a typo should not
# reorder the page or break the build.
RATING_ORDER = {"weak": 0, "unknown": 1, "mixed": 2, "good": 3}
_RATING_LAST = len(RATING_ORDER)


def _worst_first(nodes: list[dict]) -> list[dict]:
    """Order rendered nodes worst-first. Stable, so equally-rated siblings keep
    the sequence the author chose. Applied at every level of the tree, so a
    reader scanning any expanded node meets its problems first."""
    return sorted(
        nodes, key=lambda n: RATING_ORDER.get(n["rating"], _RATING_LAST)
    )

# Fields copied onto every rendered item. Anything not listed stays out of the
# payload, so adding a field to the YAML cannot silently publish it.
_ITEM_FIELDS = (
    "id", "scope", "sub_scope", "initiative", "type", "title", "consequence",
    "details", "evidence", "owner", "fills", "user_value", "churn",
    "rating_note", "confidence", "cost",
    "demand", "support",
)

# Which other engines are verified to ship the capability we lack. Rendered as
# tail tags on a card. Absent means "not verified", never "they lack it too" --
# the free-text `support:` field mixes version numbers, states and prose, so
# parity is declared explicitly rather than inferred from it.
PARITY_ENGINES = ("chrome", "safari")

# A parity tag is a claim about another engine, so it has to be citable. The
# anchor is an MDN browser-compat-data key (`mdn_bcd`) plus the MDN page it
# documents (`mdn_url`), so the tag links to the compatibility table it was
# verified against rather than asserting the claim.
#
# BCD is keyed per interface *member*, which matters: it can prove a
# sub-capability gap (AudioContext.setSinkId) that feature-level data cannot,
# because at feature level Firefox ships AudioContext.
#
# Two rules applied when reading BCD, both of which changed answers:
#   * A flagged implementation is NOT parity -- audioTracks is Chrome-behind-a-
#     flag, so Chrome does not count for it.
#   * Where Firefox ships the member and the gap is narrower still (which
#     codecs MediaRecorder accepts), BCD cannot express it.
#
# For those narrower gaps -- codec, container and DRM level -- MDN has no data at
# all, so the anchor is a line in the other engine's source instead
# (`parity_proof`, with the reasoning in `parity_evidence`). Either anchor
# counts. Parity with neither is dropped: an uncitable tag reads as verified.
#
# A tag is shown only on the node that names the item, never on an ancestor.
# Rolling it up would give a parent one proof link while covering several
# children, so the parent would appear to cite evidence for claims that link
# does not support. Because `rests_on` is authored on leaves, computing parity
# from a node's OWN items makes aspect cards and grouping nodes come out
# untagged without either being special-cased.


def _check_audience(audience: str) -> None:
    if audience not in AUDIENCES:
        known = ", ".join(sorted(AUDIENCES))
        raise ValueError(f"Unknown audience {audience!r}. Expected one of: {known}.")


def flatten(text: object) -> str:
    """Collapse a YAML block scalar to one line.

    Block scalars arrive with embedded newlines and indentation; the page
    renders this prose inside table cells, so it is flattened at build time
    rather than in the browser.
    """
    if text is None:
        return ""
    return " ".join(str(text).split())


def is_continuous(item: dict) -> bool:
    """True for work with no end state, which is budgeted rather than ranked."""
    return item.get("type") in CONTINUOUS_TYPES



# ---------------------------------------------------------------------------
# Our own rating, replacing a single impact number.
#
# The impact field was unfalsifiable: most items had nothing behind it, and a
# quarter of them turned out to be rating a premise that was stale or wrong.
# Bugzilla's severity is deliberately not used as the anchor either -- that is one
# reporter's triage of one bug, it exists for a handful of these items, and where
# it existed we disagreed with it as often as we agreed.
#
# So four things are rated separately, because they are separately arguable:
#
#   fills       the kind of hole being closed
#   user_value  what a user actually gets
#   churn       whether NOT doing it costs us the user
#   cost        how much work
#
# Order is churn, then user_value, then cheapest first. That puts "users leave over
# this and it is not expensive" at the top, which is the only question a roadmap
# order needs to answer.

# What kind of hole. Ordered worst first for display grouping.
FILLS = ("BLOCKED", "BROKEN", "ABSENT-API", "POLISH")
FILLS_LABEL = {
    "BLOCKED": "content does not work",
    "BROKEN": "works, but badly",
    "ABSENT-API": "sites cannot use it",
    "POLISH": "refinement",
}

# Does failing this cost us the user? This is the dimension a severity number
# cannot express, and the one that most deserves to drive the order.
CHURN = ("LEAVES", "SECOND-BROWSER", "ANNOYS", "INVISIBLE")
CHURN_LABEL = {
    "LEAVES": "user switches browser",
    "SECOND-BROWSER": "user keeps another browser for this",
    "ANNOYS": "user notices and stays",
    "INVISIBLE": "only developers notice",
}
CHURN_RANK = {v: i for i, v in enumerate(CHURN)}

# What a user gets if we do it. 4 is highest.
USER_VALUE_LABEL = {
    4: "content that failed now works",
    3: "something bad now works well",
    2: "a capability sites can adopt",
    1: "refinement",
}

# Cheap enough that the value is worth having now.
_QUICK_COSTS = ("S", "M")


def is_quick_win(item: dict) -> bool:
    """We are losing users over it, and it is cheap.

    Churn alone, deliberately. `user_value` used to count here too, but it is no
    longer displayed, and a marker driven by a field nobody can see is the same
    hidden-arithmetic problem the score had.
    """
    if str(item.get("cost")) not in _QUICK_COSTS:
        return False
    return str(item.get("churn")) in ("LEAVES", "SECOND-BROWSER")


def rating_key(item: dict) -> tuple:
    """Sort key: churn, then cheapest.

    `user_value` deliberately does NOT order here. It is no longer a column, and a
    field that moves rows without being visible is the hidden-score problem again:
    a reader cannot tell why row 9 sits above row 10. It is still authored and
    still shown in the expansion, where it informs without steering.

    An unrated item sorts last rather than defaulting to severe -- a missing
    judgement must not read as an urgent one.
    """
    return (
        0 if item.get("churn") else 1,
        CHURN_RANK.get(str(item.get("churn")), len(CHURN)),
        COST_ORDER.get(str(item.get("cost")), 9),
        str(item.get("title", "")),
    )


def rankable(item: dict) -> bool:
    """Whether we can honestly place this item in a priority order.

    Low confidence means we are not sure the problem is real, so ordering it
    against items we do understand would be guessing. That is now the only gate:
    `reach` used to disqualify an item too, and removing reach removes that.

    Unrankable items are no longer separated out -- they sit at the end of the one
    list, marked. Whether we can rank something is a fact about our evidence, not
    about the work, and it should not decide whether a reader sees it.
    """
    return item.get("confidence") != "low"


def priority(item: dict) -> int:
    """Kept as a thin alias so callers do not break; the real order is
    `rating_key`. Impact-as-a-number is gone: see the note above FILLS."""
    return -CHURN_RANK.get(str(item.get("churn")), len(CHURN))


def sort_items(items: list[dict]) -> list[dict]:
    """One list, ordered by our own rating -- see rating_key.

    Unrankable items (low confidence) still sort after rated ones, marked rather
    than separated.
    """
    return sorted(items, key=lambda i: (0 if rankable(i) else 1, *rating_key(i)))


def strip_internal(item: dict, *, audience: str) -> dict:
    """Return a copy of `item` filtered for `audience`.

    For `public`: drops the `internal:` block and every field it names in
    `withhold`, listing them in `withheld` so the page can mark the gap
    honestly. For `internal`: keeps everything, with `withheld` empty. The
    input is never mutated.
    """
    _check_audience(audience)
    out = dict(item)
    internal = out.get("internal") or {}
    withhold = list(internal.get("withhold") or [])

    if audience == "public":
        out.pop("internal", None)
        for field in withhold:
            out.pop(field, None)
        out["withheld"] = sorted(withhold)
    else:
        out["withheld"] = []
    return out


def _render_item(item: dict, *, audience: str) -> dict:
    """Project one item onto the payload shape, after audience filtering.

    There is no `bucket` any more: one list, with `needs_measuring` marking the
    items whose order is not evidence-backed. Whether we can rank something is a
    fact about our evidence rather than about the work, so it marks a row instead
    of moving it out of sight.

    The raw `internal:` block is never copied through: nothing renders it, so
    carrying it would only create a way for it to escape.
    """
    filtered = strip_internal(item, audience=audience)
    out = {"needs_measuring": not rankable(item),
           "quick_win": is_quick_win(filtered),
           "withheld": filtered["withheld"]}

    for field in _ITEM_FIELDS:
        if field not in filtered:
            continue
        value = filtered[field]
        # Prose fields are flattened; structured ones pass through.
        if field == "support":
            out[field] = dict(value or {})
        else:
            out[field] = flatten(value)

    out["tags"] = list(filtered.get("outcome_tags") or []) + list(
        filtered.get("area_tags") or []
    )
    # MDN first, then a source line for the gaps MDN cannot express.
    proof = (str(filtered.get("mdn_url") or "").strip()
             or str(filtered.get("parity_proof") or "").strip())
    out["parity_url"] = proof
    out["parity_evidence"] = flatten(filtered.get("parity_evidence"))
    out["parity_bcd"] = str(filtered.get("mdn_bcd") or "").strip()
    out["parity"] = sorted(
        e for e in (filtered.get("parity") or []) if e in PARITY_ENGINES
    ) if proof else []
    return out


def _render_metric(metric: dict) -> dict:
    """Project one metrics entry. Two kinds live in the same list:

    ``scalar`` (the default) is a number tracked over time against a target.
    ``matrix`` is a coverage grid -- what is supported where. Coverage used to
    be asserted in the condition narrative as "codec coverage is good"; it is
    measurable from the tree, so it is measured here instead, and carries the
    revision it was checked against.
    """
    kind = metric.get("kind") or "scalar"
    out = {
        "id": metric.get("id", ""),
        "kind": kind,
        "title": metric.get("title", ""),
        "source": flatten(metric.get("source")),
        "exists": bool(metric.get("exists")),
        "note": flatten(metric.get("note")),
    }

    if kind == "matrix":
        columns = list(metric.get("columns") or [])
        rows = [
            {"name": r.get("name", ""), "cells": list(r.get("cells") or [])}
            for r in metric.get("rows") or []
        ]
        out["columns"] = columns
        out["rows"] = rows
        out["verified"] = metric.get("verified", "")
        # Surfaced rather than raised: a ragged row is an authoring slip in a
        # file this code only reads, and losing the whole page over it would be
        # worse than rendering the rest and naming the offender.
        out["malformed_rows"] = [
            r["name"] for r in rows if len(r["cells"]) != len(columns)
        ]
    else:
        out["target"] = str(metric.get("target", "TBD"))
        out["cross_browser"] = list(metric.get("cross_browser") or [])

    return out


def _visible_children(node: dict, *, audience: str) -> list[dict]:
    """The children of `node` that this audience may see.

    Two filters. Withheld children drop out for the public build. And a child
    rated `good` with nothing beneath it drops out at every depth: the roadmap
    tracks problems, so a `good` leaf with no work is a status claim in a
    roadmap's clothing — it expands to "nothing here". An itemless *weak* child
    is the opposite and stays: it says a known problem has no work against it.
    A grouping node is never removed by that rule, because its items live in
    its children rather than on itself.
    """
    children = [
        c for c in (node.get("sub") or [])
        if audience == "internal" or not c.get("internal")
    ]
    return [
        c for c in children
        if c.get("rating") != "good"
        or (c.get("rests_on") or [])
        or (c.get("sub") or [])
    ]


def _render_sub(
    node: dict, *, audience: str, depth: int, parity_by_item: dict
) -> dict:
    """Project one sub-category and everything nested under it.

    Nesting is unbounded by design. Codec support needed three levels — the
    aspect, the kind of gap, then the API surface it shows up on — because those
    are different problems that a single "missing formats" bucket had been
    mixing together.

    `rests_on` is authored on the node it actually describes; every ancestor's
    list is the deduplicated union of its descendants plus its own. Computing it
    means no level can claim items the reader cannot see beneath it.
    """
    children = _worst_first([
        _render_sub(c, audience=audience, depth=depth + 1,
                    parity_by_item=parity_by_item)
        for c in _visible_children(node, audience=audience)
    ])

    # Order-preserving dedup: reading order decides the order, and an item cited
    # twice appears once.
    union: list[str] = []
    for iid in list(node.get("rests_on") or []):
        if iid not in union:
            union.append(iid)
    for c in children:
        for iid in c["rests_on"]:
            if iid not in union:
                union.append(iid)

    # Own items only, not `union` -- see the note on parity above.
    parity, parity_url = _parity_for(
        list(node.get("rests_on") or []), parity_by_item
    )
    return {
        "name": node.get("name", ""),
        "rating": node.get("rating", "unknown"),
        "text": flatten(node.get("text")),
        "parity": parity,
        "parity_url": parity_url,
        "depth": depth,
        "sub": children,
        "has_children": bool(children),
        "rests_on": union,
        "item_count": len(union),
    }


def _parity_for(
    item_ids: list[str], parity_by_item: dict
) -> tuple[list[str], str]:
    """Union of the engines that ship what these items describe, plus a proof
    link. Sorted so the tail tags are deterministic across builds. The link is
    the first proven item's -- a node can cover several features, and one
    citation the reader can follow beats none.
    """
    engines: set[str] = set()
    url = ""
    for iid in item_ids:
        entry = parity_by_item.get(iid) or {}
        if entry.get("parity"):
            engines.update(entry["parity"])
            url = url or entry.get("parity_url", "")
    return sorted(engines), url


def _render_aspect(aspect: dict, *, audience: str, parity_by_item: dict) -> dict:
    """Project one condition aspect — the top of the tree.

    An aspect is the big category shown on a card; expanding it reveals the
    sub-categories it is made of, which may themselves expand.
    """
    all_subs = aspect.get("sub") or []
    visible = _visible_children(aspect, audience=audience)
    subs = _worst_first([
        _render_sub(c, audience=audience, depth=1,
                    parity_by_item=parity_by_item)
        for c in visible
    ])

    union: list[str] = []
    for s in subs:
        for iid in s["rests_on"]:
            if iid not in union:
                union.append(iid)

    return {
        "name": aspect.get("name", ""),
        "rating": aspect.get("rating", "unknown"),
        "text": flatten(aspect.get("text")),
        # Aspects never carry `rests_on` themselves, so they never carry a tag.
        "parity": [],
        "parity_url": "",
        "sub": subs,
        "subs_withheld": len(all_subs) - len(visible),
        "rests_on": union,
        "item_count": len(union),
    }


def build_roadmap_view(doc: dict, audience: str = "internal") -> dict:
    """Build the JSON payload for the Roadmap subview.

    `audience` defaults to `internal`. The public build must be requested
    explicitly, so an un-annotated roadmap cannot be published by accident.
    """
    _check_audience(audience)

    ordered = sort_items(doc.get("items") or [])
    items = [_render_item(i, audience=audience) for i in ordered]

    condition = doc.get("condition") or {}
    # An aspect marked `internal: true` is dropped wholesale from the public
    # build, and so is an individual sub-category — the card still renders, one
    # child fewer. Aspect prose is the most quotable text on the page, and some
    # of it names partners and other teams.
    all_aspects = condition.get("aspects") or []
    visible_aspects = [
        a for a in all_aspects
        if audience == "internal" or not a.get("internal")
    ]
    # Worst first, at every level of the tree. Sorted here rather than in the
    # template so the order is a tested property of the data and the two
    # renderers cannot drift.
    # Built from the projected items, so a withheld item cannot contribute a
    # parity tag to a card that no longer shows it.
    parity_by_item = {
        i["id"]: {"parity": i.get("parity") or [],
                  "parity_url": i.get("parity_url", "")}
        for i in items
    }
    aspects = _worst_first([
        _render_aspect(a, audience=audience, parity_by_item=parity_by_item)
        for a in visible_aspects
    ])

    metrics = [_render_metric(m) for m in doc.get("metrics") or []]

    return {
        "updated": str(doc.get("updated", "")),
        "audience": audience,
        "summary": flatten(condition.get("summary")),
        "aspects": aspects,
        "aspects_withheld": len(all_aspects) - len(visible_aspects),
        "items": items,
        "metrics": metrics,
        # Only scalars have targets; counting a coverage grid as "no target set"
        # would inflate the number that gates the perennial scope.
        "metrics_without_target": sum(
            1 for m in metrics
            if m["kind"] == "scalar" and m["target"] == "TBD"
        ),
        # `scopes`, `questions` and `closed` are deliberately NOT projected.
        # Nothing renders them yet, and they carry prose with no withhold path,
        # so shipping them would put unreviewed text into a public artifact for
        # no benefit. Add them back — with audience filtering — in the change
        # that actually renders them.
        "counts": {
            "total": len(items),
            # How many are ordered on evidence rather than sitting at the end
            # waiting to be measured. One list, so this is a property of it
            # rather than the size of a separate bucket.
            "ranked": sum(1 for i in items if not i["needs_measuring"]),
            "needs_measuring": sum(1 for i in items if i["needs_measuring"]),
        },
    }
