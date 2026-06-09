"""The GitHub corner icon is shared by the landing picker and every
per-team page (reviewstats/ui.py), so the markup and repo URL live in
one place. These tests pin the shared helper and assert both pages
actually render it."""

import re

from reviewstats.landing import render_landing_page
from reviewstats.teams import PLAYBACK_TEAM
from reviewstats.ui import REPO_URL, github_corner_html


def test_corner_html_is_a_repo_link_with_an_svg_mark():
    html = github_corner_html()
    m = re.search(r'<a class="gh-corner" href="(https://github\.com/[^"]+)"[^>]*>', html)
    assert m, "expected an <a class=gh-corner> pointing at the repo"
    assert m.group(1) == REPO_URL
    # Opens in a new tab, safely, and carries the inline GitHub mark.
    assert 'target="_blank"' in html and "noopener" in html
    assert "<svg" in html and "</svg>" in html


def test_corner_html_honours_a_custom_repo_url():
    html = github_corner_html("https://github.com/example/repo")
    assert 'href="https://github.com/example/repo"' in html


def test_landing_page_carries_the_github_corner_icon():
    """The landing picker shows the same fixed corner icon as the team
    pages (added alongside the per-team change), styled by the shared CSS."""
    html = render_landing_page([PLAYBACK_TEAM])
    assert github_corner_html() in html
    # The shared styling is present so the icon is positioned/coloured.
    assert ".gh-corner {" in html
