# TASK-079 — Real headphone database search

## Summary
Replace the placeholder `search_headphone` with an actual search that queries the AutoEQ GitHub repository and returns matching headphone models with download URLs.

## Context
`search_headphone` currently returns static instructions telling the user to browse GitHub manually. A real search would let users find and download FR curves without leaving the CLI or GUI.

## Scope
- Query the AutoEQ GitHub repository tree via the GitHub API (no auth required for public repos).
- Match headphone model names against the query string (case-insensitive substring match).
- Return a list of matches with the raw CSV URL for each.
- Cache the repository tree locally (e.g., in `~/.cache/headmatch/autoeq_index.json`) with a TTL (e.g., 24 hours) to avoid hitting the API on every search.
- Update the CLI `search-headphone` command to display results with copy-paste-ready `fetch-curve` commands.
- Update the GUI Fetch Curve view to include a search field that populates results.

## Out of scope
- Supporting databases other than AutoEQ (future).
- Downloading multiple curves in batch.
- Authenticated API access.

## Acceptance criteria
- `headmatch search-headphone "HD650"` returns matching entries with URLs.
- Results are cached locally; repeated searches don't hit the API.
- GUI search field shows matches and allows one-click fetch.
- Graceful fallback if the API is unreachable (show cached results or the old placeholder message).
- Tests cover parsing, caching, and error handling (mock the API).

## Suggested files
- `headmatch/headphone_db.py`
- `headmatch/cli.py`
- `headmatch/gui.py` / `headmatch/gui_views.py`
- `tests/test_headphone_db.py`
