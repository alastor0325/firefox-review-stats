#!/usr/bin/env bash
#
# Local refresh of the Recent Changes overviews.
#
# The Anthropic key is intentionally NOT stored in GitHub, so the LLM
# overviews can only be generated where the key lives — your machine.
# This script regenerates the GitHub-commit reports (which include the
# Recent Changes feed + overviews), writing each overview into the
# git-tracked .summary_cache/ so the weekly CI run reuses it without a key.
#
# Run it whenever you want fresh overviews (it also picks up new landings):
#
#   ANTHROPIC_API_KEY=sk-ant-... ./refresh-overviews.sh
#
# Requires: the `anthropic` package installed (pip install anthropic) and a
# GitHub token reachable by analyze_git.py (GH_TOKEN env or `gh auth token`).
# Optional: REVIEW_STATS_SUMMARY_MODEL to override the model (default opus).

set -euo pipefail
cd "$(dirname "$0")"

: "${ANTHROPIC_API_KEY:?set ANTHROPIC_API_KEY (the key is never committed)}"

# Prefer the project venv if present (it has anthropic + playwright).
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python

echo "Pulling latest..."
git pull --rebase

echo "Regenerating reports + overviews..."
"$PY" analyze_git.py

echo "Committing overviews + summary cache..."
git add -A index.html playback/ webrtc/ gfx/ .summary_cache/
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "overviews: local refresh $(date -u +'%Y-%m-%d')"
  git push
  echo "Pushed."
fi
