# firefox-review-stats Dev Loop

The **firefox-review-stats Dev Loop** is a mandatory workflow for all code changes. All steps are required and cannot be skipped.

## The Cycle

Development proceeds through six sequential steps: understand the task, extract & develop, write tests, agent review, commit & push, then conclude.

## Core Requirements

- All new or changed logic must be extracted into **pure/testable functions** (no I/O, no network calls) so they can be unit tested directly.
- Every function added or changed must have **unit tests** covering its branches. If behavior is removed, a test must assert the removal holds.
- **`pytest tests/unit/` must pass** before committing. Failing tests are a hard blocker — fix them, do not work around them.
- **README.md must be updated** whenever a command is added/removed or a flag/default changes.
- Unit tests go in `tests/unit/`, mock all I/O and network calls (git subprocess, Phabricator HTTP).
- Integration tests go in `tests/integration/` (only for changes touching real I/O or APIs).
- Write the failing test first — confirm it fails before implementing.

## Process Details

### Step 1 — Understand
Read the relevant source files before touching anything. Understand the existing structure: which functions are involved, what tests already cover them. The authoritative design doc is `~/firefox-bug-investigation/dom-media-reviewer-bottleneck-investigation.md` — consult it for scope, definitions, and chart specs.

### Step 2 — Extract & Develop
Write the implementation. Extract logic into named pure functions first, then call them from handlers/controllers. Keep entry points thin — they only wire up I/O (subprocess, HTTP, file writes) and call pure functions.

Examples of what to extract:
- `parse_reviewers(commit_subject: str) -> list[Reviewer]`
- `is_group_reviewer(token: str) -> bool`
- `compute_gini(counts: list[int]) -> float`
- `bucket_by_iso_week(dates: list[datetime]) -> dict[str, int]`

The shell that calls `git log` or `requests.get(phab_url)` should be a thin
wrapper that hands raw data to these pure functions.

### Step 3 — Write Tests
For every function added or changed, write unit tests:
- Happy path
- Each meaningful branch or flag
- Regression guards for removed behavior

Run and confirm green:
```
pytest tests/unit/
```

### Step 4 — Agent Review
Run `/simplify` to have a fresh-context agent review the changes for code quality, reuse, and efficiency. Apply any fixes before committing.

### Step 5 — Commit & Push
```
git commit -m "<type>: <what and why>"
git push
```
Both are required. Never commit without pushing. (If there is no remote configured yet, document why in the commit message and skip the push — record this as an open task.)

### Step 6 — Conclude
Summarize: what changed, what tests were added, whether README was updated.
