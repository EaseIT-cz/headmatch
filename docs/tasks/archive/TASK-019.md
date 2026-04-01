# TASK-019 — Add TUI and GUI run/history browsing

## Summary
Let users inspect recent runs and open the generated output guides from the terminal UI and GUI.

## Context
The interactive frontends should not only start workflows. They should also help users recover what they did last time.

## Scope
- List recent runs.
- Show run summaries.
- Open or display `README.txt` and key result metadata.
- Keep navigation simple.

## Out of scope
- File manager integration.
- Rich analytics dashboards.

## Acceptance criteria
- Users can see recent runs.
- [done] Users can inspect a run’s summary from the TUI or GUI.
- The workflow fits the same beginner-friendly tone as the rest of the app.

## Suggested files/components
- future `headmatch/tui.py`
- future `headmatch/gui.py`
- `headmatch/pipeline.py`
- `headmatch/io_utils.py`


## Status

Done. The TUI and GUI both read the shared `run_summary.json` / `README.txt` history contract.
