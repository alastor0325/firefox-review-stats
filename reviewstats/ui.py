"""Shared UI fragments reused across the landing picker and the per-team
pages, so the markup and the repo URL stay in one place."""

# Single source of truth for the source-repo link.
REPO_URL = "https://github.com/alastor0325/firefox-review-stats"

# The GitHub "mark" (octocat) as an inline SVG. `currentColor` lets the CSS
# below drive its colour. Kept here once so both pages share the same glyph.
_GITHUB_MARK_SVG = (
    '<svg viewBox="0 0 16 16" width="22" height="22" aria-hidden="true">'
    '<path fill="currentColor" fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 '
    "3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37"
    "-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01"
    " 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64"
    "-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 "
    "2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82"
    ".44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95"
    ".29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 "
    '0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>'
)


def github_corner_html(repo_url: str = REPO_URL) -> str:
    """A small GitHub mark fixed in the top-right corner, linking to the
    source repo in a new tab. Shared by the landing picker and every
    per-team page so the icon and its URL never drift apart."""
    return (
        f'<a class="gh-corner" href="{repo_url}" target="_blank" rel="noopener"'
        ' title="View the source on GitHub" aria-label="View the source on GitHub">'
        f"{_GITHUB_MARK_SVG}</a>"
    )


# Styling for github_corner_html(). Uses --muted/--ink, which both pages
# define with the same values. z-index sits above any sticky header (the
# per-team page's .top-bar is z-index 100) so the icon is never occluded.
GITHUB_CORNER_CSS = """\
.gh-corner {
  position: fixed;
  top: 14px;
  right: 16px;
  z-index: 101;
  color: var(--muted);
  line-height: 0;
  transition: color 0.15s;
}
.gh-corner:hover { color: var(--ink); }"""
