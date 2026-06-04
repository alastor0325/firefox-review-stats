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
_EXCLUDED_AUTHORS = frozenset({"Lando"})


@dataclass(frozen=True)
class Reviewer:
    name: str
    is_group: bool


def is_group_reviewer(token: str) -> bool:
    return token.endswith(_GROUP_SUFFIXES)


def parse_reviewers(subject: str) -> list[Reviewer]:
    out: list[Reviewer] = []
    seen: set[str] = set()
    for match in _REVIEWER_BLOCK_RE.finditer(subject):
        for raw in match.group(1).split(","):
            name = raw.strip().lstrip("#").rstrip(".")
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(Reviewer(name=name, is_group=is_group_reviewer(name)))
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
