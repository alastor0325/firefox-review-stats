"""git log subprocess wrapper + pure parser.

`run_git_log` is the thin I/O shell. `parse_git_log_output` is the pure
function that converts raw `git log` text to `Commit` objects.
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime

from reviewstats.parse import (
    Reviewer,
    extract_differential_revision,
    is_excluded_author,
    parse_reviewers,
    should_skip_commit,
)


# Record separator (ASCII 30) to delimit commits unambiguously, since
# commit bodies contain blank lines.
_RECORD_SEP = "\x1e"
_GIT_LOG_FORMAT = f"%H%x09%aI%x09%an%x09%s%n%b{_RECORD_SEP}"


@dataclass(frozen=True)
class Commit:
    sha: str
    date: datetime
    author: str
    subject: str
    reviewers: list[Reviewer] = field(default_factory=list)
    differential_revision: str | None = None


def run_git_log(
    repo: str,
    path: str,
    since: str,
    *,
    exclude_paths: tuple[str, ...] = (),
) -> str:
    """Run `git log` and return raw stdout. I/O shell only."""
    args = [
        "git",
        "-C",
        repo,
        "log",
        f"--since={since}",
        f"--format={_GIT_LOG_FORMAT}",
        "--",
        path,
    ]
    args.extend(f":!{excl}" for excl in exclude_paths)
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout


def parse_git_log_output(raw: str) -> list[Commit]:
    commits: list[Commit] = []
    for record in raw.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        header, _, body = record.partition("\n")
        try:
            sha, date_str, author, subject = header.split("\t", 3)
        except ValueError:
            continue
        if should_skip_commit(subject) or is_excluded_author(author):
            continue
        commits.append(
            Commit(
                sha=sha,
                date=datetime.fromisoformat(date_str),
                author=author,
                subject=subject,
                reviewers=parse_reviewers(subject),
                differential_revision=extract_differential_revision(body),
            )
        )
    return commits
