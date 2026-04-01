# TASK-033 — Surface confidence more clearly in the CLI

## Summary
Make the confidence/trust summary more visible and more useful in the CLI so users can understand run quality without opening JSON files first.

## Context
The GUI confidence presentation pass is now complete. The active backlog item is to surface confidence and interpretation more clearly in the GUI and CLI. The backend confidence summary already exists and should remain the source of truth.

## Scope
- Improve the CLI post-run output so confidence/trust status is surfaced directly.
- Show the most useful confidence label/score/headline and concise warnings or interpretation text.
- Reuse the existing run-summary/report contract.
- Update tests as needed.

## Out of scope
- New confidence heuristics.
- GUI changes.
- Troubleshooting flow design beyond concise guidance tied to existing confidence output.
- Broad CLI redesign.

## Acceptance criteria
- CLI users can see the confidence level and a short interpretation without opening `run_summary.json` manually.
- Existing JSON outputs remain the source of truth.
- CLI tests cover the new presentation behavior.
- Full test suite passes.

## Suggested files/components
- `headmatch/cli.py`
- `headmatch/contracts.py` if needed
- `headmatch/history.py` only if directly useful
- `tests/test_cli.py`
- `tests/test_integration_cli.py` if needed
