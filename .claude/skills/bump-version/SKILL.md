---
description: >
  Release a new firefox-review-stats version: bump pyproject.toml, test, commit,
  tag, push, THEN file an issue on the fx-bug-toolkit repo so the downstream
  consumer stays in sync. fx-bug-toolkit's /open-team opens this dashboard's
  hosted site (no version pin), so the ask is lighter — but the fx-bug-toolkit
  issue step is still MANDATORY. Triggers on: "bump version", "/bump-version",
  "release review-stats", "cut a release".
allowed-tools: [Read, Edit, Bash, AskUserQuestion]
---

# firefox-review-stats Version Bump

fx-bug-toolkit's `/open-team` skill **opens this dashboard's hosted GitHub Pages
site** (`https://alastor0325.github.io/firefox-review-stats/`) — it does **not**
install or pin a version. So there is no pin to bump, but every release should
still file an issue so fx-bug-toolkit can review whether its `/open-team` tutorial
needs updating (e.g. the team list or the views changed).

**MANDATORY: the bump is not complete until the fx-bug-toolkit issue is filed
(Step 5). Do not report done before then.**

Downstream repo: **`alastor0325/fx-bug-toolkit`**.

---

## Step 1 — Decide the new version

```bash
grep -m1 '^version' pyproject.toml
```

Use the caller's level (`patch`/`minor`/`major`) or explicit version; otherwise
`AskUserQuestion`. Set `OLD` and `NEW`.

## Step 2 — Bump pyproject.toml

Edit only the `version` field under `[project]`.

## Step 3 — Test (green before committing — see CLAUDE.md)

```bash
python -m pytest tests/
```

A failing test is a hard blocker.

## Step 4 — Commit, tag, push

```bash
git add pyproject.toml <other release files>
git commit -m "release: vNEW

<one-line summary>"
git tag vNEW
git push origin <current-branch>
git push origin vNEW
```

(The dashboards republish to GitHub Pages via the weekly Action on push to the
default branch — nothing extra to deploy here.)

## Step 5 — File the fx-bug-toolkit issue (MANDATORY)

```bash
PREV=$(git describe --tags --abbrev=0 vNEW^ 2>/dev/null || echo "")
[ -n "$PREV" ] && git log --oneline "$PREV"..vNEW || git log --oneline -10 vNEW
```

Write the body to a temp file, then:

```bash
gh issue create -R alastor0325/fx-bug-toolkit \
  --title "firefox-review-stats bumped to vNEW — review /open-team if teams/views changed" \
  --label enhancement \
  --body-file /tmp/review-stats-bump-issue.md && rm -f /tmp/review-stats-bump-issue.md
```

The body must include:
- The new version **NEW** and previous **OLD**, and a short changelog.
- The ask: `/open-team` opens the **hosted** dashboards (no version pin to bump).
  Review whether its tutorial chapter needs updating — e.g. if the **registered
  teams** (`playback`/`webrtc`/`gfx`/…) or the **views** (Team / Member / Wait
  Queue / Recent Changes) changed. No action needed if the tutorial still matches.
- Source: the commit hash and tag `vNEW`.

Report the created issue URL.

## Step 6 — Summary

old → new, pushed tag, changelog, and the fx-bug-toolkit issue URL. If the issue
was NOT filed, say so loudly — the release is incomplete.
