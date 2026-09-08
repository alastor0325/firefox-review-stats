"""Pure parsing of commit subjects and bodies."""

import re
from dataclasses import dataclass

_REVIEWER_BLOCK_RE = re.compile(r"r[=?]([A-Za-z0-9_\-,#.]+)")
# Strip a trailing reviewer tag for human-friendly display. Consumes the
# leading whitespace too so "Fix something. r=padenot" collapses to
# "Fix something." with no dangling space. `!` covers blocking reviews
# (r=padenot!), which `_REVIEWER_BLOCK_RE` intentionally doesn't parse.
_REVIEW_TAG_RE = re.compile(r"\s+r[=?][A-Za-z0-9_\-,#.!]+")
_BUG_NUMBER_RE = re.compile(r"^Bug (\d+)")
# Strip the leading "Bug NNNN - " / "Bug NNNN: " so a change reads as a
# description, not a bug reference. A "Part N" marker (if any) is kept —
# it disambiguates a patch series; only the bug number is noise.
_BUG_PREFIX_RE = re.compile(r"^Bug \d+\s*[-:]\s*")
_DIFF_REV_RE = re.compile(
    r"^Differential Revision:\s*\S*/(D\d+)\s*$", re.MULTILINE
)
_LANDO_FORMAT_RE = re.compile(r"apply code formatting via Lando", re.IGNORECASE)
_MERGE_RE = re.compile(r"^Merge\b", re.IGNORECASE)
_REVERT_RE = re.compile(r"^Revert\b", re.IGNORECASE)
_GROUP_SUFFIXES = ("-reviewers", "-reviewers-rotation")
# Review groups the `-reviewers` suffix rule can't recognise. Two shapes:
# a project's secondary hashtag (`#dom-core` and `#dom-core-reviewers`
# both resolve to Phab project 178), and a project whose only hashtag
# has no suffix at all (`#webidl` is project 112). Both are common in
# mozilla-central subjects — `r=dom-core` accounts for 237 of that
# group's 575 tags over a 6-month window — and without this table they
# parse as *individuals*, so `_has_group()` misses them and the bare
# hashtag shows up as a phantom person in the non-member reviewer list.
#
# Values are the canonical name the rest of the pipeline matches on
# (`Team.group`); a suffixless project maps to itself. Keep this an
# explicit allow-list: inferring "looks like a component" would
# misclassify real handles.
_GROUP_ALIASES: dict[str, str] = {
    "dom-core": "dom-core-reviewers",  # Phab project 178
    "layout": "layout-reviewers",      # Phab project 126
    "webidl": "webidl",                # Phab project 112, no suffix
}
_EXCLUDED_AUTHORS = frozenset({"Lando"})


@dataclass(frozen=True)
class Reviewer:
    name: str
    is_group: bool


def canonical_group(token: str) -> str | None:
    """The canonical review-group name a reviewer token denotes, or
    None if the token is an individual.

    Aliases resolve to the spelling `Team.group` uses, so
    `r=dom-core` and `r=dom-core-reviewers` are the same group
    downstream.
    """
    if token in _GROUP_ALIASES:
        return _GROUP_ALIASES[token]
    return token if token.endswith(_GROUP_SUFFIXES) else None


def is_group_reviewer(token: str) -> bool:
    return canonical_group(token) is not None


def parse_reviewers(subject: str) -> list[Reviewer]:
    out: list[Reviewer] = []
    seen: set[str] = set()
    for match in _REVIEWER_BLOCK_RE.finditer(subject):
        for raw in match.group(1).split(","):
            token = raw.strip().lstrip("#").rstrip(".")
            if not token:
                continue
            group = canonical_group(token)
            # De-dup on the canonical name so a subject naming both an
            # alias and its canonical spelling yields one Reviewer.
            name = group or token
            if name in seen:
                continue
            seen.add(name)
            out.append(Reviewer(name=name, is_group=group is not None))
    return out


def should_skip_commit(subject: str) -> bool:
    if _LANDO_FORMAT_RE.search(subject):
        return True
    if _MERGE_RE.match(subject):
        return True
    if _REVERT_RE.match(subject):
        return True
    return False


def is_excluded_author(author: str) -> bool:
    return author in _EXCLUDED_AUTHORS


def extract_differential_revision(body: str) -> str | None:
    match = _DIFF_REV_RE.search(body)
    return match.group(1) if match else None


def extract_bug_number(subject: str) -> str | None:
    """Return the leading bug number ("Bug 1900123 - ...") or None.

    Only matches the canonical "Bug N" prefix at the start of the
    subject — a bug referenced mid-sentence is not the patch's own bug.
    """
    match = _BUG_NUMBER_RE.match(subject)
    return match.group(1) if match else None


def strip_reviewer_tag(subject: str) -> str:
    """Drop the trailing `r=…` / `r?…` reviewer tag from a subject so it
    reads cleanly in a human-facing list (the reviewer is shown
    elsewhere). A subject without a tag is returned unchanged."""
    return _REVIEW_TAG_RE.sub("", subject).rstrip()


def strip_bug_prefix(subject: str) -> str:
    """Drop a leading "Bug NNNN - " / "Bug NNNN: " so the change reads as a
    description rather than a bug reference. Only the leading occurrence is
    removed; a subject without the prefix is returned unchanged."""
    return _BUG_PREFIX_RE.sub("", subject, count=1)
