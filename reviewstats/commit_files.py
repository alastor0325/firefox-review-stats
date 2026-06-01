"""Fetch the list of files changed by a commit, cached on disk.

`fetch_commits` returns commits without file paths — that's all the
list endpoint gives us. The single-commit endpoint
(`/repos/<repo>/commits/<sha>`) does include a `files` array, but each
call is one HTTP round-trip. To keep weekly regenerations cheap we
cache per-sha results to `.commit_files_cache/<sha>.json` and only
hit the API for SHAs we haven't seen before.

The classification logic that consumes these (which dom/media
subdirectory each "without team review" commit primarily belongs to)
lives in `reviewstats.metrics`.
"""

import json
from pathlib import Path

from reviewstats import github_http


_API = "https://api.github.com"
_PER_PAGE = 100  # matches github_commits._PER_PAGE


def fetch_commit_files(repo: str, sha: str, *, token: str | None) -> list[str]:
    """Single-commit GitHub API call. Returns the file paths the
    commit changed (renamed, added, deleted, modified — all).

    GitHub caps the `files` array at 300 entries; for the rare
    mega-commits above that, the truncated subset is fine: we use
    these paths to classify primary subdirectory, and the answer for
    a 300+-file mega-refactor is going to be the same either way.
    """
    url = f"{_API}/repos/{repo}/commits/{sha}"
    data = github_http.get_json(url, token=token)
    return [f["filename"] for f in data.get("files", [])]


def fetch_commit_files_cached(
    repo: str,
    sha: str,
    *,
    cache_dir: Path,
    token: str | None,
) -> list[str]:
    """Disk-cached wrapper around `fetch_commit_files`.

    Cache key is the full sha — files don't change after a commit is
    written, so an entry is good forever.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{sha}.json"
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except json.JSONDecodeError:
            # Corrupt cache entry — refetch and overwrite.
            pass
    files = fetch_commit_files(repo, sha, token=token)
    cache_path.write_text(json.dumps(files))
    return files
