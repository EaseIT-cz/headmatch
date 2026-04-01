# TASK-009 — Add TUI run/history browsing

## Summary
Let users inspect recent runs and open the generated output guides from the terminal UI.

## Context
The TUI should not just start workflows. It should also help users recover what they did last time.

## Scope
- List recent runs.
- Show run summaries.
- Open or display `README.txt` and key result metadata.
- Keep navigation simple.

## Out of scope
- GUI history browser.
- File manager integration.

## Acceptance criteria
- Users can see recent runs.
- Users can inspect a run’s summary from the TUI.
- The workflow fits the same beginner-friendly tone as the rest of the app.

## Suggested files/components
- future `headmatch/tui.py`
- `headmatch/pipeline.py`
- `headmatch/io_utils.py`
