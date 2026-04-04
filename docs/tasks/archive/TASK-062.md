# TASK-062 — Add one-line confidence verdict to CLI fit output

## Summary
The CLI `fit` and `measure` commands print confidence details, but the first line a user sees should be a single-line pass/fail verdict before the breakdown.

## Context
`print_run_confidence` in `cli.py` prints the confidence label, score, headline, interpretation, warnings, and troubleshooting steps. This is thorough but the user has to read several lines to know if the run is usable. A single colored verdict line at the top (e.g., "✓ This run looks trustworthy" or "⚠ Low confidence — check the details below") would make the output scannable.

## Scope
- Add a one-line verdict as the first line of `print_run_confidence`.
- Use ANSI color codes when stdout is a TTY (green/yellow/red).
- Fall back to plain unicode prefix when not a TTY.

## Out of scope
- Changing confidence scoring.
- Adding new CLI flags.
- Modifying the detailed output that follows the verdict.

## Acceptance criteria
- `headmatch measure` and `headmatch fit` print a single-line verdict before the existing confidence output.
- The verdict is green for high, yellow for medium, red for low confidence.
- Plain terminals get a unicode prefix instead of ANSI codes.
- Existing CLI tests pass.

## Suggested files/components
- `headmatch/cli.py`
- `tests/test_cli.py`
