"""Pure parsing of commit subjects and bodies."""

import re
from dataclasses import dataclass

_REVIEWER_BLOCK_RE = re.compile(r"r[=?]([A-Za-z0-9_\-,#.]+)")
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
